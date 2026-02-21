/*
 * ToRoTRoN Auto-Generated ESP32 Firmware
 * Protocol: "joint_id:angle:speed\n"
 * Generated for Global Speed: 50%
 */

#include <ESP32Servo.h>

// --- PIN CONFIGURATION ---
const int PIN_J1 = 18;

Servo servo_j1;
float current_angle_j1 = 90.0;

void setup() {
  Serial.begin(115200);
  delay(500);

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);

  servo_j1.setPeriodHertz(50);
  servo_j1.attach(PIN_J1, 500, 2400);
  servo_j1.write(90);

  Serial.println("\n--- ToRoTRoN HARDWARE READY ---");
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

void slowMove(Servo &s, float &current, float target, float speed) {
  if (speed <= 0) { s.write((int)target); current = target; return; }
  float step = (speed / 100.0) * 2.0; // Scale speed to increment
  if (step < 0.1) step = 0.5;

  if (current < target) {
    while (current < target) {
      current += step;
      if (current > target) current = target;
      s.write((int)current);
      delay(15);
    }
  } else {
    while (current > target) {
      current -= step;
      if (current < target) current = target;
      s.write((int)current);
      delay(15);
    }
  }
}

void parseCommand(String cmd) {
  int first = cmd.indexOf(':');
  int last = cmd.lastIndexOf(':');

  if (first != -1 && last != -1) {
    String id = cmd.substring(0, first);
    float angle = cmd.substring(first + 1, last).toFloat();
    float speed = cmd.substring(last + 1).toFloat();

    float target = angle;
    if (target < 0) target = 0;
    if (target > 180) target = 180;

    if (id.equalsIgnoreCase("j1")) {
      slowMove(servo_j1, current_angle_j1, target, speed);
      Serial.print("ROBOT_ACK: j1 moved to ");
      Serial.println(target);
    }
  }
}