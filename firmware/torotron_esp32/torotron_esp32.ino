/**
 * ToRoTRoN — ESP32-S3 Robot Firmware (Enhanced)
 * Auto-generated with Gear Ratio & Servo Mode support
 */

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
  #error "Target MCU must be ESP32-S3"
#endif

#include <ESP32Servo.h>

#define CONTROL_PERIOD_MS  8
#define SERIAL_LINE_BUF    96

struct ServoJoint {
  Servo  servo;
  const char* name;
  float  current_deg;
  float  target_deg;
  float  speed_pct;
  int    pin;
  bool   is_continuous;
  float  min_limit;
  float  max_limit;
  int    last_write_val;
};
ServoJoint sJoints[6];

char serialLine[SERIAL_LINE_BUF];
uint8_t serialLinePos = 0;
unsigned long lastControlTick = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("ToRoTRoN Online");

  ESP32PWM::allocateTimer(0); ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2); ESP32PWM::allocateTimer(3);
  // Servo [0]: joint_01_02 (Continuous)
  sJoints[0].name = "joint_01_02";
  sJoints[0].pin = 4;
  sJoints[0].is_continuous = true;
  sJoints[0].current_deg = 0.0f;
  sJoints[0].target_deg = 0.0f;
  sJoints[0].speed_pct = 50.0f;
  sJoints[0].min_limit = -180.0f;
  sJoints[0].max_limit = 180.0f;
  sJoints[0].last_write_val = -999;
  sJoints[0].servo.setPeriodHertz(50);
  sJoints[0].servo.attach(4, 500, 2400);
  sJoints[0].servo.write(90); // Neutral / Home

  // Servo [1]: joint_02_03 (Continuous)
  sJoints[1].name = "joint_02_03";
  sJoints[1].pin = 5;
  sJoints[1].is_continuous = true;
  sJoints[1].current_deg = 0.0f;
  sJoints[1].target_deg = 0.0f;
  sJoints[1].speed_pct = 50.0f;
  sJoints[1].min_limit = -90.0f;
  sJoints[1].max_limit = 90.0f;
  sJoints[1].last_write_val = -999;
  sJoints[1].servo.setPeriodHertz(50);
  sJoints[1].servo.attach(5, 500, 2400);
  sJoints[1].servo.write(90); // Neutral / Home

  // Servo [2]: joint_03_04 (Continuous)
  sJoints[2].name = "joint_03_04";
  sJoints[2].pin = 6;
  sJoints[2].is_continuous = true;
  sJoints[2].current_deg = 0.0f;
  sJoints[2].target_deg = 0.0f;
  sJoints[2].speed_pct = 50.0f;
  sJoints[2].min_limit = -90.0f;
  sJoints[2].max_limit = 90.0f;
  sJoints[2].last_write_val = -999;
  sJoints[2].servo.setPeriodHertz(50);
  sJoints[2].servo.attach(6, 500, 2400);
  sJoints[2].servo.write(90); // Neutral / Home

  // Servo [3]: joint_04_05 (Standard (0-180))
  sJoints[3].name = "joint_04_05";
  sJoints[3].pin = 7;
  sJoints[3].is_continuous = false;
  sJoints[3].current_deg = 0.0f;
  sJoints[3].target_deg = 0.0f;
  sJoints[3].speed_pct = 50.0f;
  sJoints[3].min_limit = -90.0f;
  sJoints[3].max_limit = 90.0f;
  sJoints[3].last_write_val = -999;
  sJoints[3].servo.setPeriodHertz(50);
  sJoints[3].servo.attach(7, 500, 2400);
  sJoints[3].servo.write(90); // Neutral / Home

  // Servo [4]: joint_05_06 (Standard (0-180))
  sJoints[4].name = "joint_05_06";
  sJoints[4].pin = 8;
  sJoints[4].is_continuous = false;
  sJoints[4].current_deg = 0.0f;
  sJoints[4].target_deg = 0.0f;
  sJoints[4].speed_pct = 50.0f;
  sJoints[4].min_limit = -180.0f;
  sJoints[4].max_limit = 180.0f;
  sJoints[4].last_write_val = -999;
  sJoints[4].servo.setPeriodHertz(50);
  sJoints[4].servo.attach(8, 500, 2400);
  sJoints[4].servo.write(90); // Neutral / Home

  // Servo [5]: joint_06_07 (Standard (0-180))
  sJoints[5].name = "joint_06_07";
  sJoints[5].pin = 9;
  sJoints[5].is_continuous = false;
  sJoints[5].current_deg = 0.0f;
  sJoints[5].target_deg = 0.0f;
  sJoints[5].speed_pct = 50.0f;
  sJoints[5].min_limit = 0.0f;
  sJoints[5].max_limit = 45.0f;
  sJoints[5].last_write_val = -999;
  sJoints[5].servo.setPeriodHertz(50);
  sJoints[5].servo.attach(9, 500, 2400);
  sJoints[5].servo.write(90); // Neutral / Home

  Serial.println("READY");
}

