#include <Arduino.h>
#ifdef ESP32
#include <WiFi.h>
#include <AsyncTCP.h>
#include <HTTPClient.h>
#include "esp_wifi.h"
#include "esp_mac.h"
#elif defined(ESP8266)
#include <ESP8266WiFi.h>
#include <ESPAsyncTCP.h>
#include <ESP8266HTTPClient.h>
#endif
#include <ESPAsyncWebServer.h>

#include <stdlib.h>
#include <vector>
#include <functional>
#include <map>
#include <function_objects.h>
//#include <Process.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#define DEBUG_PULSES

// Webhook support
String webhookUrl = "http://192.168.137.1:5000/webhook";

// --- Webhook queue: offload HTTPClient to a dedicated FreeRTOS task ---
// This prevents lwIP assert crashes when HTTPClient (loop task) and
// ESPAsyncWebServer (AsyncTCP task) touch TCP simultaneously.
#define WEBHOOK_QUEUE_LEN 8
#define WEBHOOK_MSG_SIZE 256
static QueueHandle_t webhookQueue = NULL;
static TaskHandle_t webhookTaskHandle = NULL;

struct WebhookMsg {
  char payload[WEBHOOK_MSG_SIZE];
};

void webhookTask(void *pvParameters) {
  WebhookMsg msg;
  for (;;) {
    if (xQueueReceive(webhookQueue, &msg, portMAX_DELAY) == pdTRUE) {
      if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(webhookUrl);
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(3000);
        int code = http.POST(String(msg.payload));
        if (code > 0) {
          Serial.printf("Webhook OK %d\n", code);
        } else {
          Serial.printf("Webhook err %d\n", code);
        }
        http.end();
      }
    }
  }
}

const byte OUTPUT_PIN = 16; // 2
const byte INPUT_PIN = 14; // 3
const byte PULSE_BUFFER_SIZE = 200;

volatile unsigned long timeLowTransition = 0;
volatile byte bufferReadPosition = 0;
volatile byte bufferWritePosition = 0;
volatile byte pulseBuffer[PULSE_BUFFER_SIZE];
volatile unsigned int pulseBufferOverflows = 0;

// Define a buffer to hold the incoming playlist data
char playlistBuffer[512]; // Adjust the size as needed for your data
int playlistBufferLength = 0;
int stopButtonCounter = 0;

// Global variables
std::vector<byte> messageBytes;
std::map<byte, FunctionObject<void(const std::vector<byte>&)>> commandHandlers;
// Global playlist and current position
std::vector<String> playlist;
unsigned int currentPlaylistPosition = 0;

int64_t startTime = 0;
int64_t alarmTime = 0;
bool isTimerEnabled = false;

#ifdef DEBUG_PULSES
String pulseLengths;
#endif

AsyncWebServer server(8080);
bool serverStarted = false;
const char* ssid = "COREI9";
const char* password = "helloworld";
const char* PARAM_MESSAGE = "message";

void notFound(AsyncWebServerRequest *request) {
    request->send(404, "text/plain", "Not found");
}

// This interrupt handler receives data from a remote slink device
void IRAM_ATTR busChange()
{
  static unsigned long timeOfPreviousInterrupt = 0;
  unsigned long timeNow = micros();

  if (timeNow - timeOfPreviousInterrupt < 100) {
    return;
  }
  timeOfPreviousInterrupt = timeNow;

 int busState = digitalRead(INPUT_PIN);
  if (busState == LOW) {
    timeLowTransition = timeNow;
    return;
  }

  // Bus is high. The time that the bus has been low determines what
  // has happened. Let's store this information for analysis outside
  // of the interrupt handler.
  int timeLow = timeNow - timeLowTransition;

  if ((bufferWritePosition + 1) % PULSE_BUFFER_SIZE == bufferReadPosition) {
    pulseBufferOverflows++;
    return;
  }

  // Divide by 10 to make the pulse length fit in 8 bits
  pulseBuffer[bufferWritePosition] = std::min(255, timeLow / 10);
  bufferWritePosition = (bufferWritePosition + 1) % PULSE_BUFFER_SIZE;
}

