def generate_esp32_firmware(robot, default_speed=50, motor_assignments=None):
    """
    Generates a compilable Arduino (.ino) string for ESP32-S3.

    Improvements:
      - Supports Stepper Gear Ratios (e.g. 1:3)
      - Supports Servo Modes (Standard 0-180 vs Continuous)
      - All inputs in degrees are converted to motor units (steps/pulse) automatically.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # ESP32-S3 Safe GPIO Pool
    # ─────────────────────────────────────────────────────────────────────────
    _GPIO_POOL = [
        4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
        21,
        38, 43, 44, 47, 48,
        1, 2,
        39, 40, 41, 42,
    ]

    # Stepper Base Constants (NEMA17 typical)
    STEPS_PER_REV   = 200
    MICROSTEP        = 16
    BASE_STEPS_PER_DEG = (STEPS_PER_REV * MICROSTEP) / 360.0  # ~8.8889
    MAX_SPEED_SPS   = 3200
    ACCEL_SPS2      = 1600

    slave_ids = set()
    for slaves in robot.joint_relations.values():
        for s_id, _ in slaves:
            slave_ids.add(s_id)

    joint_names = [n for n in robot.joints if n not in slave_ids]

    if motor_assignments is None:
        motor_assignments = {}

    _available = list(_GPIO_POOL)
    _used       = set()

    def _alloc_pin():
        for pin in _available:
            if pin not in _used:
                _used.add(pin)
                return pin
        return -1

    servo_joints   = []   # [(name, joint_obj, pwm_pin, mode)]
    stepper_joints = []   # [(name, joint_obj, step_pin, dir_pin, en_pin, ratio)]

    for name in joint_names:
        jobj = robot.joints[name]
        data = motor_assignments.get(name, {"type": "servo"})
        # Support legacy string format if any
        if isinstance(data, str): data = {"type": data}
        
        mtype = data.get("type", "servo").lower()

        if mtype == "stepper":
            step = _alloc_pin()
            dr   = _alloc_pin()
            en   = _alloc_pin()
            ratio = float(data.get("gear_ratio", 1.0))
            stepper_joints.append((name, jobj, step, dr, en, ratio))
        else:
            pwm = _alloc_pin()
            mode = data.get("servo_mode", "Standard (0-180)")
            servo_joints.append((name, jobj, pwm, mode))

    num_servo    = len(servo_joints)
    num_stepper  = len(stepper_joints)
    need_servo   = num_servo > 0
    need_stepper = num_stepper > 0

    c = []
    c.append("/**")
    c.append(" * ToRoTRoN — ESP32-S3 Robot Firmware (Enhanced)")
    c.append(" * Auto-generated with Gear Ratio & Servo Mode support")
    c.append(" */")
    c.append("")

    c.append("#if !defined(CONFIG_IDF_TARGET_ESP32S3)")
    c.append("  #error \"Target MCU must be ESP32-S3\"")
    c.append("#endif")
    c.append("")

    if need_servo:   c.append("#include <ESP32Servo.h>")
    if need_stepper: c.append("#include <AccelStepper.h>")
    c.append("")

    c.append("#define CONTROL_PERIOD_MS  8")
    c.append("#define SERIAL_LINE_BUF    96")
    c.append("")

    # --- STRUCTS ---
    if need_servo:
        c.append("struct ServoJoint {")
        c.append("  Servo  servo;")
        c.append("  const char* name;")
        c.append("  float  current_deg;")
        c.append("  float  target_deg;")
        c.append("  float  speed_pct;")
        c.append("  int    pin;")
        c.append("  bool   is_continuous;")
        c.append("  float  min_limit;")
        c.append("  float  max_limit;")
        c.append("  int    last_write_val;")
        c.append("};")
        c.append(f"ServoJoint sJoints[{num_servo}];")
        c.append("")

    if need_stepper:
        c.append("struct StepperJoint {")
        c.append("  AccelStepper stepper;")
        c.append("  const char*  name;")
        c.append("  float        target_deg;")
        c.append("  float        speed_pct;")
        c.append("  float        steps_per_deg; // Includes Gear Ratio")
        c.append("  float        min_limit;")
        c.append("  float        max_limit;")
        c.append("};")
        c.append(f"AccelStepper _rawSteppers[{num_stepper}] = {{")
        for i, (name, jobj, step, dr, en, ratio) in enumerate(stepper_joints):
            comma = "," if i < num_stepper - 1 else ""
            c.append(f"  AccelStepper(AccelStepper::DRIVER, {step}, {dr}){comma}")
        c.append("};")
        c.append(f"StepperJoint stJoints[{num_stepper}];")
        c.append(f"#define MAX_SPEED_BASE {MAX_SPEED_SPS}.0f")
        c.append(f"#define ACCEL_BASE     {ACCEL_SPS2}.0f")
        c.append("")

    c.append("char serialLine[SERIAL_LINE_BUF];")
    c.append("uint8_t serialLinePos = 0;")
    c.append("unsigned long lastControlTick = 0;")
    c.append("")

    # --- SETUP ---
    c.append("void setup() {")
    c.append("  Serial.begin(115200);")
    c.append("  delay(500);")
    c.append("  Serial.println(\"ToRoTRoN Online\");")
    c.append("")
    if need_servo:
        c.append("  ESP32PWM::allocateTimer(0); ESP32PWM::allocateTimer(1);")
        c.append("  ESP32PWM::allocateTimer(2); ESP32PWM::allocateTimer(3);")

    # Init Servo Joints
    for i, (name, jobj, pwm, mode) in enumerate(servo_joints):
        is_cont = "true" if "Continuous" in mode else "false"
        mn, mx = jobj.min_limit, jobj.max_limit
        c.append(f"  // Servo [{i}]: {name} ({mode})")
        c.append(f"  sJoints[{i}].name = \"{name}\";")
        c.append(f"  sJoints[{i}].pin = {pwm};")
        c.append(f"  sJoints[{i}].is_continuous = {is_cont};")
        c.append(f"  sJoints[{i}].current_deg = 0.0f;")
        c.append(f"  sJoints[{i}].target_deg = 0.0f;")
        c.append(f"  sJoints[{i}].speed_pct = {default_speed}.0f;")
        c.append(f"  sJoints[{i}].min_limit = {mn}f;")
        c.append(f"  sJoints[{i}].max_limit = {mx}f;")
        c.append(f"  sJoints[{i}].last_write_val = -999;")
        if pwm != -1:
            c.append(f"  sJoints[{i}].servo.setPeriodHertz(50);")
            c.append(f"  sJoints[{i}].servo.attach({pwm}, 500, 2400);")
            c.append(f"  sJoints[{i}].servo.write(90); // Neutral / Home")
        c.append("")

    # Init Stepper Joints
    for i, (name, jobj, step, dr, en, ratio) in enumerate(stepper_joints):
        mn, mx = jobj.min_limit, jobj.max_limit
        spd_deg = round(BASE_STEPS_PER_DEG * ratio, 6)
        c.append(f"  // Stepper [{i}]: {name} (Gear Ratio 1:{ratio})")
        c.append(f"  stJoints[{i}].name = \"{name}\";")
        c.append(f"  stJoints[{i}].steps_per_deg = {spd_deg}f;")
        c.append(f"  stJoints[{i}].target_deg = 0.0f;")
        c.append(f"  stJoints[{i}].speed_pct = {default_speed}.0f;")
        c.append(f"  stJoints[{i}].min_limit = {mn}f;")
        c.append(f"  stJoints[{i}].max_limit = {mx}f;")
        c.append(f"  stJoints[{i}].stepper = _rawSteppers[{i}];")
        if en != -1:
            c.append(f"  pinMode({en}, OUTPUT);")
            c.append(f"  digitalWrite({en}, LOW); // Enable driver")
        c.append(f"  stJoints[{i}].stepper.setMaxSpeed(MAX_SPEED_BASE);")
        c.append(f"  stJoints[{i}].stepper.setAcceleration(ACCEL_BASE);")
        c.append(f"  stJoints[{i}].stepper.setCurrentPosition(0);")
        c.append("")

    c.append("  Serial.println(\"READY\");")
    c.append("}")
    c.append("")

    # --- LOOP ---
    c.append("void loop() {")
    c.append("  updateSerial();")
    if need_stepper:
        c.append(f"  for(int i=0; i<{num_stepper}; i++) stJoints[i].stepper.run();")
    if need_servo:
        c.append("  unsigned long now = millis();")
        c.append("  if (now - lastControlTick >= CONTROL_PERIOD_MS) {")
        c.append("    lastControlTick = now;")
        c.append("    updateServos();")
        c.append("  }")
    c.append("}")
    c.append("")

    # --- SERIAL ---
    c.append("void updateSerial() {")
    c.append("  while (Serial.available() > 0) {")
    c.append("    char ch = (char)Serial.read();")
    c.append("    if (ch == '\\n') {")
    c.append("      serialLine[serialLinePos] = '\\0';")
    c.append("      parseCommand(String(serialLine));")
    c.append("      serialLinePos = 0;")
    c.append("    } else if (serialLinePos < SERIAL_LINE_BUF - 1) {")
    c.append("      serialLine[serialLinePos++] = ch;")
    c.append("    }")
    c.append("  }")
    c.append("}")
    c.append("")

    c.append("void parseCommand(String cmd) {")
    c.append("  cmd.trim(); if(cmd.length() == 0) return;")
    c.append("  if (cmd.equalsIgnoreCase(\"PING\")) {")
    c.append("    Serial.println(\"PONG\");")
    c.append("    return;")
    c.append("  }")
    c.append("  int f = cmd.indexOf(':');")
    c.append("  int l = cmd.lastIndexOf(':');")
    c.append("  if (f < 1 || l <= f) return;")
    c.append("  String name = cmd.substring(0, f);")
    c.append("  float angle = cmd.substring(f + 1, l).toFloat();")
    c.append("  float spd   = cmd.substring(l + 1).toFloat();")
    c.append("")
    
    if need_servo:
        c.append(f"  for (int i = 0; i < {num_servo}; i++) {{")
        c.append("    if (name.equalsIgnoreCase(sJoints[i].name)) {")
        c.append("      sJoints[i].target_deg = constrain(angle, sJoints[i].min_limit, sJoints[i].max_limit);")
        c.append("      sJoints[i].speed_pct = spd;")
        c.append("      Serial.print(\"💡 [HW] Pin \");")
        c.append("      Serial.print(sJoints[i].pin);")
        c.append("      Serial.print(\" -> Angle: \");")
        c.append("      Serial.println(sJoints[i].target_deg);")
        c.append("      return;")
        c.append("    }")
        c.append("  }")

    if need_stepper:
        c.append(f"  for (int i = 0; i < {num_stepper}; i++) {{")
        c.append("    if (name.equalsIgnoreCase(stJoints[i].name)) {")
        c.append("      stJoints[i].target_deg = constrain(angle, stJoints[i].min_limit, stJoints[i].max_limit);")
        c.append("      stJoints[i].speed_pct = spd;")
        c.append("      float sps = (spd / 100.0f) * MAX_SPEED_BASE;")
        c.append("      stJoints[i].stepper.setMaxSpeed(max(50.0f, sps));")
        c.append("      stJoints[i].stepper.moveTo((long)(stJoints[i].target_deg * stJoints[i].steps_per_deg));")
        c.append("      Serial.print(\"⚙️ [HW] Stepper '\");")
        c.append("      Serial.print(stJoints[i].name);")
        c.append("      Serial.print(\"' -> Steps: \");")
        c.append("      Serial.println(stJoints[i].stepper.targetPosition());")
        c.append("      return;")
        c.append("    }")
        c.append("  }")
        
    c.append("  Serial.print(\"⚠️ [HW] Unrecognized or unmatched command: \");")
    c.append("  Serial.println(cmd);")
    c.append("}")
    c.append("")

    # --- UPDATE SERVOS ---
    if need_servo:
        c.append("void updateServos() {")
        c.append(f"  for (int i = 0; i < {num_servo}; i++) {{")
        c.append("    if (sJoints[i].pin == -1) continue;")
        c.append("    int sVal = -999;")
        c.append("    if (sJoints[i].is_continuous) {")
        c.append("      // Continuous: target_deg maps to speed (-90 to 90 range ideally)")
        c.append("      // Map software degrees directly where 0 is stop, -90 is full reverse, 90 is full forward")
        c.append("      sVal = (int)constrain(sJoints[i].target_deg + 90, 0, 180);")
        c.append("    } else {")
        c.append("      // Standard: interpolate then move")
        c.append("      float err = sJoints[i].target_deg - sJoints[i].current_deg;")
        c.append("      if (fabs(err) < 0.1f) sJoints[i].current_deg = sJoints[i].target_deg;")
        c.append("      else {")
        c.append("        float step = (sJoints[i].speed_pct / 100.0f) * 4.0f;")
        c.append("        sJoints[i].current_deg += (err > 0 ? 1 : -1) * max(0.1f, step);")
        c.append("        if ((err > 0 && sJoints[i].current_deg > sJoints[i].target_deg) ||")
        c.append("            (err < 0 && sJoints[i].current_deg < sJoints[i].target_deg))")
        c.append("          sJoints[i].current_deg = sJoints[i].target_deg;")
        c.append("      }")
        c.append("      sVal = (int)constrain(sJoints[i].current_deg + 90, 0, 180);")
        c.append("    }")
        c.append("    if (sVal != sJoints[i].last_write_val) {")
        c.append("      sJoints[i].servo.write(sVal);")
        c.append("      sJoints[i].last_write_val = sVal;")
        c.append("    }")
        c.append("  }")
        c.append("}")

    return "\n".join(c)
