#include <StandardCplusplus.h>
#include <vector>
#include <functional>
#include <map>
#include <function_objects.h>
#include <Bridge.h>
#include <BridgeHttpClient.h>

#include <Process.h>

#define DEBUG_PULSES

const byte OUTPUT_PIN = 2;
const byte INPUT_PIN = 3;
const byte PULSE_BUFFER_SIZE = 200;

volatile unsigned long timeLowTransition = 0;
volatile byte bufferReadPosition = 0;
volatile byte bufferWritePosition = 0;
volatile byte pulseBuffer[PULSE_BUFFER_SIZE];

BridgeHttpClient client;

// Define a buffer to hold the incoming playlist data
char playlistBuffer[64]; // Adjust the size as needed for your data
int stopButtonCounter = 0;

// Global variables
std::vector<byte> messageBytes;
std::map<byte, FunctionObject<void(const std::vector<byte>&)>> commandHandlers;
// Global playlist and current position
std::vector<String> playlist;
unsigned int currentPlaylistPosition = 0;

unsigned long startTime;
unsigned long alarmTime;
bool isTimerEnabled = false;

#ifdef DEBUG_PULSES
String pulseLengths;
#endif

void setup()
{
  pinMode(OUTPUT_PIN, OUTPUT);
  digitalWrite(OUTPUT_PIN, LOW);
  pinMode(INPUT_PIN, INPUT);

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

  attachInterrupt(digitalPinToInterrupt(INPUT_PIN), busChange, CHANGE);

  Bridge.begin();
  // Console.begin();
  // Serial.begin(115200L);

  Console.println("Bridge started.");
  client.enableInsecure();
  startTime = readCurrentTimestamp();
}

long readCurrentTimestamp() {
  // Check the current time and compare it to the alarm time
  Process timeProc;
  timeProc.runShellCommand("date +%s");
  while(timeProc.available() == 0); // Wait for the command to complete

  // Read the timestamp as a string and convert it to an unsigned long
  String currentTime = timeProc.readString();
  currentTime.trim(); // Remove any trailing newline characters
  return currentTime.toInt();
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
    Console.println(F("Pulse buffer overflow when receiving data"));
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
          Console.print(F("!Discarding "));
          Console.print(currentBit);
          Console.print(F(" stray bits"));
        }

        Console.print('\n');
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
        Console.print(0, HEX);
      }
      Console.print(currentByte, HEX);
      messageBytes.push_back(currentByte);
      currentBit = 0;
    }
  }

  if (partialOutput && isBusIdle()) {
    Console.print('\n');
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
 
    client.getAsync("http://localhost:8080/stop");
  }
  if (isTimerEnabled) {
    isTimerEnabled = false;
    return;
  }
}

void handlePlayCommand(const std::vector<byte>& message) {
  Console.println("Incoming PLAY command");
  int messageSize = message.size();
  Console.println("Message size: " + String(messageSize));

  Console.println(hexByteToDecimalInt(message[2]));

  for (size_t i = 0; i < message.size(); ++i) {
    Console.println(message[i], HEX); // Print each byte in hexadecimal format
  }
  Console.println("Handing PLAY command");
  //unsigned long duration = (minutes * 60000ul) + (seconds * 1000ul); // Convert to ms

  int minutes = 0;
  int seconds = 0;
  if (messageSize >= 6) {
    // Extract timing information from the message
    // Assuming message[4] is minutes and message[5] is seconds
    Console.println("converting minutes");
    int minutes = hexByteToDecimalInt(message[4]);
    Console.println("converting seconds");
    int seconds = hexByteToDecimalInt(message[5]);
  }
  unsigned long duration = (minutes * 60ul) + (seconds); // Convert to s
  // Set a timer to call onTrackFinish after the duration
  // You'll need to implement setTimer and onTrackFinish
  /*Console.println("Duration: ");
  Console.println(duration);
  alarmTime = duration;
  startTime = readCurrentTimestamp();
  isTimerEnabled = true;*/
  int disc = 0;
  int track = 0;
  if (messageSize >= 3) {
    Console.println("converting disc");
    disc = hexByteToDecimalInt(message[2]);
  }
  if (messageSize >= 4) {
    Console.println("converting track");
    track = hexByteToDecimalInt(message[3]);
  }

  int deckId = message[0];

  Console.println("sending html get");

  client.get("http://localhost:8080/playButton/" + String(deckId) + "/" + String(disc) + "/" + String(track) + "/" + String(duration));

  if (isTimerEnabled) {
    onTrackFinish();
    isTimerEnabled = false;
    //return;
  }

}