void setup()
{
  Serial.begin(115200L);

  pinMode(OUTPUT_PIN, OUTPUT);
  digitalWrite(OUTPUT_PIN, LOW);
  pinMode(INPUT_PIN, INPUT);
  Serial.println("Booting User code...");
  // Setup command handlers
  commandHandlers[0x00] = handlePlayStateCommand;
  commandHandlers[0x01] = handleStopCommand;
  commandHandlers[0x02] = handlePauseCommand;
  commandHandlers[0x03] = handlePauseToggleCommand;
  commandHandlers[0x06] = handleCarouselMovingCommand;
  commandHandlers[0x08] = handleReadyCommand;
  commandHandlers[0x0C] = handle30SecCommand;
  commandHandlers[0x18] = handleDoorOpenCommand;
  commandHandlers[0x2E] = handlePowerOnCommand;
  commandHandlers[0x2F] = handlePowerOffCommand;
  commandHandlers[0x50] = handlePlayCommand;
  commandHandlers[0x51] = handleIgnoredStatusCommand;
  commandHandlers[0x52] = handleDisplayDiscCommand;
  commandHandlers[0x54] = handleLoadingDiscCommand;
  commandHandlers[0x58] = handleDiscLoadedCommand;
  commandHandlers[0x61] = handleModelIdCommand;
  commandHandlers[0x70] = handlePlayerStatusCommand;
  Serial.println("attach interrupt");
  //attachInterrupt(digitalPinToInterrupt(INPUT_PIN), busChange, CHANGE);



  // Robust WiFi init: full stack reset to clear stale state
  WiFi.disconnect(true, true);
  delay(500);
  WiFi.mode(WIFI_OFF);
  delay(500);
  WiFi.mode(WIFI_STA);
  delay(500);
  WiFi.setSleep(false);   // Disable modem sleep for reliability

  // Ensure valid MAC (eFuse may read zeros on some boards)
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  bool macValid = false;
  for (int i = 0; i < 6; i++) { if (mac[i] != 0) { macValid = true; break; } }
  if (!macValid) {
    uint8_t fallback[6] = {0x24, 0x0A, 0xC4, 0x82, 0x42, 0x68};
    memcpy(mac, fallback, 6);
    Serial.println("eFuse MAC is zeros, using fallback");
  }
  esp_wifi_set_mac(WIFI_IF_STA, mac);
  Serial.printf("MAC: %s\n", WiFi.macAddress().c_str());

  // Disable PMF (802.11w) — ESP32 rev 0 can't handle it, causes AUTH_EXPIRE
  wifi_config_t wifi_cfg = {};
  esp_wifi_get_config(WIFI_IF_STA, &wifi_cfg);
  wifi_cfg.sta.pmf_cfg.capable = false;
  wifi_cfg.sta.pmf_cfg.required = false;
  esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg);

  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi to '");
  Serial.print(ssid);
  Serial.print("'");
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 20000) {
    delay(500);
    Serial.print('.');
    Serial.print(WiFi.status());
  }
  Serial.println();

  bool wifiConnected = WiFi.status() == WL_CONNECTED;
  if (!wifiConnected) {
    Serial.print("WiFi Failed, status=");
    Serial.print(WiFi.status());
    // Status codes: 0=IDLE, 1=NO_SSID_AVAIL, 4=CONNECT_FAILED, 6=WRONG_PASSWORD
    if (WiFi.status() == 1) Serial.println(" (NO_SSID_AVAIL - SSID not found)");
    else if (WiFi.status() == 4) Serial.println(" (CONNECT_FAILED)");
    else if (WiFi.status() == 6) Serial.println(" (WRONG_PASSWORD)");
    else Serial.println();
  } else {
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  }

  startTime = readCurrentTimestamp();

  // Register HTTP routes unconditionally so the server can start later
  // if WiFi connects after the initial timeout.
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
        request->send(200, "text/plain", "Hello, world");
    });

    // Send a GET request to <IP>/get?message=<message>
    server.on("/get", HTTP_GET, [] (AsyncWebServerRequest *request) {
        String message;
        if (request->hasParam(PARAM_MESSAGE)) {
            message = request->getParam(PARAM_MESSAGE)->value();
        } else {
            message = "No message sent";
        }
        request->send(200, "text/plain", "Hello, GET: " + message);
    });

      server.on("/status", HTTP_GET, [](AsyncWebServerRequest *request) {
        String payload = "{\"device\":\"sony_slink_esp32\",\"version\":\"main-rx14\",\"ip\":\"";
        payload += WiFi.localIP().toString();
        payload += "\",\"mac\":\"";
        payload += WiFi.macAddress();
        payload += "\",\"webhook_url\":\"";
        payload += webhookUrl;
        payload += "\",\"rx_pin\":14,\"tx_pin\":16}";
        request->send(200, "application/json", payload);
      });

      server.on("/webhook-target", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->send(200, "application/json", "{\"webhook_url\":\"" + webhookUrl + "\"}");
      });

    // Send a POST request to <IP>/post with a form field message set to <message>
    server.on("/post", HTTP_POST, [](AsyncWebServerRequest *request) {
        // request->send(200, "text/plain", "Hello, POST: " + message);
    }, [](AsyncWebServerRequest *request, const String& filename, size_t index, uint8_t *data, size_t len, bool final) {
        // upload
    }, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
        processBodyHandler(request, data, len, index, total);
        request->send(200, "text/plain", "OK");
    });

    server.onRequestBody([](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
      if (request->url() == "/webhook-target") {
        static String bodyData;
        processBodyData(data, len, index, total, bodyData);
        if (index + len == total) {
          int keyIndex = bodyData.indexOf("webhook_url");
          int valueStart = bodyData.indexOf('"', bodyData.indexOf(':', keyIndex));
          int valueEnd = bodyData.indexOf('"', valueStart + 1);
          if (keyIndex >= 0 && valueStart >= 0 && valueEnd > valueStart) {
            webhookUrl = bodyData.substring(valueStart + 1, valueEnd);
          }
          request->send(200, "application/json", "{\"webhook_url\":\"" + webhookUrl + "\"}");
        }
        return;
      }
      processBodyHandler(request, data, len, index, total);
      request->send(200, "text/plain", "OK");
    });

    server.onNotFound(notFound);

  // Create webhook queue and dedicated task (runs on core 0, isolated from AsyncTCP)
  webhookQueue = xQueueCreate(WEBHOOK_QUEUE_LEN, sizeof(WebhookMsg));
  xTaskCreatePinnedToCore(webhookTask, "webhook", 4096, NULL, 3, &webhookTaskHandle, 0);
  Serial.println("Webhook task started on core 0");

  // Start the server immediately if WiFi is already connected.
  if (wifiConnected && !serverStarted) {
    server.begin();
    serverStarted = true;
    Serial.println("HTTP server started");
  }
    attachInterrupt(digitalPinToInterrupt(INPUT_PIN), busChange, CHANGE);
    enableContinuousStatus();
}

