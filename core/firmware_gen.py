def generate_esp32_firmware(robot, default_speed=50):
    """
    Generates a compilable Arduino (.ino) string for ESP32,
    supporting non-blocking smoothed movement for multiple joints.
    """
    AVAILABLE_PINS = [18, 19, 21, 22, 23, 25, 26, 27, 32, 33]
    
    joints = robot.joints
    joint_names = list(joints.keys())
    
    code = []
    code.append("/**")
    code.append(" * ToRoTRoN Advanced ESP32 Firmware")
    code.append(" * Features: Non-blocking smoothed multi-joint movement")
    code.append(" * Protocol: \"joint_name:angle:speed\\n\"")
    code.append(" */\n")
    code.append("#include <ESP32Servo.h>\n")
    
    code.append("// --- ROBOT CONFIGURATION ---")
    code.append(f"#define NUM_JOINTS {len(joint_names)}")
    code.append("")
    
    code.append("struct JointControl {")
    code.append("  Servo servo;")
    code.append("  String name;")
    code.append("  float current;")
    code.append("  float target;")
    code.append("  float speed;")
    code.append("  int pin;")
    code.append("};")
    code.append("")
    
    code.append("JointControl joints[NUM_JOINTS];\n")
    
    code.append("void setup() {")
    code.append("  Serial.begin(115200);")
    code.append("  delay(500);")
    code.append("")
    code.append("  // Allocate timers for ESP32Servo")
    code.append("  ESP32PWM::allocateTimer(0);")
    code.append("  ESP32PWM::allocateTimer(1);")
    code.append("  ESP32PWM::allocateTimer(2);")
    code.append("  ESP32PWM::allocateTimer(3);")
    code.append("")
    
    for i, name in enumerate(joint_names):
        pin = AVAILABLE_PINS[i] if i < len(AVAILABLE_PINS) else -1
        code.append(f"  // Initialize {name}")
        code.append(f"  joints[{i}].name = \"{name}\";")
        code.append(f"  joints[{i}].current = 90.0;")
        code.append(f"  joints[{i}].target = 90.0;")
        code.append(f"  joints[{i}].speed = 0.0;")
        code.append(f"  joints[{i}].pin = {pin};")
        if pin != -1:
            code.append(f"  joints[{i}].servo.setPeriodHertz(50);")
            code.append(f"  joints[{i}].servo.attach(joints[{i}].pin, 500, 2400);")
            code.append(f"  joints[{i}].servo.write(90);")
    
    code.append("")
    code.append("  Serial.println(\"\\n--- ToRoTRoN HARDWARE ONLINE ---\");")
    code.append("}\n")
    
    code.append("void loop() {")
    code.append("  updateSerial();")
    code.append("  updateServos();")
    code.append("  delay(15);")
    code.append("}\n")
    
    code.append("void updateSerial() {")
    code.append("  if (Serial.available() > 0) {")
    code.append("    String cmd = Serial.readStringUntil('\\n');")
    code.append("    cmd.trim();")
    code.append("    if (cmd.length() > 0) parseCommand(cmd);")
    code.append("  }")
    code.append("}\n")
    
    code.append("void parseCommand(String cmd) {")
    code.append("  int first = cmd.indexOf(':');")
    code.append("  int last = cmd.lastIndexOf(':');")
    code.append("  if (first == -1 || last == -1) return;")
    code.append("")
    code.append("  String id = cmd.substring(0, first);")
    code.append("  float target = cmd.substring(first + 1, last).toFloat();")
    code.append("  float speed = cmd.substring(last + 1).toFloat();")
    code.append("")
    code.append("  // Map angle to servo limits (0-180)")
    code.append("  target = constrain(target + 90.0, 0, 180);")
    code.append("")
    code.append("  for (int i = 0; i < NUM_JOINTS; i++) {")
    code.append("    if (joints[i].name.equalsIgnoreCase(id)) {")
    code.append("      joints[i].target = target;")
    code.append("      joints[i].speed = speed;")
    code.append("      Serial.print(\"ACK: \"); Serial.print(id); ")
    code.append("      Serial.print(\" T:\"); Serial.println(target);")
    code.append("      break;")
    code.append("    }")
    code.append("  }")
    code.append("}\n")
    
    code.append("void updateServos() {")
    code.append("  for (int i = 0; i < NUM_JOINTS; i++) {")
    code.append("    if (joints[i].pin == -1) continue;")
    code.append("")
    code.append("    if (abs(joints[i].current - joints[i].target) < 0.2) {")
    code.append("      joints[i].current = joints[i].target;")
    code.append("    } else {")
    code.append("      float step = (joints[i].speed / 100.0) * 2.0;")
    code.append("      if (step < 0.1) step = 0.5;")
    code.append("")
    code.append("      if (joints[i].current < joints[i].target) joints[i].current += step;")
    code.append("      else joints[i].current -= step;")
    code.append("    }")
    code.append("    joints[i].servo.write((int)joints[i].current);")
    code.append("  }")
    code.append("}\n")
    
    return "\n".join(code)

