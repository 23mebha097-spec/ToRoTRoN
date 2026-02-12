/*
 * ToRoTRoN FINAL ESP32 FIRMWARE
 * ----------------------------
 * This code is optimized for the "j1" joint on Pin 18.
 * It will interpret ANY joint command it receives as a command for the motor on
 * Pin 18.
 *
 * BOARD: ESP32 Dev Module
 * PIN: Servo Signal on Pin 18
 * LIBRARY: Install "ESP32Servo" by Kevin Harrington
 */

#include <ESP32Servo.h>

const int J1_PIN = 18;
const long BAUD = 115200;

Servo myServo;

void setup() {
  Serial.begin(BAUD);

  // ESP32 Servo setup
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  myServo.setPeriodHertz(50);
  myServo.attach(J1_PIN, 500, 2400);

  Serial.println("\n[SYSTEM] ESP32 Online - ToRoTRoN Interface");

  // STARTUP DIAGNOSTIC: Wiggle back and forth to prove power is okay
  myServo.write(20);
  delay(500);
  myServo.write(160);
  delay(500);
  myServo.write(90);
  delay(500);

  Serial.println("[SYSTEM] Wiggle test complete. Ready for Serial.");
}

void loop() {
  if (Serial.available() > 0) {
    // Read the incoming line
    String data = Serial.readStringUntil('\n');
    data.trim();

    // Command format: "id:angle:speed"
    // We only care about the middle value (angle) for our single servo.

    int firstColon = data.indexOf(':');
    int lastColon = data.lastIndexOf(':');

    if (firstColon != -1 && lastColon != -1) {
      String angleStr = data.substring(firstColon + 1, lastColon);
      float targetAngle = angleStr.toFloat();

      // Safety limits
      int angle = (int)targetAngle;
      if (angle < 0)
        angle = 0;
      if (angle > 180)
        angle = 180;

      myServo.write(angle);

      // Confirm back to PC
      Serial.print("ROBOT_ACK: Moving to ");
      Serial.println(angle);
    }
  }
}