void processBodyHandler(AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
  static String bodyData;
  processBodyData(data, len, index, total, bodyData);
  // Convert String to char array using bodyData.length()
  size_t bodyLength = bodyData.length();
  bodyData.toCharArray(playlistBuffer, bodyLength + 1);
  
  // Ensure the buffer is null-terminated
  playlistBuffer[bodyLength] = '\0';
  playlistBufferLength = bodyLength;
  //readSLinkBuffer(bodyLength);  
}

String processBodyData(uint8_t *data, size_t len, size_t index, size_t total, String &bodyData) {
  if (index == 0) {
    bodyData = "";  // Initialize the bodyData string
  }
  
  // Append received data to bodyData
  bodyData += String((const char*)data).substring(0, len);

  if (index + len == total) {
    
    // Trim the bodyData to the specified length
    if (bodyData.length() > total) {
      bodyData = bodyData.substring(0, total);
    }
  }
  
  return bodyData;
}

long readCurrentTimestamp() {
  return esp_timer_get_time();
}


void processSlinkInput()
{
  static byte currentByte = 0;
  static byte currentBit = 0;
  static bool partialOutput = false;

  while (bufferReadPosition != bufferWritePosition) {
    int timeLow = pulseBuffer[bufferReadPosition] * 10;

    bufferReadPosition = (bufferReadPosition + 1) % PULSE_BUFFER_SIZE;

#ifdef DEBUG_PULSES
    if (timeLow > 2000) {
      pulseLengths = String();
    }
    else {
      pulseLengths += " ";
    }
    pulseLengths += String(timeLow, DEC);
#endif

    if (timeLow > 2000) {
      // 2400 us -> new data sequence

      if (partialOutput) {
        if (currentBit != 0) {
          Serial.print(F("!Discarding "));
          Serial.print(currentBit);
          Serial.print(F(" stray bits"));
        }

        Serial.print('\n');
        if (currentBit == 0 && !messageBytes.empty() && (messageBytes[0] == 0x98 || messageBytes[0] == 0x99 || messageBytes[0] == 0x9A || messageBytes[0] == 0x9B || messageBytes[0] == 0x9C || messageBytes[0] == 0x9D)) {
          handleCommand(messageBytes);
        }
        messageBytes.clear();
        partialOutput = false;
      }

      currentByte = 0;
      currentBit = 0;
      continue;
    }

    partialOutput = true;
    currentBit += 1;
    if (timeLow > 900) {
      // 1200 us -> bit == 1
      bitSet(currentByte, 8 - currentBit);
    }
    else {
      // 600 us -> bit == 0
      bitClear(currentByte, 8 - currentBit);
    }

    if (currentBit == 8) {
      if (currentByte <= 0xF) {
        Serial.print(0, HEX);
      }
      Serial.print(currentByte, HEX);
      messageBytes.push_back(currentByte);
      currentBit = 0;
    }
  }

  if (partialOutput && isBusIdle()) {
    Serial.print('\n');
    partialOutput = false;
    if (!messageBytes.empty() && (messageBytes[0] == 0x98 || messageBytes[0] == 0x99 || messageBytes[0] == 0x9A || messageBytes[0] == 0x9B || messageBytes[0] == 0x9C || messageBytes[0] == 0x9D)) {
      handleCommand(messageBytes);
    }
    messageBytes.clear(); // Clear the message bytes after handling
    currentByte = 0;
    currentBit = 0;
  }
}

