from PyQt5 import QtWidgets, QtCore, QtGui
import time
import os
import re


class RobotSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for robot programming languages (Command, Python, Matlab)."""

    def __init__(self, document, lang="command"):
        super().__init__(document)
        self.lang = lang
        self._build_rules()

    def set_language(self, lang):
        self.lang = lang
        self._build_rules()
        self.rehighlight()

    def _build_rules(self):
        self.rules = []

        # --- FORMATS ---
        keyword_fmt = QtGui.QTextCharFormat()
        keyword_fmt.setForeground(QtGui.QColor("#1976d2"))
        keyword_fmt.setFontWeight(QtGui.QFont.Bold)

        builtin_fmt = QtGui.QTextCharFormat()
        builtin_fmt.setForeground(QtGui.QColor("#1565c0"))
        builtin_fmt.setFontWeight(QtGui.QFont.Bold)

        number_fmt = QtGui.QTextCharFormat()
        number_fmt.setForeground(QtGui.QColor("#0d47a1"))

        string_fmt = QtGui.QTextCharFormat()
        string_fmt.setForeground(QtGui.QColor("#00796b"))

        comment_fmt = QtGui.QTextCharFormat()
        comment_fmt.setForeground(QtGui.QColor("#9e9e9e"))
        comment_fmt.setFontItalic(True)

        func_fmt = QtGui.QTextCharFormat()
        func_fmt.setForeground(QtGui.QColor("#0d47a1"))

        if self.lang == "command":
            # Robot command keywords
            for kw in [r'\bJOINT\b', r'\bWAIT\b', r'\bMOVE\b', r'\bSPEED\b', r'\bHOME\b', r'\bLOOP\b']:
                self.rules.append((re.compile(kw, re.IGNORECASE), keyword_fmt))
            # Comments
            self.rules.append((re.compile(r'#.*$', re.MULTILINE), comment_fmt))

        elif self.lang == "python":
            # Python keywords
            py_keywords = [
                r'\bdef\b', r'\bclass\b', r'\bimport\b', r'\bfrom\b', r'\breturn\b',
                r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
                r'\bin\b', r'\bnot\b', r'\band\b', r'\bor\b', r'\bTrue\b',
                r'\bFalse\b', r'\bNone\b', r'\btry\b', r'\bexcept\b', r'\bwith\b',
                r'\bas\b', r'\blambda\b', r'\byield\b', r'\bpass\b', r'\bbreak\b',
                r'\bcontinue\b', r'\braise\b',
            ]
            for kw in py_keywords:
                self.rules.append((re.compile(kw), keyword_fmt))
            # Builtins
            for bi in [r'\bprint\b', r'\brange\b', r'\blen\b', r'\bint\b', r'\bfloat\b', r'\bstr\b']:
                self.rules.append((re.compile(bi), builtin_fmt))
            # Function calls
            self.rules.append((re.compile(r'\b[a-zA-Z_]\w*(?=\s*\()'), func_fmt))
            # Strings
            self.rules.append((re.compile(r"'[^']*'"), string_fmt))
            self.rules.append((re.compile(r'"[^"]*"'), string_fmt))
            # Comments
            self.rules.append((re.compile(r'#.*$', re.MULTILINE), comment_fmt))

        elif self.lang == "matlab":
            # Matlab keywords
            for kw in [r'\bfunction\b', r'\bend\b', r'\bif\b', r'\belse\b', r'\bfor\b',
                        r'\bwhile\b', r'\breturn\b', r'\bpause\b']:
                self.rules.append((re.compile(kw, re.IGNORECASE), keyword_fmt))
            # Function calls
            self.rules.append((re.compile(r'\bjoint\b', re.IGNORECASE), builtin_fmt))
            # Strings
            self.rules.append((re.compile(r"'[^']*'"), string_fmt))
            # Comments
            self.rules.append((re.compile(r'%.*$', re.MULTILINE), comment_fmt))

        # Numbers (universal)
        self.rules.append((re.compile(r'\b-?\d+\.?\d*\b'), number_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class LineNumberArea(QtWidgets.QWidget):
    """Line number gutter for the code editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QtCore.QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QtWidgets.QPlainTextEdit):
    """Professional code editor with line numbers and current-line highlight."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        # Editor font
        font = QtGui.QFont("Consolas", 11)
        font.setStyleHint(QtGui.QFont.Monospace)
        self.setFont(font)

        # Tab width
        metrics = QtGui.QFontMetrics(font)
        self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))

        # Editor style
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #fafafa;
                color: #212121;
                border: 1px solid #e0e0e0;
                selection-background-color: #bbdefb;
                selection-color: #212121;
                padding-left: 5px;
            }
        """)

    def line_number_area_width(self):
        digits = max(1, len(str(self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QtCore.QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QtGui.QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QtGui.QColor("#f5f5f5"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QtGui.QColor("#bdbdbd"))
                painter.setFont(self.font())
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignRight, number
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

        painter.end()

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            line_color = QtGui.QColor("#e3f2fd")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)


class ProgramPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.is_running = False
        self.current_lang = "command"  # Default language

        # Example templates for each language
        self.templates = {
            "command": "# Command format: JOINT Name Angle\nJOINT Shoulder 45\nWAIT 1.0\nJOINT Shoulder -45\nWAIT 1.0\n",
            "python": "# Python API: robot.move('Name', Angle)\nrobot.move('Shoulder', 45)\nrobot.wait(1.0)\nrobot.move('Shoulder', -45)\nrobot.wait(1.0)\n",
            "matlab": "% Matlab Syntax: joint('Name', Angle)\njoint('Shoulder', 45);\npause(1.0);\njoint('Shoulder', -45);\npause(1.0);\n"
        }

        self.init_ui()

        # Periodic UI updates for hardware health
        self.badge_timer = QtCore.QTimer(self)
        self.badge_timer.timeout.connect(self.update_hw_badge)
        self.badge_timer.start(1000)  # Check every 1s

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- TOP TOOLBAR ---
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(6)

        # Icon-based action buttons — blue/white/black theme
        btn_style = """
            QPushButton {
                background-color: white;
                color: #212121;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976d2;
                color: white;
                border-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #1565c0;
                color: white;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #bdbdbd;
                border-color: #e0e0e0;
            }
        """

        self.upload_btn = QtWidgets.QPushButton("  Upload")
        self.upload_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.upload_btn.setToolTip("Upload code to hardware (ESP32)")
        self.upload_btn.setAccessibleName("Upload to Hardware")
        self.upload_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.upload_btn.setStyleSheet(btn_style)
        self.upload_btn.clicked.connect(self.upload_code)
        toolbar.addWidget(self.upload_btn)

        self.run_btn = QtWidgets.QPushButton("  Run")
        self.run_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        self.run_btn.setToolTip("Run simulation")
        self.run_btn.setAccessibleName("Run Simulation")
        self.run_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.run_btn.setStyleSheet(btn_style)
        self.run_btn.clicked.connect(self.run_program)
        toolbar.addWidget(self.run_btn)

        self.stop_btn = QtWidgets.QPushButton("  Stop")
        self.stop_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop))
        self.stop_btn.setToolTip("Stop execution")
        self.stop_btn.setAccessibleName("Stop Execution")
        self.stop_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.stop_btn.setStyleSheet(btn_style)
        self.stop_btn.clicked.connect(self.stop_program)
        toolbar.addWidget(self.stop_btn)

        toolbar.addStretch()

        # --- LIVE SYNC OPTION ---
        self.sync_hw_check = QtWidgets.QCheckBox("Live Sync")
        self.sync_hw_check.setToolTip("If checked, Run will also move physical motors")
        self.sync_hw_check.setStyleSheet("""
            QCheckBox {
                color: #424242;
                font-size: 11px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #bdbdbd;
                border-radius: 3px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #1976d2;
                border-color: #1976d2;
            }
        """)
        toolbar.addWidget(self.sync_hw_check)

        self.hw_status_lbl = QtWidgets.QLabel("● Idle")
        self.hw_status_lbl.setStyleSheet("color: #bdbdbd; margin-left: 8px; font-size: 11px;")
        toolbar.addWidget(self.hw_status_lbl)

        layout.addLayout(toolbar)

        # --- Thin separator ---
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(sep)

        # --- CODE EDITOR ---
        self.code_edit = CodeEditor()
        self.code_edit.setPlainText(self.templates["command"])

        # Syntax highlighter
        self.highlighter = RobotSyntaxHighlighter(self.code_edit.document(), "command")

        # Editor takes all available space
        layout.addWidget(self.code_edit, 1)

        # --- LANGUAGE SELECTION (Bottom) ---
        lang_layout = QtWidgets.QHBoxLayout()
        lang_layout.setSpacing(8)

        lang_label = QtWidgets.QLabel("Language:")
        lang_label.setStyleSheet("color: #757575; font-size: 15px; font-weight: bold;")
        lang_layout.addWidget(lang_label)

        self.lang_btns = {}
        for lang_key, display_name in [("command", "Command"), ("python", "Python"), ("matlab", "Matlab")]:
            btn = QtWidgets.QPushButton(display_name)
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #424242;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 8px 20px;
                    font-weight: bold;
                    font-size: 15px;
                }
                QPushButton:checked {
                    background-color: #1976d2;
                    color: white;
                    border-color: #1976d2;
                }
                QPushButton:hover:!checked {
                    background-color: #f5f5f5;
                    border-color: #1976d2;
                    color: #1976d2;
                }
            """)
            btn.clicked.connect(lambda checked, lk=lang_key: self.set_language(lk))
            lang_layout.addWidget(btn)
            self.lang_btns[lang_key] = btn

        lang_layout.addStretch()
        self.lang_btns["command"].setChecked(True)
        layout.addLayout(lang_layout)

        # --- BUILD FIRMWARE BUTTON ---
        self.build_fw_btn = QtWidgets.QPushButton("Build Firmware")
        self.build_fw_btn.setToolTip("Generate ESP32 Arduino code for all joints")
        self.build_fw_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.build_fw_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                padding: 12px;
                font-size: 14px;
                border: none;
                border-radius: 8px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        self.build_fw_btn.clicked.connect(lambda: self.mw.on_generate_code())
        layout.addWidget(self.build_fw_btn)

    def set_language(self, lang_key):
        """Switches the editor template and parsing mode."""
        self.current_lang = lang_key

        # Uncheck others
        for key, btn in self.lang_btns.items():
            btn.blockSignals(True)
            btn.setChecked(key == lang_key)
            btn.blockSignals(False)

        # Set template if editor is empty or just has another template
        current_text = self.code_edit.toPlainText().strip()
        is_default = any(current_text == t.strip() for t in self.templates.values())
        if not current_text or is_default:
            self.code_edit.setPlainText(self.templates[self.current_lang])

        # Update syntax highlighter
        self.highlighter.set_language(lang_key)

        self.mw.log(f"Language set to: {lang_key.capitalize()}")

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
            # Standard "command" parsing
            for line in lines:
                if not self.is_running: break
                line = line.strip()
                if not line or line.startswith("#"): continue
                self.execute_line(line, force_hw_sync=sync_to_hw)

        self.is_running = False
        self.upload_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.mw.log(f"{self.current_lang.capitalize()} Finished.")

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
            self.hw_status_lbl.setText("● Idle")
            self.hw_status_lbl.setStyleSheet("color: #bdbdbd; font-size: 11px;")

        try:
            parts = line.split()
            if not parts: return
            original_line = line

            # 1. Use global universal speed
            speed = float(self.mw.current_speed)

            # Search for and handle optional 'SPEED' parameter (e.g., JOINT Shoulder 90 SPEED 10)
            upper_parts = [p.upper() for p in parts]
            if "SPEED" in upper_parts:
                s_idx = upper_parts.index("SPEED")
                if len(parts) > s_idx + 1:
                    try:
                        speed = float(parts[s_idx + 1])
                        self.mw.log(f"⚡ Override Speed: {speed}%")
                    except ValueError:
                        self.mw.log(f"⚠️ Invalid speed value: {parts[s_idx+1]}")
                # Clean parts so the rest of the parsing (JOINT, WAIT, etc.) ignores the speed suffix
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
                                if not self.is_running: return  # Stop interpolation immediately
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
        """Syncs the badge color with the physical SerialManager state and liveness."""
        if not hasattr(self.mw, 'serial_mgr'): return

        sm = self.mw.serial_mgr
        if sm.is_connected:
            if not sm.is_alive:
                self.hw_status_lbl.setText("● Stalled")
                self.hw_status_lbl.setStyleSheet("color: #ff9800; font-size: 11px;")
            elif self.is_running and self.sync_hw_check.isChecked():
                self.hw_status_lbl.setText("● Streaming")
                self.hw_status_lbl.setStyleSheet("color: #1976d2; font-size: 11px;")
            else:
                self.hw_status_lbl.setText("● Online")
                self.hw_status_lbl.setStyleSheet("color: #1976d2; font-size: 11px;")
        else:
            self.hw_status_lbl.setText("● Offline")
            self.hw_status_lbl.setStyleSheet("color: #bdbdbd; font-size: 11px;")
