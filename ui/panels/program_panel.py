from PyQt5 import QtWidgets, QtCore, QtGui
import time
import os

class ProgramPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.is_running = False
        self.current_lang = "normal" # Default language
        
        # Example templates for each language
        self.templates = {
            "normal": "# Command format: JOINT Name Angle\nJOINT Shoulder 45\nWAIT 1.0\nJOINT Shoulder -45\nWAIT 1.0\n",
            "python": "# Python API: robot.move('Name', Angle)\nrobot.move('Shoulder', 45)\nrobot.wait(1.0)\nrobot.move('Shoulder', -45)\nrobot.wait(1.0)\n",
            "matlab": "% Matlab Syntax: joint('Name', Angle)\njoint('Shoulder', 45);\npause(1.0);\njoint('Shoulder', -45);\npause(1.0);\n"
        }
        
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- TOP TOOLBAR AREA ---
        self.toolbar_layout = QtWidgets.QHBoxLayout()
        
        self.upload_btn = QtWidgets.QPushButton("UPLOAD CODE")
        self.upload_btn.setToolTip("Run code on Hardware (ESP32)")
        self.upload_btn.setStyleSheet("background-color: #1976d2; font-weight: bold; color: black; border-radius: 8px; padding: 5px;")
        self.upload_btn.clicked.connect(self.upload_code)
        self.toolbar_layout.addWidget(self.upload_btn)
        
        self.run_btn = QtWidgets.QPushButton("RUN PROGRAM")
        self.run_btn.setToolTip("Run Simulation Only")
        self.run_btn.setStyleSheet("background-color: #4caf50; font-weight: bold; color: black; border-radius: 8px; padding: 5px;")
        self.run_btn.clicked.connect(self.run_program)
        self.toolbar_layout.addWidget(self.run_btn)
        
        self.stop_btn = QtWidgets.QPushButton("STOP")
        self.stop_btn.setToolTip("Stop execution")
        self.stop_btn.setStyleSheet("background-color: #d32f2f; font-weight: bold; color: black; border-radius: 8px; padding: 5px;")
        self.stop_btn.clicked.connect(self.stop_program)
        self.toolbar_layout.addWidget(self.stop_btn)
        
        self.toolbar_layout.addStretch()
        
        # --- LIVE SYNC OPTION ---
        self.sync_hw_check = QtWidgets.QCheckBox("Live Hardware Sync")
        self.sync_hw_check.setToolTip("If checked, RUN PROGRAM will also move the physical ESP32 motors.")
        self.sync_hw_check.setStyleSheet("color: #1976d2; font-weight: bold;")
        self.toolbar_layout.addWidget(self.sync_hw_check)

        self.hw_status_lbl = QtWidgets.QLabel("● HW Idle")
        self.hw_status_lbl.setStyleSheet("color: #888; margin-left: 10px; font-weight: bold;")
        self.toolbar_layout.addWidget(self.hw_status_lbl)
        
        layout.addLayout(self.toolbar_layout)
        
        # --- EDITOR AREA ---
        layout.addWidget(QtWidgets.QLabel("Program Code:"))
        self.code_edit = QtWidgets.QPlainTextEdit()
        self.code_edit.setPlainText("""# Example Program
JOINT Shoulder 30
WAIT 0.5
JOINT Shoulder -30
WAIT 0.5
""")
        self.code_edit.setFont(QtGui.QFont("Consolas", 10))
        # Give editor stretch factor of 1 so it fills the space
        layout.addWidget(self.code_edit, 1)

        # --- LANGUAGE SELECTION BUTTONS (Bottom) ---
        lang_layout = QtWidgets.QHBoxLayout()
        lang_layout.setSpacing(10)
        
        self.lang_btns = {}
        for lang in ["normal code", "python", "matlab"]:
            btn = QtWidgets.QPushButton(lang)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e0e0e0;
                    color: black;
                    border: 2px solid #333;
                    border-radius: 8px;
                    padding: 10px;
                    font-weight: bold;
                    min-width: 100px;
                }
                QPushButton:checked {
                    background-color: #1976d2;
                    border-color: #1976d2;
                }
                QPushButton:hover {
                    background-color: #1976d2;
                }
            """)
            btn.clicked.connect(lambda checked, l=lang: self.set_language(l))
            lang_layout.addWidget(btn)
            self.lang_btns[lang] = btn
            
        self.lang_btns["normal code"].setChecked(True)
        layout.addLayout(lang_layout)
        layout.addSpacing(10)

    def set_language(self, lang):
        """Switches the editor template and parsing mode."""
        self.current_lang = lang.replace(" code", "")
        
        # Uncheck others
        for name, btn in self.lang_btns.items():
            btn.blockSignals(True)
            btn.setChecked(name == lang)
            btn.blockSignals(False)
            
        # Set template if editor is empty or just has another template
        current_text = self.code_edit.toPlainText().strip()
        is_default = any(current_text == t.strip() for t in self.templates.values())
        if not current_text or is_default:
            self.code_edit.setPlainText(self.templates[self.current_lang])
            
        self.mw.log(f"Language set to: {lang.upper()}")

    def upload_code(self):
        """Hardware Sync execution of the editor's code."""
        if self.is_running: return
        
        code = self.code_edit.toPlainText()
        lines = code.splitlines()
        
        hw_sync = self.mw.serial_mgr.is_connected if hasattr(self.mw, 'serial_mgr') else False
        if not hw_sync:
            self.mw.log("❌ Cannot Upload: ESP32 not connected. Please check the hardware bar.")
            return

        self.is_running = True
        self.upload_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        
        self.mw.log("📡 UPLOADING CODE TO HARDWARE (Outputting to Serial)...")
        for line in lines:
            if not self.is_running: break
            line = line.strip()
            if not line or line.startswith("#"): continue
            self.execute_line(line, force_hw_sync=True)
        
        self.is_running = False
        self.upload_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.update_hw_badge()
        self.mw.log("Hardware Upload Finished.")

    def run_program(self):
        """Simulation Only execution of the editor's code."""
        if self.is_running: return
        
        code = self.code_edit.toPlainText()
        lines = code.splitlines()
        
        self.is_running = True
        self.upload_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        
        # Determine if we should sync to hardware during simulation
        sync_to_hw = self.sync_hw_check.isChecked()
        hw_msg = "(Hardware Live Sync ENABLED)" if sync_to_hw else "(Hardware Signals Disabled)"
        
        self.mw.log(f"🧪 RUNNING {self.current_lang.upper()} SIMULATION {hw_msg}...")
        
        if self.current_lang == "python":
            self.run_python_code(code, sync_to_hw)
        elif self.current_lang == "matlab":
            self.run_matlab_code(code, sync_to_hw)
        else:
            # Standard "normal code" parsing
            for line in lines:
                if not self.is_running: break
                line = line.strip()
                if not line or line.startswith("#"): continue
                self.execute_line(line, force_hw_sync=sync_to_hw)
            
        self.is_running = False
        self.upload_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.mw.log(f"{self.current_lang.upper()} Finished.")

    def run_python_code(self, code, sync_to_hw):
        """Executes Python code with a safe robot API."""
        class RobotAPI:
            def __init__(self, panel, sync):
                self.panel = panel
                self.sync = sync
            def move(self, joint_name, angle):
                if not self.panel.is_running: return
                self.panel.execute_line(f"JOINT {joint_name} {angle}", force_hw_sync=self.sync)
            def wait(self, seconds):
                if not self.panel.is_running: return
                self.panel.execute_line(f"WAIT {seconds}")

        api = RobotAPI(self, sync_to_hw)
        try:
            # Execute with robot api available as 'robot'
            exec(code, {"robot": api, "print": self.mw.log})
        except Exception as e:
            self.mw.log(f"Python Error: {e}")

    def run_matlab_code(self, code, sync_to_hw):
        """Simulates Matlab syntax execution."""
        import re
        lines = code.splitlines()
        for line in lines:
            if not self.is_running: break
            line = line.strip()
            if not line or line.startswith("%"): continue
            
            # Simple regex for joint('name', value)
            joint_match = re.match(r"joint\s*\(['\"](.+?)['\"]\s*,\s*(-?\d+\.?\d*)\s*\);?", line, re.IGNORECASE)
            # Simple regex for pause(value)
            pause_match = re.match(r"pause\s*\((-?\d+\.?\d*)\s*\);?", line, re.IGNORECASE)
            
            if joint_match:
                name = joint_match.group(1)
                val = joint_match.group(2)
                self.execute_line(f"JOINT {name} {val}", force_hw_sync=sync_to_hw)
            elif pause_match:
                val = pause_match.group(1)
                self.execute_line(f"WAIT {val}")
            else:
                self.mw.log(f"Matlab Parser: Skipping unknown line: {line}")

    def stop_program(self):
        """Stops script execution."""
        if self.is_running:
            self.is_running = False
            self.mw.log("🛑 EXECUTION STOPPED BY USER.")

    def execute_line(self, line, force_hw_sync=False):
        """Core parsing and execution logic for a single line of code."""
        # Determine if we should send signals to serial
        hw_sync = False
        if force_hw_sync:
            hw_sync = self.mw.serial_mgr.is_connected if hasattr(self.mw, 'serial_mgr') else False
            self.update_hw_badge()
        else:
            self.hw_status_lbl.setText("● HW Idle")
            self.hw_status_lbl.setStyleSheet("color: #888;")
        
        try:
            parts = line.split()
            if not parts: return
            original_line = line
            
            # 1. Use global universal speed
            speed = float(self.mw.current_speed)
            
            # Remove SPEED from parts if it was explicitly typed (cleaning up legacy lines)
            if "SPEED" in [p.upper() for p in parts]:
                s_idx = [p.upper() for p in parts].index("SPEED")
                # Just remove it and skip its value
                parts = parts[:s_idx]
            
            # 2. Identify Command and Joint Name
            cmd = parts[0].upper()
            j_name = ""
            val = 0.0

            if cmd == "WAIT":
                if len(parts) >= 2:
                    val = float(parts[1])
            elif cmd == "JOINT":
                if len(parts) >= 3:
                    j_name = parts[1]
                    val = float(parts[2])
            else:
                # Potential Shorthand: Name Value (e.g. j1 90)
                if len(parts) >= 2:
                    potential_name = parts[0]
                    if potential_name in self.mw.robot.joints:
                        cmd = "JOINT"
                        j_name = potential_name
                        val = float(parts[1])
                    else:
                        self.mw.log(f"❓ Unknown joint or command: {potential_name}")
                        return
                else:
                    return
            
            if cmd == "JOINT":
                if j_name in self.mw.robot.joints:
                    joint = self.mw.robot.joints[j_name]
                    
                    # --- SAFETY CHECK ---
                    if val < joint.min_limit or val > joint.max_limit:
                        self.mw.log(f"⚠️ SAFETY SKIP: {j_name} command ({val}) is outside limits")
                        return
                        
                    start_val = joint.current_value
                    target_val = val
                    
                    if hw_sync:
                        # Send the target command ONCE to hardware
                        # The firmware handles its own internal smoothing
                        self.mw.serial_mgr.send_command(j_name, target_val, speed)

                    if speed > 0:
                        # Interpolate rotation FOR SIMULATION ONLY
                        diff = target_val - start_val
                        steps = int(abs(diff) / (speed * 0.1))
                        if steps > 0:
                            step_inc = diff / steps
                            for _ in range(steps):
                                if not self.is_running: return # Stop interpolation immediately
                                joint.current_value += step_inc
                                self.mw.robot.update_kinematics()
                                self.mw.canvas.update_transforms(self.mw.robot)
                                # Ghost shadow every ~12 deg
                                try:
                                    _l = joint.child_link
                                    import numpy as _np2
                                    import copy
                                    self.mw.canvas.add_joint_ghost(
                                        _l.name,
                                        mesh=_l.mesh,
                                        transform=_np2.copy(_l.t_world),
                                        color=getattr(_l, 'color', '#888888') or '#888888'
                                    )
                                except Exception:
                                    pass
                                
                                # Process UI events to keep view responsive
                                QtWidgets.QApplication.processEvents()
                                time.sleep(0.1)
                    
                    # Set final precise value
                    if not self.is_running: return
                    joint.current_value = target_val
                    self.mw.robot.update_kinematics()
                    self.mw.canvas.update_transforms(self.mw.robot)
                    if hasattr(self.mw, 'show_speed_overlay'):
                        self.mw.show_speed_overlay()
                    if hw_sync:
                        self.mw.serial_mgr.send_command(j_name, joint.current_value, speed)
                    QtWidgets.QApplication.processEvents()
            
            elif cmd == "WAIT":
                # Sleep in small chunks to allow stopping
                wait_time = val
                start_wait = time.time()
                while time.time() - start_wait < wait_time:
                    if not self.is_running: break
                    QtWidgets.QApplication.processEvents()
                    time.sleep(0.05)
                
            elif cmd == "MOVE":
                self.mw.log(f"CMD: {original_line} (IK implementation pending)")
                
        except Exception as e:
            self.mw.log(f"Error executing line: {line} -> {str(e)}")

    def update_hw_badge(self):
        """Syncs the badge color with the physical SerialManager state."""
        if not hasattr(self.mw, 'serial_mgr'): return
        
        if self.mw.serial_mgr.is_connected:
            if self.is_running and self.sync_hw_check.isChecked():
                self.hw_status_lbl.setText("● HW Streaming")
                self.hw_status_lbl.setStyleSheet("color: #4caf50;")
            else:
                self.hw_status_lbl.setText("● HW Online")
                self.hw_status_lbl.setStyleSheet("color: #2196f3;") # Blue for standby online
        else:
            self.hw_status_lbl.setText("● HW Offline")
            self.hw_status_lbl.setStyleSheet("color: #f44336;")