void handleCommand(const std::vector<byte>& message) {
  if (message.size() < 2) return; // Ensure there's at least an ID and a command

  byte commandByte = message[1];
  if (commandHandlers.find(commandByte) != commandHandlers.end()) {
    commandHandlers[commandByte](message);
  } else {
    // Handle unknown command or ignore
  }
}

String rawMessageHex(const std::vector<byte>& message) {
  String raw;
  for (size_t i = 0; i < message.size(); ++i) {
    if (i > 0) {
      raw += " ";
    }
    if (message[i] <= 0x0F) {
      raw += "0";
    }
    raw += String(message[i], HEX);
  }
  raw.toUpperCase();
  return raw;
}

String hexByteJson(byte value) {
  String encoded;
  if (value <= 0x0F) {
    encoded += "0";
  }
  encoded += String(value, HEX);
  encoded.toUpperCase();
  return encoded;
}

void postSimpleStatus(const char* status, const std::vector<byte>& message) {
  String json = "{\"status\":\"" + String(status) + "\",\"raw\":\"" + rawMessageHex(message) + "\"}";
  httpPost(json);
}

void postDiscStatus(const char* status, const std::vector<byte>& message) {
  if (message.size() >= 3) {
    String json = "{\"status\":\"" + String(status) + "\",\"device\":\"" + hexByteJson(message[0]) + "\",\"disc\":\"" + hexByteJson(message[2]) + "\",\"raw\":\"" + rawMessageHex(message) + "\"}";
    httpPost(json);
    return;
  }
  postSimpleStatus(status, message);
}

void handlePlayStateCommand(const std::vector<byte>& message) {
  postSimpleStatus("PLAY", message);
}

