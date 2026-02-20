def generate_esp32_firmware(robot, default_speed=50):
    """
    Generates a compilable Arduino (.ino) string for ESP32,
    automatically mapping robot joints to specific GPIO pins.
    """
    AVAILABLE_PINS = [18, 19, 21, 22, 23, 25, 26, 27, 32, 33]
    
    joints = robot.joints
    joint_names = list(joints.keys())
    
    code = []
    code.append("/*")
    code.append(" * ToRoTRoN Auto-Generated ESP32 Firmware")
    code.append(" * Protocol: \"joint_id:angle:speed\\n\"")
    code.append(f" * Generated for Global Speed: {default_speed}%")
    code.append(" */\n")
    code.append("#include <ESP32Servo.h>\n")
    
    code.append("// --- PIN CONFIGURATION ---")
    for i, name in enumerate(joint_names):
        if i < len(AVAILABLE_PINS):
            pin = AVAILABLE_PINS[i]
            code.append(f"const int PIN_{name.upper()} = {pin};")
    code.append("")
    
    for name in joint_names:
        code.append(f"Servo servo_{name};")
        code.append(f"float current_angle_{name} = 90.0;")
    code.append("")
    
    code.append("void setup() {")
    code.append("  Serial.begin(115200);")
    code.append("  delay(500);")
    code.append("")
    code.append("  ESP32PWM::allocateTimer(0);")
    code.append("  ESP32PWM::allocateTimer(1);")
    code.append("  ESP32PWM::allocateTimer(2);")
    code.append("  ESP32PWM::allocateTimer(3);")
    code.append("")
    
    for name in joint_names:
        code.append(f"  servo_{name}.setPeriodHertz(50);")
        code.append(f"  servo_{name}.attach(PIN_{name.upper()}, 500, 2400);")
        code.append(f"  servo_{name}.write(90);") # Default to middle
    
    code.append("")
    code.append("  Serial.println(\"\\n--- ToRoTRoN HARDWARE READY ---\");")
    code.append("}\n")
    
    code.append("void loop() {")
    code.append("  if (Serial.available() > 0) {")
    code.append("    String cmd = Serial.readStringUntil('\\n');")
    code.append("    cmd.trim();")
    code.append("    if (cmd.length() > 0) {")
    code.append("      parseCommand(cmd);")
    code.append("    }")
    code.append("  }")
    code.append("}\n")

    code.append("void slowMove(Servo &s, float &current, float target, float speed) {")
    code.append("  if (speed <= 0) { s.write((int)target); current = target; return; }")
    code.append("  float step = (speed / 100.0) * 2.0; // Scale speed to increment")
    code.append("  if (step < 0.1) step = 0.5;")
    code.append("")
    code.append("  if (current < target) {")
    code.append("    while (current < target) {")
    code.append("      current += step;")
    code.append("      if (current > target) current = target;")
    code.append("      s.write((int)current);")
    code.append("      delay(15);")
    code.append("    }")
    code.append("  } else {")
    code.append("    while (current > target) {")
    code.append("      current -= step;")
    code.append("      if (current < target) current = target;")
    code.append("      s.write((int)current);")
    code.append("      delay(15);")
    code.append("    }")
    code.append("  }")
    code.append("}\n")
    
    code.append("void parseCommand(String cmd) {")
    code.append("  int first = cmd.indexOf(':');")
    code.append("  int last = cmd.lastIndexOf(':');")
    code.append("")
    code.append("  if (first != -1 && last != -1) {")
    code.append("    String id = cmd.substring(0, first);")
    code.append("    float angle = cmd.substring(first + 1, last).toFloat();")
    code.append("    float speed = cmd.substring(last + 1).toFloat();")
    code.append("")
    code.append("    float target = angle;")
    code.append("    if (target < 0) target = 0;")
    code.append("    if (target > 180) target = 180;")
    code.append("")
    
    for i, name in enumerate(joint_names):
        prefix = "} else " if i > 0 else ""
        code.append(f"    {prefix}if (id.equalsIgnoreCase(\"{name}\")) {{")
        code.append(f"      slowMove(servo_{name}, current_angle_{name}, target, speed);")
        code.append(f"      Serial.print(\"ROBOT_ACK: {name} moved to \");")
        code.append("      Serial.println(target);")
    
    code.append("    }")
    code.append("  }")
    code.append("}")
    
    return "\n".join(code)