void loop() {
  updateSerial();
  unsigned long now = millis();
  if (now - lastControlTick >= CONTROL_PERIOD_MS) {
    lastControlTick = now;
    updateServos();
  }
}

void updateSerial() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      serialLine[serialLinePos] = '\0';
      parseCommand(String(serialLine));
      serialLinePos = 0;
    } else if (serialLinePos < SERIAL_LINE_BUF - 1) {
      serialLine[serialLinePos++] = ch;
    }
  }
}

void parseCommand(String cmd) {
  cmd.trim(); if(cmd.length() == 0) return;
  if (cmd.equalsIgnoreCase("PING")) {
    Serial.println("PONG");
    return;
  }
  int f = cmd.indexOf(':');
  int l = cmd.lastIndexOf(':');
  if (f < 1 || l <= f) return;
  String name = cmd.substring(0, f);
  float angle = cmd.substring(f + 1, l).toFloat();
  float spd   = cmd.substring(l + 1).toFloat();

  for (int i = 0; i < 6; i++) {
    if (name.equalsIgnoreCase(sJoints[i].name)) {
      sJoints[i].target_deg = constrain(angle, sJoints[i].min_limit, sJoints[i].max_limit);
      sJoints[i].speed_pct = spd;
      Serial.print("💡 [HW] Pin ");
      Serial.print(sJoints[i].pin);
      Serial.print(" -> Angle: ");
      Serial.println(sJoints[i].target_deg);
      return;
    }
  }
  Serial.print("⚠️ [HW] Unrecognized or unmatched command: ");
  Serial.println(cmd);
}

void updateServos() {
  for (int i = 0; i < 6; i++) {
    if (sJoints[i].pin == -1) continue;
    int sVal = -999;
    if (sJoints[i].is_continuous) {
      // Continuous: target_deg maps to speed (-90 to 90 range ideally)
      // Map software degrees directly where 0 is stop, -90 is full reverse, 90 is full forward
      sVal = (int)constrain(sJoints[i].target_deg + 90, 0, 180);
    } else {
      // Standard: interpolate then move
      float err = sJoints[i].target_deg - sJoints[i].current_deg;
      if (fabs(err) < 0.1f) sJoints[i].current_deg = sJoints[i].target_deg;
      else {
        float step = (sJoints[i].speed_pct / 100.0f) * 4.0f;
        sJoints[i].current_deg += (err > 0 ? 1 : -1) * max(0.1f, step);
        if ((err > 0 && sJoints[i].current_deg > sJoints[i].target_deg) ||
            (err < 0 && sJoints[i].current_deg < sJoints[i].target_deg))
          sJoints[i].current_deg = sJoints[i].target_deg;
      }
      sVal = (int)constrain(sJoints[i].current_deg + 90, 0, 180);
    }
    if (sVal != sJoints[i].last_write_val) {
      sJoints[i].servo.write(sVal);
      sJoints[i].last_write_val = sVal;
    }
  }
}