// Function to convert a hex string to an integer
int hexStringToInt(String hexString) {
  // strtol function converts the string to a long integer
  // Parameters: input string, reference to the string after the number, numerical base
  return (int)strtol(hexString.c_str(), NULL, 16);
}

String intToHexString(int value) {
  char hexString[5]; // 4 characters for the hex representation and one for the null terminator
  itoa(value, hexString, 16); // Convert the integer to a hex string
  return String(hexString); // Convert the char array to a String object and return it
}

// Function to convert a single nibble (4 bits) to a hexadecimal character
char nibbleToHexCharacter(byte nibble) {
  nibble &= 0x0F; // Ensure it's only 4 bits
  return nibble < 10 ? '0' + nibble : 'A' + nibble - 10;
}

// Function to convert a byte representing a hexadecimal value to an integer
int hexByteToDecimalInt(byte hexByte) {
  char str[3];
  
  // Convert each nibble to its ASCII character representation
  str[0] = nibbleToHexCharacter(hexByte >> 4);
  str[1] = nibbleToHexCharacter(hexByte);
  str[2] = '\0'; // Null-terminator for string

  // Convert the string to an integer
  return atoi(str);
}

void handleStopCommand(const std::vector<byte>& message) {
  stopButtonCounter = 0;
  httpPost("{\"status\":\"STOP\"}");
  if (isTimerEnabled) {
    isTimerEnabled = false;
    return;
  }
}

void handlePauseCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;
  httpPost("{\"status\":\"PAUSE\"}");
}

void handlePauseToggleCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;
  httpPost("{\"status\":\"PAUSE_TOGGLE\"}");
}

void handleEjectCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;
  httpPost("{\"status\":\"EJECT\"}");
}

void handleCarouselMovingCommand(const std::vector<byte>& message) {
  postSimpleStatus("CAROUSEL_MOVING", message);
}

void handleReadyCommand(const std::vector<byte>& message) {
  postSimpleStatus("READY", message);
}

void handleDoorOpenCommand(const std::vector<byte>& message) {
  postSimpleStatus("DOOR_OPEN", message);
}

void handlePowerOnCommand(const std::vector<byte>& message) {
  postSimpleStatus("POWER_ON", message);
}

void handlePowerOffCommand(const std::vector<byte>& message) {
  postSimpleStatus("POWER_OFF", message);
}

void handlePlayCommand(const std::vector<byte>& message) {
  Serial.println("Incoming PLAY command");

  if (isTimerEnabled) {
    onTrackFinish();
    isTimerEnabled = false;
    //return;
  }
  
  int messageSize = message.size();
  Serial.println("Message size: " + String(messageSize));

  Serial.println(hexByteToDecimalInt(message[2]));

  for (size_t i = 0; i < message.size(); ++i) {
    Serial.print(i);
    Serial.print(": ");
    Serial.println(message[i], HEX); // Print each byte in hexadecimal format
  }
  Serial.println("Handing PLAY command");
  //int64_t duration = (minutes * 60000ul) + (seconds * 1000ul); // Convert to ms

  int minutes = 0;
  int seconds = 0;
  if (messageSize >= 6) {
    // Extract timing information from the message
    // Assuming message[4] is minutes and message[5] is seconds
    Serial.println("converting minutes");
    minutes = hexByteToDecimalInt(message[4]);
    Serial.println(minutes);
    Serial.println("converting seconds");
    seconds = hexByteToDecimalInt(message[5]);
    Serial.println(seconds);
  }
  int64_t duration = (minutes * 60) + (seconds); // Convert to 
  // Set a timer to call onTrackFinish after the duration
  // You'll need to implement setTimer and onTrackFinish
  Serial.println("Duration: ");
  Serial.println(duration);

  // We Use handle30SecCommand() instead
  // TODO 3
  alarmTime = duration * 1000 * 1000; // convert to micro seconds
  startTime = readCurrentTimestamp();
  isTimerEnabled = true;

  int deckId = message[0];

  Serial.println("sending html get");

  char buffer[256];

  snprintf(buffer, sizeof(buffer), "{\"status\":\"PLAY\", \"device\":\"%02X\", \"cd\":\"%02X\", \"track\":\"%02X\", \"duration\":\"%lld\"}", deckId, messageSize >= 3 ? message[2] : 0, messageSize >= 4 ? message[3] : 0, static_cast<long long>(duration));

  // Convert the character buffer to a String
  String jsonString = String(buffer);
  httpPost(jsonString);


}