void handle30SecCommand(const std::vector<byte>& message) {
  unsigned long duration = 30; // Convert to ms

  // Set a timer to call onTrackFinish after the duration
  // You'll need to implement setTimer and onTrackFinish
  Console.println("Duration: ");
  Console.println(30);
  alarmTime = duration;
  // Reset the timer if you want it to start counting again
  startTime = readCurrentTimestamp();
  isTimerEnabled = true;
  //Bridge.put("nextTrackTimer", duration);

  client.getAsync("http://localhost:8080/nextTrack/" + String(duration-3));
}

void handleNextCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;

  client.getAsync("http://localhost:8080/nextTrack");
}

void handlePrevCommand(const std::vector<byte>& message) {
  isTimerEnabled = false;

  client.getAsync("http://localhost:8080/prevTrack");
}

void playNextFromPlaylist() {
  const String command = playlist[currentPlaylistPosition];

  currentPlaylistPosition++;

  if (playlist.size() < currentPlaylistPosition) {
    currentPlaylistPosition = 0;
    command = playlist[currentPlaylistPosition];
    currentPlaylistPosition = 1;
  }

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
}

void onTrackFinish() {
  Console.println("onTrackFinish");
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
  EIFR = bit(INTF0) | bit(INTF1);

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
//    Console.println(pulseLengths);
//    return;
//  }
//#endif
//
//  // A hexadecimal command is expected
//  if (command.length() % 2 != 0) {
//    Console.println(F("Uneven length of Serial input"));
//    return;
//  }
//
//  for (int i = 0; i < command.length(); ++i) {
//    if (!isHexadecimalDigit(command[i])) {
//      Console.println(F("Non-hexadecimal Serial input"));
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

  if (isTimerEnabled) {
    /*if (readCurrentTimestamp() - startTime >= alarmTime) {
      // Time to trigger the alarm
      Console.println("Alarm!");
      onTrackFinish();
      isTimerEnabled = false;
    }*/
  }

  // Attempt to get the playlist data from the Bridge
  int bytesRead = Bridge.get("playlist", playlistBuffer, sizeof(playlistBuffer) - 1);

  bool isPlaylist = false;
  bool hasReadData = false;

  if (bytesRead > 0) {
    hasReadData = true;
    // Ensure the buffer is null-terminated
    playlistBuffer[bytesRead] = '\0';

    // Process the playlist
    Console.println("Received data buffer:");
    //Console.println(playlistBuffer);

    // Split the playlist into songs and print each song
    char* song = strtok(playlistBuffer, "\r\n");
    while (song != NULL) {
      if (strcmp(song, "PLAYLIST") == 0) {
        Console.println("Receiving PLAYLIST");
        currentPlaylistPosition = 0;
        isPlaylist = true;
        isTimerEnabled = false;
        playlist.clear();
      } else {
        String command = String(song);
        // A hexadecimal command is expected
        if (command.length() % 2 != 0) {
          Console.println(F("Uneven length of Serial input"));
          break;
        }

        for (int i = 0; i < command.length(); ++i) {
          if (!isHexadecimalDigit(command[i])) {
            Console.println(F("Non-hexadecimal Serial input"));
            break;
          }
        }

        if (isPlaylist) {
          playlist.push_back(command);
          Console.print("Song: ");
          Console.println(song);
        } else {
          Console.println(song);

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
    Bridge.put("playlist", "");
    if (isPlaylist) {
      onTrackFinish();
    }
  }

}
