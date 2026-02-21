/**
 * ToRoTRoN Advanced ESP32 Firmware
 * Features: Non-blocking smoothed multi-joint movement
 * Protocol: "joint_name:angle:speed\n"
 */

#include <ESP32Servo.h>

// --- ROBOT CONFIGURATION ---
#define NUM_JOINTS 1

struct JointControl {
  Servo servo;
  String name;
  float current;
  float target;
  float speed;
  int pin;
};

JointControl joints[NUM_JOINTS];

void setup() {
  Serial.begin(115200);
  delay(500);

  // Allocate timers for ESP32Servo
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);

  // Initialize j1
  joints[0].name = "j1";
  joints[0].current = 90.0;
  joints[0].target = 90.0;
  joints[0].speed = 0.0;
  joints[0].pin = 18;
  joints[0].servo.setPeriodHertz(50);
  joints[0].servo.attach(joints[0].pin, 500, 2400);
  joints[0].servo.write(90);

  Serial.println("\n--- ToRoTRoN HARDWARE ONLINE ---");
  performHandshake();
}

void performHandshake() {
  Serial.println("HANDSHAKE: Moving all pins 0-30-0...");
  // Move all to 120 (mid + 30)
  for (int i = 0; i < NUM_JOINTS; i++) {
    if (joints[i].pin != -1) joints[i].target = 120.0;
    joints[i].speed = 50.0;
  }
  
  // Wait and move back to 90 (mid)
  for(int k=0; k<100; k++) { updateServos(); delay(15); }
  for (int i = 0; i < NUM_JOINTS; i++) {
    if (joints[i].pin != -1) joints[i].target = 90.0;
  }
  for(int k=0; k<100; k++) { updateServos(); delay(15); }
  Serial.println("HANDSHAKE: Ready.");
}

void loop() {
  updateSerial();
  updateServos();
  delay(15);
}

void updateSerial() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "?") { Serial.println("PONG"); return; }
    if (cmd.length() > 0) parseCommand(cmd);
  }
}

void parseCommand(String cmd) {
  int first = cmd.indexOf(':');
  int last = cmd.lastIndexOf(':');
  if (first == -1 || last == -1) return;

  String id = cmd.substring(0, first);
  float target = cmd.substring(first + 1, last).toFloat();
  float speed = cmd.substring(last + 1).toFloat();

  // Map angle to servo limits (0-180)
  target = constrain(target + 90.0, 0, 180);

  for (int i = 0; i < NUM_JOINTS; i++) {
    if (joints[i].name.equalsIgnoreCase(id)) {
      joints[i].target = target;
      joints[i].speed = speed;
      Serial.print("ACK: "); Serial.print(id); 
      Serial.print(" T:"); Serial.println(target);
      break;
    }
  }
}

void updateServos() {
  for (int i = 0; i < NUM_JOINTS; i++) {
    if (joints[i].pin == -1) continue;

    if (abs(joints[i].current - joints[i].target) < 0.2) {
      joints[i].current = joints[i].target;
    } else {
      float step = (joints[i].speed / 100.0) * 2.0;
      if (step < 0.1) step = 0.5;

      if (joints[i].current < joints[i].target) joints[i].current += step;
      else joints[i].current -= step;
    }
    joints[i].servo.write((int)joints[i].current);
  }
}