void handle30SecCommand(const std::vector<byte>& message) {
  int64_t duration = 30; // Convert to ms

  // Set a timer to call onTrackFinish after the duration
  // You'll need to implement setTimer and onTrackFinish
  Serial.println("Duration: ");
  Serial.println(30);
  alarmTime = duration * 1000 * 1000;
  // Reset the timer if you want it to start counting again
  startTime = readCurrentTimestamp();
  isTimerEnabled = true;
  //Bridge.put("nextTrackTimer", duration);

  // Define a character buffer to hold the formatted string
  char buffer[128];

  snprintf(buffer, sizeof(buffer), "{\"status\":\"NEXT_TRACK_IN\", \"duration\":\"%lld\"}", static_cast<long long>(duration - 3));

  // Convert the character buffer to a String
  String jsonString = String(buffer);
  httpPost(jsonString); 
}

void handleNextCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;

  //client.get("http://localhost:8080/nextTrack");
  httpPost("{\"status\":\"NEXT_TRACK\"}"); 
}

void handlePrevCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;

  //client.get("http://localhost:8080/prevTrack");
  httpPost("{\"status\":\"PREV_TRACK\"}"); 
}

void handleDisplayDiscCommand(const std::vector<byte>& message) {
  postDiscStatus("DISPLAY_DISC", message);
}

void handleLoadingDiscCommand(const std::vector<byte>& message) {
  postDiscStatus("LOADING_DISC", message);
}

void handleDiscLoadedCommand(const std::vector<byte>& message) {
  postDiscStatus("DISC_LOADED", message);
}

void handleModelIdCommand(const std::vector<byte>& message) {
  postSimpleStatus("MODEL_ID", message);
}

void handlePlayerStatusCommand(const std::vector<byte>& message) {
  postSimpleStatus("PLAYER_STATUS", message);
}

void handleUnknownStatusCommand(const std::vector<byte>& message) {
  postSimpleStatus("UNKNOWN_STATUS", message);
}

void handleIgnoredStatusCommand(const std::vector<byte>& message) {
  Serial.print("Ignoring status: ");
  Serial.println(rawMessageHex(message));
}

void playNextFromPlaylist() {
  Serial.println("playNextFromPlaylist() COMMAND:");
  Serial.println(currentPlaylistPosition);

  String command = playlist[currentPlaylistPosition];

  currentPlaylistPosition++;

  if (playlist.size() < currentPlaylistPosition) {
    currentPlaylistPosition = 0;
    command = playlist[currentPlaylistPosition];
    currentPlaylistPosition = 1;
  }

  Serial.println(command);

  // Logic to enqueue the new command to play a different disc and track
  byte commandBytes[command.length() / 2];
  for (int i = 0; i < sizeof(commandBytes); ++i) {
    String hexByte = command.substring(2 * i, 2 * i + 2);
    commandBytes[i] = strtol(hexByte.c_str(), NULL, 16);
  }

  if (!sendCommand(commandBytes, sizeof(commandBytes))) {
    // If send fails, re-queue command
    //bytesReceived = command + "\n" + bytesReceived;
    sendCommand(commandBytes, sizeof(commandBytes));
  }

      char buffer[256];

  snprintf(buffer, sizeof(buffer), "{\"status\":\"PREPARE_TRACK\", \"track\":\"%s\"}", command.c_str());

  // Convert the character buffer to a String
  String jsonString = String(buffer);
  httpPost(jsonString); // using PREPARE_TRACK instead of PLAY
}

void onTrackFinish() {
  Serial.println("onTrackFinish");
  playNextFromPlaylist();
}

