#include <Arduino.h>
#ifdef ESP32
#include <WiFi.h>
#include <AsyncTCP.h>
#include <HTTPClient.h>
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
#include <Process.h>

#define DEBUG_PULSES

// Webhook support
const char* serverName = "http://192.168.1.122:5000/webhook";  

const byte OUTPUT_PIN = 16; // 2
const byte INPUT_PIN = 17; // 3
const byte PULSE_BUFFER_SIZE = 600;

volatile unsigned long timeLowTransition = 0;
volatile byte bufferReadPosition = 0;
volatile byte bufferWritePosition = 0;
volatile byte pulseBuffer[PULSE_BUFFER_SIZE];

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
const char* ssid = "DILNA21";
const char* password = "nanotriko";
const char* PARAM_MESSAGE = "message";

void notFound(AsyncWebServerRequest *request) {
    request->send(404, "text/plain", "Not found");
}

void setup()
{
  Serial.begin(115200L);

  pinMode(OUTPUT_PIN, OUTPUT);
  digitalWrite(OUTPUT_PIN, LOW);
  pinMode(INPUT_PIN, INPUT);
  Serial.println("Booting User code...");
  // Setup command handlers
  commandHandlers[0x01] = handleStopCommand; // Command byte for 'Stop'
  commandHandlers[0x02] = handleStopCommand; // Command byte for 'Pause'
  commandHandlers[0x03] = handleStopCommand; // Command byte for 'Pause'
  commandHandlers[0x04] = handleStopCommand; // Command byte for 'Eject'
  commandHandlers[0x08] = handleNextCommand; // Command byte for 'Next'  
  commandHandlers[0x09] = handlePrevCommand; // Command byte for 'Prev'  
  commandHandlers[0x50] = handlePlayCommand; // Command byte for 'Play'
  commandHandlers[0x0C] = handle30SecCommand; // Command byte for '30 sec remaining'
  // Add more command handlers as needed
  Serial.println("attach interrupt");
  attachInterrupt(digitalPinToInterrupt(INPUT_PIN), busChange, CHANGE);



  WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    if (WiFi.waitForConnectResult() != WL_CONNECTED) {
        Serial.printf("WiFi Failed!\n");
        return;
    }

    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

  startTime = readCurrentTimestamp();

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
      processBodyHandler(request, data, len, index, total);
      request->send(200, "text/plain", "OK");
    });

    server.onNotFound(notFound);

    server.begin();
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

// This interrupt handler receives data from a remote slink device
void busChange()
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
    Serial.println(F("Pulse buffer overflow when receiving data"));
    return;
  }

  // Divide by 10 to make the pulse length fit in 8 bits
  pulseBuffer[bufferWritePosition] = std::min(255, timeLow / 10);
  bufferWritePosition = (bufferWritePosition + 1) % PULSE_BUFFER_SIZE;
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
        partialOutput = false;
      }

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
    if (messageBytes[0] == 0x98 || messageBytes[0] == 0x99 || messageBytes[0] == 0x9A || messageBytes[0] == 0x9B || messageBytes[0] == 0x9C || messageBytes[0] == 0x9D) {
      handleCommand(messageBytes);
    }
    messageBytes.clear(); // Clear the message bytes after handling
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
  stopButtonCounter++;
  if (stopButtonCounter >= 2) {
    stopButtonCounter = 0;
 
    //client.get("http://localhost:8080/stop");
    httpPost("{\"status\":\"STOP\"}");
  }
  if (isTimerEnabled) {
    isTimerEnabled = false;
    return;
  }
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

  int disc = 0;
  int track = 0;
  if (messageSize >= 3) {
    Serial.println("converting disc");
    disc = hexByteToDecimalInt(message[2]);
  }
  if (messageSize >= 4) {
    Serial.println("converting track");
    track = hexByteToDecimalInt(message[3]);
  }

  int deckId = message[0];

  Serial.println("sending html get");

  char buffer[256];

  // Format the string using sprintf
  sprintf(buffer, "{\"status\":\"PLAY\", \"device\":\"%s\", \"cd\":\"%s\", \"track\":\"%s\", \"duration\":\"%s\"}", String(deckId), String(disc), String(track), String(duration));

  // Convert the character buffer to a String
  String jsonString = String(buffer);
  //client.get("http://localhost:8080/playButton/" + String(deckId) + "/" + String(disc) + "/" + String(track) + "/" + String(duration));
  //httpPost(jsonString); // using prepare_track instead


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

  // Format the string using sprintf
  sprintf(buffer, "{\"status\":\"NEXT_TRACK_IN\", \"duration\":\"%s\"}", String(duration-3));

  // Convert the character buffer to a String
  String jsonString = String(buffer);
  //client.get("http://localhost:8080/nextTrack/" + String(duration-3));
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

  // Format the string using sprintf
  sprintf(buffer, "{\"status\":\"PREPARE_TRACK\", \"track\":\"%s\"}", String(command));

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
  if (!isBusIdle()) {
    return false;
  }

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
  return true;
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
  processSlinkInput();
  //processSerialInput();

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
  // Check WiFi connection status
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;

        // Specify request destination
        http.begin(serverName);

        // Specify content type header
        http.addHeader("Content-Type", "application/json");

        // Send HTTP POST request
        int httpResponseCode = http.POST(jsonPayload);

        // Check the returning code
        if (httpResponseCode > 0) {
            Serial.print("HTTP Response code: ");
            Serial.println(httpResponseCode);

            // Get the response payload
            String response = http.getString();
            Serial.print("Response: ");
            Serial.println(response);
        }
        else {
            Serial.print("Error code: ");
            Serial.println(httpResponseCode);
        }

        // Free resources
        http.end();
    }
}
