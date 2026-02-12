#include <Servo.h>

/**
 * ToRoTRoN MG995 Servo Control
 *
 * Hardware Connection for MG995:
 * - Signal (Orange/Yellow): Digital Pin 9
 * - VCC (Red): 5V (Note: MG995 draws high current, use external 5V-6V supply if
 * it jitters)
 * - GND (Brown): GND
 *
 * Instructions:
 * 1. Upload this code.
 * 2. Open Serial Monitor (Ctrl+Shift+M) at 9600 baud.
 * 3. Type a number (0-180) and press Enter to move the motor.
 */

Servo mg995;

void setup() {
  mg995.attach(9); // Signal pin on Digital 9
  Serial.begin(9600);
  Serial.println("MG995 Servo Ready!");
  Serial.println("Enter angle (0-180) to rotate motor:");
}

void loop() {
  if (Serial.available() > 0) {
    int angle = Serial.parseInt(); // Read number from Serial Monitor

    if (angle >= 0 && angle <= 180) {
      Serial.print("Rotating to: ");
      Serial.println(angle);
      mg995.write(angle);
    }
  }
}
