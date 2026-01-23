/*
 * ToRoTRoN ESP32 Firmware
 * Controls robotic joints via Serial Protocol: "joint_id:angle:speed\n"
 * 
 * Target Board: ESP32
 * Library Needed: ESP32Servo
 */

#include <ESP32Servo.h>

// PIN CONFIGURATION
const int J1_PIN = 18;

// SERVO OBJECTS
Servo joint1;

// SERIAL COMMUNICATION
const long BAUD_RATE = 115200;
String inputString = "";
bool stringComplete = false;

void setup() {
  // Initialize Serial
  Serial.begin(BAUD_RATE);
  inputString.reserve(200);
  
  // Attach Servos
  joint1.attach(J1_PIN, 500, 2400); // Standard PWM range for 180 or 270 degree servos
  
  // Set Initial Position (Center)
  joint1.write(90);
  
  Serial.println("ToRoTRoN ESP32 Hardware Online.");
  Serial.println("System Ready. Waiting for commands...");
}

void loop() {
  // Process serial string when a newline is received
  if (stringComplete) {
    parseCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

/*
 * SERIAL EVENT (Interrupt-like behavior)
 */
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}

/*
 * COMMAND PARSER
 * Protocol: "joint_id:angle:speed\n"
 * Example: "J1:45.00:10.00"
 */
void parseCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  int firstColon = cmd.indexOf(':');
  int lastColon = cmd.lastIndexOf(':');

  if (firstColon != -1 && lastColon != -1 && firstColon != lastColon) {
    String id = cmd.substring(0, firstColon);
    float angle = cmd.substring(firstColon + 1, lastColon).toFloat();
    float speed = cmd.substring(lastColon + 1).toFloat();

    // Map to Hardware
    if (id.equalsIgnoreCase("J1") || id.equalsIgnoreCase("Shoulder")) {
      moveJoint(joint1, angle, speed);
      Serial.print("Success: J1 moved to ");
      Serial.println(angle);
    } 
    else {
      Serial.print("Error: Unknown Joint ID: ");
      Serial.println(id);
    }
  } else {
    Serial.println("Error: Invalid Command Format. Use 'id:angle:speed'");
  }
}

/*
 * JOINT MOTION EXECUTION
 * Handles basic angle mapping and ensures reasonable constraints.
 */
void moveJoint(Servo &s, float angle, float speed) {
  // Assuming 'angle' from software is in degrees (e.g., -90 to 90 or 0 to 180)
  // Most Servo libraries use 0-180. 
  // If your design uses offset 0, you might need: int servoAngle = (int)angle + 90;
  
  int servoAngle = (int)angle;
  
  // Constraint check
  if (servoAngle < 0) servoAngle = 0;
  if (servoAngle > 180) servoAngle = 180;

  // Simple direct write. 
  // Advanced speed control can be implemented by interpolating steps with speed delay.
  s.write(servoAngle);
}