bool isBusIdle()
{
  noInterrupts();
  bool isBusIdle = micros() - timeLowTransition > 1200 + 600 + 20000;
  interrupts();
  return isBusIdle;
}

void sendPulseDelimiter()
{
  digitalWrite(OUTPUT_PIN, LOW);
  delayMicroseconds(600);
}

void sendSyncPulse()
{
  digitalWrite(OUTPUT_PIN, HIGH);
  delayMicroseconds(2400);
  sendPulseDelimiter();
}

void sendBit(int bit)
{
  digitalWrite(OUTPUT_PIN, HIGH);
  if (bit) {
    delayMicroseconds(1200);
  }
  else {
    delayMicroseconds(600);
  }
  sendPulseDelimiter();
}

void sendByte(int value)
{
  for (int i = 7; i >= 0; --i) {
    sendBit(bitRead(value, i));
  }
}

void idleAfterCommand()
{
  delayMicroseconds(20000);
}

bool sendCommand(byte command[], int commandLength)
{
  unsigned long waitStart = millis();
  while (!isBusIdle()) {
    if (millis() - waitStart > 250) {
      Serial.print(F("sendCommand: BUS NOT IDLE after 250ms, cmd="));
      for (int i = 0; i < commandLength; ++i) {
        if (command[i] < 0x10) Serial.print('0');
        Serial.print(command[i], HEX);
      }
      Serial.println(F(" — ABORTING"));
      return false;
    }
    delayMicroseconds(1000);
  }

  unsigned long waitedMs = millis() - waitStart;
  Serial.print(F("sendCommand: bus idle after "));
  Serial.print(waitedMs);
  Serial.print(F("ms, sending "));
  for (int i = 0; i < commandLength; ++i) {
    if (command[i] < 0x10) Serial.print('0');
    Serial.print(command[i], HEX);
  }
  Serial.println();

  noInterrupts();
  sendSyncPulse();
  for (int i = 0; i < commandLength; ++i) {
    sendByte(command[i]);
  }

  // Clear interrupt flags because interrupts triggered when we sent
  // the command and the interrupts are queued for processing once
  // interrupts are re-enabled.
  //EIFR = bit(INTF0) | bit(INTF1);
  // TODO

  interrupts();
  idleAfterCommand();
  Serial.println(F("sendCommand: TX complete"));
  return true;
}

void enableContinuousStatus()
{
  byte command[] = {0x90, 0x25};
  for (int attempt = 0; attempt < 3; ++attempt) {
    if (sendCommand(command, sizeof(command))) {
      Serial.println("Continuous S-Link status enabled");
      return;
    }
    delay(100);
  }
  Serial.println("Continuous S-Link status enable failed");
}

//void processSerialInput()
//{
//  static String bytesReceived;
//
//  while (Serial.available()) {
//    bytesReceived += char(Serial.read());
//  }
//
//  const int eolPos = bytesReceived.indexOf("\n");
//  if (eolPos == -1) {
//    return;
//  }
//
//  const String command = bytesReceived.substring(0, eolPos);
//  bytesReceived.remove(0, command.length() + 1);
//
//#ifdef DEBUG_PULSES
//  if (command == "pulsedump") {
//    Serial.println(pulseLengths);
//    return;
//  }
//#endif
//
//  // A hexadecimal command is expected
//  if (command.length() % 2 != 0) {
//    Serial.println(F("Uneven length of Serial input"));
//    return;
//  }
//
//  for (int i = 0; i < command.length(); ++i) {
//    if (!isHexadecimalDigit(command[i])) {
//      Serial.println(F("Non-hexadecimal Serial input"));
//      return;
//    }
//  }
//
//  byte commandBytes[command.length() / 2];
//  for (int i = 0; i < sizeof(commandBytes); ++i) {
//    String hexByte = command.substring(2 * i, 2 * i + 2);
//    commandBytes[i] = strtol(hexByte.c_str(), NULL, 16);
//  }
//
//  if (!sendCommand(commandBytes, sizeof(commandBytes))) {
//    // If send fails, re-queue command
//    bytesReceived = command + "\n" + bytesReceived;
//  }
//}

