/*
 * ToRoTRoN Auto-Generated ESP32 Firmware
 * Protocol: "joint_id:angle:speed\n"
 */

#include <ESP32Servo.h>

// --- PIN CONFIGURATION ---
const int PIN_J1 = 18;

Servo servo_j1;

void setup() {
  Serial.begin(115200);
  delay(500);

  // Allocate timers (ESP32 requirement)
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);

  servo_j1.setPeriodHertz(50);
  servo_j1.attach(PIN_J1, 500, 2400);

  Serial.println("\n--- ToRoTRoN HARDWARE READY ---");
  Serial.println("Testing j1...");
  servo_j1.write(90);
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      parseCommand(cmd);
    }
  }
}

void parseCommand(String cmd) {
  int first = cmd.indexOf(':');
  int last = cmd.lastIndexOf(':');

  if (first != -1 && last != -1) {
    String id = cmd.substring(0, first);
    float angle = cmd.substring(first + 1, last).toFloat();

    // Handle Safety Bounds
    int target = (int)angle;
    if (target < 0) target = 0;
    if (target > 180) target = 180;

    if (id.equalsIgnoreCase("j1")) {
      servo_j1.write(target);
      Serial.print("ROBOT_ACK: j1 moved to ");
      Serial.println(target);
    }
  }
}