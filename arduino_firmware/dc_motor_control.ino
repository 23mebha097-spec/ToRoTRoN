/**
 * ToRoTRoN Basic DC Motor Control (using L298N Driver)
 * This sketch will make a DC motor rotate for 2 seconds and then stop.
 *
 * Hardware Connection (L298N Driver):
 * - ENA (Enable A): Digital Pin 9 (PWM)
 * - IN1: Digital Pin 8
 * - IN2: Digital Pin 7
 * - Connect motor to Out1 and Out2
 */

// Motor A connections
int enA = 9;
int in1 = 8;
int in2 = 7;

void setup() {
  // Set all the motor control pins to outputs
  pinMode(enA, OUTPUT);
  pinMode(in1, OUTPUT);
  pinMode(in2, OUTPUT);

  Serial.begin(9600);
  Serial.println("DC Motor initialization complete.");
}

void loop() {
  Serial.println("Motor Rotating Clockwise...");
  // Turn on motor clockwise
  digitalWrite(in1, HIGH);
  digitalWrite(in2, LOW);
  analogWrite(enA, 200); // Speed 0-255
  delay(2000);

  Serial.println("Motor Stopping...");
  // Stop motor
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
  delay(1000);

  Serial.println("Motor Rotating Counter-Clockwise...");
  // Turn on motor counter-clockwise
  digitalWrite(in1, LOW);
  digitalWrite(in2, HIGH);
  analogWrite(enA, 200);
  delay(2000);

  Serial.println("Motor Stopping...");
  // Stop motor
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
  delay(1000);
}