void loop()
{
  static unsigned long lastStatusPrint = 0;

  // Start the HTTP server once WiFi becomes available (handles late connection).
  if (!serverStarted && WiFi.status() == WL_CONNECTED) {
    server.begin();
    serverStarted = true;
    Serial.print("HTTP server started (late WiFi), IP: ");
    Serial.println(WiFi.localIP());
  }

  processSlinkInput();
  //processSerialInput();

  if (millis() - lastStatusPrint > 5000) {
    lastStatusPrint = millis();
    Serial.print("STATUS wifi=");
    Serial.print(WiFi.status());
    Serial.print(" ip=");
    Serial.print(WiFi.localIP());
    Serial.print(" rxOverflows=");
    Serial.println(pulseBufferOverflows);
  }

  if (playlistBufferLength > 0) {
    readSLinkBuffer(playlistBufferLength);
    playlistBufferLength = 0;
  }

  if (isTimerEnabled) {
    if (readCurrentTimestamp() - startTime >= alarmTime) {
      // Time to trigger the alarm
      Serial.println("Alarm!");
      onTrackFinish();
      isTimerEnabled = false;
    }
  }

}

void readSLinkBuffer(int bytesRead) {
  bool isPlaylist = false;
  bool hasReadData = false;

  if (bytesRead > 0) {
    hasReadData = true;
    // Ensure the buffer is null-terminated
    playlistBuffer[bytesRead] = '\0';

    // Process the playlist
    Serial.println("Received data buffer:");
    Serial.println(playlistBuffer);

    // Split the playlist into songs and print each song
    char* song = strtok(playlistBuffer, "\r\n");
    while (song != NULL) {
      if (strcmp(song, "PLAYLIST") == 0) {
        Serial.println("Receiving PLAYLIST");
        currentPlaylistPosition = 0;
        isPlaylist = true;
        isTimerEnabled = false;
        playlist.clear();
      } else {
        if (!isPlaylist) {
          playlist.clear(); // TODO
        }
        String command = String(song);
        // A hexadecimal command is expected
        if (command.length() % 2 != 0) {
          Serial.println(F("Uneven length of Serial input"));
          break;
        }

        for (int i = 0; i < command.length(); ++i) {
          if (!isHexadecimalDigit(command[i])) {
            Serial.println(F("Non-hexadecimal Serial input"));
            break;
          }
        }

        if (isPlaylist) {
          playlist.push_back(command);
          Serial.print("Song: ");
          Serial.println(song);
        } else {
          Serial.println(song);

          byte commandBytes[command.length() / 2];
          for (int i = 0; i < sizeof(commandBytes); ++i) {
            String hexByte = command.substring(2 * i, 2 * i + 2);
            commandBytes[i] = strtol(hexByte.c_str(), NULL, 16);
          }

          if (!sendCommand(commandBytes, sizeof(commandBytes))) {
            // If send fails, re-queue command
            sendCommand(commandBytes, sizeof(commandBytes));
          }
        }
      }
      song = strtok(NULL, "\r\n"); // Get the next song
    }

  }

  if (hasReadData) {
    // Clear the playlist after processing
    Serial.println("Clear the playlist after processing");
    if (isPlaylist) {
      onTrackFinish();
    }
  }
}

void httpPost(String jsonPayload) {
  // Non-blocking: enqueue the message for the dedicated webhook task.
  // This avoids lwIP threading conflicts with ESPAsyncWebServer.
  if (webhookQueue == NULL) return;
  WebhookMsg msg;
  memset(msg.payload, 0, sizeof(msg.payload));
  jsonPayload.toCharArray(msg.payload, sizeof(msg.payload) - 1);
  // If queue is full, drop the oldest message to avoid blocking the caller
  if (xQueueSend(webhookQueue, &msg, 0) != pdTRUE) {
    WebhookMsg dropped;
    xQueueReceive(webhookQueue, &dropped, 0);  // drop oldest
    xQueueSend(webhookQueue, &msg, 0);          // enqueue new
    Serial.println("Webhook queue full, dropped oldest");
  }
}
