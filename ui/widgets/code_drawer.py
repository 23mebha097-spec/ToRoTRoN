from PyQt5 import QtWidgets, QtCore, QtGui
import os
import subprocess
import threading
import time
import shutil
import re
import serial
import serial.tools.list_ports
import json

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ─────────────────────────────────────────────────────────────────────────────
# arduino-cli search locations (Windows + PATH fallback)
# Ordered: standalone install → Arduino IDE 2.x bundle → Arduino IDE 1.x bundle
# ─────────────────────────────────────────────────────────────────────────────
_ARDUINO_CLI_SEARCH_PATHS = [
    # Standalone arduino-cli installed via winget / installer
    r"C:\Program Files\arduino-cli\arduino-cli.exe",
    r"C:\Program Files\Arduino CLI\arduino-cli.exe",
    r"C:\Program Files (x86)\arduino-cli\arduino-cli.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\arduino-cli\arduino-cli.exe"),
    os.path.expandvars(r"%USERPROFILE%\scoop\shims\arduino-cli.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\arduino-cli\arduino-cli.exe"),
    # Arduino IDE 2.x (bundled cli)
    r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    r"C:\Program Files (x86)\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
    # Arduino IDE 1.x
    r"C:\Program Files\Arduino\hardware\tools\avr\bin\arduino-cli.exe",
    # Project-local (checked into repo alongside firmware/)
    os.path.join(_WORKSPACE_ROOT, "tools", "arduino-cli.exe"),
    os.path.join(_WORKSPACE_ROOT, "arduino-cli.exe"),
]

# ESP32-S3 FQBN — override via the UI combo if needed
_FQBN_ESP32_S3 = "esp32:esp32:esp32s3"

# Library install identifiers used by arduino-cli.
_LIB_ESP32_SERVO = ("ESP32Servo", "madhephaestus/ESP32Servo")
_LIB_ACCEL_STEPPER = ("AccelStepper", "waspinator/AccelStepper")


def _find_arduino_cli() -> str | None:
    """
    Returns the path to arduino-cli.exe if found, else None.
    Checks PATH first (fastest), then known install locations.
    """
    # 1. Check system PATH (covers all clean installations)
    from_path = shutil.which("arduino-cli")
    if from_path:
        return from_path

    # 2. Check known install locations
    for path in _ARDUINO_CLI_SEARCH_PATHS:
        if path and os.path.isfile(path):
            return path

    return None


class CodeDrawer(QtWidgets.QWidget):
    upload_status_signal = QtCore.pyqtSignal(str, bool)  # message, is_error

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        print("[DEBUG] CodeDrawer Initialized (v2_fixed)")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-left: 1px solid #333;
            }
            QLabel {
                color: #4a90e2;
                font-weight: bold;
            }
        """)

        # ── Header ────────────────────────────────────────────────────────────
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("ESP32-S3 CODE GENERATOR")
        title.setStyleSheet("font-size: 13px;")
        header.addWidget(title)

        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setToolTip("Close Code Panel")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { color: #ff5555; }
        """)
        self.close_btn.clicked.connect(self.hide_panel)
        header.addWidget(self.close_btn)
        self.layout.addLayout(header)

        # ── Code editor ───────────────────────────────────────────────────────
        self.code_edit = QtWidgets.QPlainTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setFont(QtGui.QFont("Consolas", 9))
        self.code_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121212;
                color: #a9b7c6;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        self.layout.addWidget(self.code_edit)

        # ── FQBN selector ─────────────────────────────────────────────────────
        fqbn_row = QtWidgets.QHBoxLayout()
        fqbn_lbl = QtWidgets.QLabel("Board:")
        fqbn_lbl.setStyleSheet("color: #888; font-size: 11px; font-weight: normal;")
        fqbn_row.addWidget(fqbn_lbl)

        self.fqbn_combo = QtWidgets.QComboBox()
        self.fqbn_combo.addItems([
            "esp32:esp32:esp32s3        (ESP32-S3 QIO)",
            "esp32:esp32:esp32s3:FlashMode=dio (ESP32-S3 DIO - Stable)",
            "esp32:esp32:esp32          (ESP32)",
            "esp32:esp32:esp32s2        (ESP32-S2)",
            "esp32:esp32:esp32c3        (ESP32-C3)",
        ])
        self.fqbn_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                color: #a9b7c6;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                color: #a9b7c6;
                selection-background-color: #1976d2;
            }
        """)
        fqbn_row.addWidget(self.fqbn_combo, 1)
        self.layout.addLayout(fqbn_row)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_layout = QtWidgets.QHBoxLayout()

        self.copy_btn = QtWidgets.QPushButton("📋 COPY")
        self.copy_btn.setToolTip("Copy code to clipboard")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: black;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #bbb;
            }
            QPushButton:hover { background-color: #4d4d4d; color: white; }
        """)
        self.copy_btn.clicked.connect(self.copy_code)
        btn_layout.addWidget(self.copy_btn)


        self.build_btn = QtWidgets.QPushButton("🛠️ BUILD FIRMWARE")
        self.build_btn.setToolTip("Compile the firmware to check for errors")
        self.build_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #1565c0; }
            QPushButton:disabled {
                background-color: #2c3e50;
                color: #7f8c8d;
            }
        """)
        self.build_btn.clicked.connect(self.build_firmware)
        btn_layout.addWidget(self.build_btn)

        self.upload_btn = QtWidgets.QPushButton("🚀 UPLOAD CODE")
        self.upload_btn.setToolTip("Upload the pre-built firmware to the detected board")
        self.upload_btn.setEnabled(False)  # Disabled until build succeeds
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled {
                background-color: #2c3e50;
                color: #7f8c8d;
            }
        """)
        self.upload_btn.clicked.connect(self.upload_code)
        btn_layout.addWidget(self.upload_btn)

        self.layout.addLayout(btn_layout)

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #888; font-size: 10px; font-weight: normal;")
        self.layout.addWidget(self.status_label)

        self.upload_status_signal.connect(self.on_upload_status)
        # ── Polling Timer for Auto-Detection ────────────────────────────────
        self.detect_timer = QtCore.QTimer(self)
        self.detect_timer.timeout.connect(self._auto_detect_hardware)
        self.detect_timer.start(3000)  # Check every 3 seconds

        self._upload_in_progress = False
        self._preflight_in_progress = False
        self._build_successful = False
        self._detected_port = None
        self._detected_board = None

        self._core_check_cache = {}  # {core_key: (ok, message, ts)}
        self._workspace_root = _WORKSPACE_ROOT
        self._arduino_runtime_root = os.path.join(self._workspace_root, ".arduino_runtime")
        self._arduino_user_dir = os.path.join(self._arduino_runtime_root, "user")
        self._arduino_downloads_dir = os.path.join(self._arduino_runtime_root, "downloads")
        self._arduino_tmp_dir = os.path.join(self._arduino_runtime_root, "tmp")
        for path in [
            self._arduino_runtime_root,
            self._arduino_user_dir,
            self._arduino_downloads_dir,
            self._arduino_tmp_dir,
        ]:
            os.makedirs(path, exist_ok=True)
        self.hide()

    def _log(self, message: str):
        """Thread-safe log helper that can be called from worker threads."""
        if hasattr(self.mw, "log_signal"):
            self.mw.log_signal.emit(str(message))
        elif hasattr(self.mw, "log"):
            self.mw.log(str(message))

    def _auto_detect_hardware(self):
        """Poll arduino-cli to detect connected boards and match them with UI targets."""
        self._update_button_states() # Keep UI sync with SerialManager state
        
        if self._upload_in_progress or self._preflight_in_progress:
            return

        cli_path = _find_arduino_cli()
        if not cli_path:
            return

        def task():
            try:
                result = subprocess.run(
                    [cli_path, "board", "list", "--format", "json"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=self._cli_env()
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    # arduino-cli returns a list or a dict depending on version
                    boards = data if isinstance(data, list) else data.get("detected_ports", [])
                    
                    for info in boards:
                        port = info.get("port", {}).get("address")
                        matching_boards = info.get("matching_boards", [])
                        
                        if port and matching_boards:
                            fqbn = matching_boards[0].get("fqbn")
                            name = matching_boards[0].get("name")
                            
                            if fqbn and port:
                                # Synchronize with UI if different
                                if port != self._detected_port or fqbn != self._detected_board:
                                    self._detected_port = port
                                    self._detected_board = fqbn
                                    QtCore.QMetaObject.invokeMethod(self, "_update_ui_from_detection", 
                                                                  QtCore.Qt.QueuedConnection,
                                                                  QtCore.Q_ARG(str, port),
                                                                  QtCore.Q_ARG(str, fqbn),
                                                                  QtCore.Q_ARG(str, name))
                                return # Pick first matching board
                
                # If no board found, reset detection memory but don't force UI reset yet
                # to avoid jitter if cable is loose
            except Exception:
                pass

        threading.Thread(target=task, daemon=True).start()

    @QtCore.pyqtSlot(str, str, str)
    def _update_ui_from_detection(self, port, fqbn, name):
        """Update the FQBN combo and port info based on auto-detection."""
        self._log(f"📋 Hardware detected: {name} on {port}")
        
        # 1. Update FQBN Combo
        for i in range(self.fqbn_combo.count()):
            if fqbn in self.fqbn_combo.itemText(i):
                self.fqbn_combo.setCurrentIndex(i)
                break
        else:
            # If not in list, add it temporarily or log it
            self.fqbn_combo.addItem(f"{fqbn} ({name})")
            self.fqbn_combo.setCurrentIndex(self.fqbn_combo.count() - 1)

        # 2. Update status label for visual confirmation
        self.status_label.setText(f"Auto-selected: {name} ({port})")
        self.status_label.setStyleSheet("color: #27ae60; font-size: 10px; font-weight: bold;")

    def _cli_env(self):
        """Environment override for arduino-cli to avoid OneDrive temp/library paths."""
        env = os.environ.copy()
        env["TEMP"] = self._arduino_tmp_dir
        env["TMP"] = self._arduino_tmp_dir
        env["ARDUINO_DIRECTORIES_USER"] = self._arduino_user_dir
        env["ARDUINO_DIRECTORIES_DOWNLOADS"] = self._arduino_downloads_dir
        return env

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_code(self, code: str):
        self.code_edit.setPlainText(code)

    def open_drawer(self):
        self.show()

    def hide_panel(self):
        self.hide()
        if hasattr(self.mw, "main_splitter"):
            self.mw.main_splitter.setSizes([350, 850, 0])

    def copy_code(self):
        QtWidgets.QApplication.clipboard().setText(self.code_edit.toPlainText())
        self.copy_btn.setText("✓ COPIED")
        QtCore.QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋 COPY"))

    # ─────────────────────────────────────────────────────────────────────────
    # Upload
    # ─────────────────────────────────────────────────────────────────────────

    def _selected_fqbn(self) -> str:
        """Extract the raw FQBN token from the combo text."""
        raw = self.fqbn_combo.currentText().split()[0].strip()
        return raw if raw else _FQBN_ESP32_S3

    def _required_libraries_from_code(self, code_text: str):
        """Infer required Arduino libraries from include directives in generated code."""
        required = []
        if "#include <ESP32Servo.h>" in code_text:
            required.append(_LIB_ESP32_SERVO)
        if "#include <AccelStepper.h>" in code_text:
            required.append(_LIB_ACCEL_STEPPER)
        return required

    def _installed_libraries_output(self, cli_path: str):
        """Return raw `arduino-cli lib list` output, or None if command fails."""
        result = subprocess.run(
            [cli_path, "lib", "list"],
            capture_output=True,
            text=True,
            timeout=12,
            cwd=self._workspace_root,
            env=self._cli_env(),
        )
        if result.returncode != 0:
            return None
        return result.stdout or ""

    def _missing_libraries(self, cli_path: str, required_libs):
        """Return subset of required libraries that are not installed."""
        if not required_libs:
            return []
        listed = self._installed_libraries_output(cli_path)
        if listed is None:
            return list(required_libs)

        listed_lower = listed.lower()
        missing = []
        for display_name, _install_name in required_libs:
            if display_name.lower() not in listed_lower:
                missing.append((display_name, _install_name))
        return missing

    def _ensure_required_libraries(self, cli_path: str, required_libs):
        """Install missing required libraries before compile/upload."""
        missing = self._missing_libraries(cli_path, required_libs)
        if not missing:
            return True, "Libraries ready"

        missing_names = ", ".join(name for name, _ in missing)
        self.upload_status_signal.emit(f"Installing missing libraries: {missing_names}...", False)
        self._log(f"Installing Arduino libs: {missing_names}")

        for display_name, install_name in missing:
            install_cmd = [cli_path, "lib", "install", install_name]
            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self._workspace_root,
                env=self._cli_env(),
            )
            if result.returncode != 0:
                # Fallback: some cli setups accept plain display name better.
                fallback_cmd = [cli_path, "lib", "install", display_name]
                fallback = subprocess.run(
                    fallback_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=self._workspace_root,
                    env=self._cli_env(),
                )
                if fallback.returncode != 0:
                    err = (fallback.stderr or fallback.stdout or result.stderr or result.stdout or "Unknown lib install error").strip()
                    return False, f"Failed to install {display_name}: {self._summarize_upload_error(err)}"

        # Verify again after install.
        still_missing = self._missing_libraries(cli_path, required_libs)
        if still_missing:
            names = ", ".join(name for name, _ in still_missing)
            return False, f"Missing libraries after install: {names}"

        return True, "Libraries installed"

    def upload_code(self):
        """Validates prerequisites then spawns upload thread."""
        if self._upload_in_progress:
            self.on_upload_status("Upload already running...", False)
            return
        if self._preflight_in_progress:
            self.on_upload_status("Wait for preflight to finish", True)
            return

        # 1. Find arduino-cli
        cli_path = _find_arduino_cli()
        if not cli_path:
            self._show_cli_missing_dialog()
            return

        code_text = self.code_edit.toPlainText().strip()
        if not code_text:
            self.on_upload_status("No firmware code to upload", True)
            return
        required_libs = self._required_libraries_from_code(code_text)

        # 2. Validate COM port
        port = ""
        if hasattr(self.mw, "serial_mgr") and self.mw.serial_mgr.port_name:
            port = self.mw.serial_mgr.port_name
        if not port:
            port = self.mw.port_combo.currentText()
        port = port.split()[0].strip()  # strip description suffix

        if not port or port.lower() in ("no ports found", ""):
            self._log("⚠️ No COM port selected. Choose a port in the top bar.")
            self.on_upload_status("Select a COM port first!", True)
            return

        self._upload_in_progress = True
        self.upload_btn.setEnabled(False)
        if hasattr(self.mw, "port_scan_timer"):
            self.mw.port_scan_timer.stop()
        self._log(f"🚀 Uploading to {port} via {os.path.basename(cli_path)}...")

        thread = threading.Thread(
            target=self._run_upload_process,
            args=(cli_path, port, self._selected_fqbn(), required_libs),
            daemon=True,
        )
        thread.start()


    def _check_core_installed(self, cli_path: str, core_key: str):
        """Check installed board core, caching results briefly for speed."""
        now = time.time()
        cached = self._core_check_cache.get(core_key)
        if cached and (now - cached[2]) < 45:
            return cached[0], cached[1]

        result = subprocess.run(
            [cli_path, "core", "list"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=self._workspace_root,
            env=self._cli_env(),
        )

        if result.returncode != 0:
            msg = "Unable to query installed board cores"
            self._core_check_cache[core_key] = (False, msg, now)
            return False, msg

        output = result.stdout or ""
        installed = any(line.strip().startswith(core_key) for line in output.splitlines())
        if installed:
            msg = "Board core available"
            self._core_check_cache[core_key] = (True, msg, now)
            return True, msg

        msg = f"Missing core {core_key}. Run: arduino-cli core install {core_key}"
        self._core_check_cache[core_key] = (False, msg, now)
        return False, msg

    def build_firmware(self):
        """Pre-compiles the firmware code to verify correctness before upload."""
        if self._upload_in_progress or self._preflight_in_progress:
            return

        cli_path = _find_arduino_cli()
        if not cli_path:
            self._show_cli_missing_dialog()
            return

        code_text = self.code_edit.toPlainText().strip()
        if not code_text:
            self.on_upload_status("No firmware code to build", True)
            return

        self._preflight_in_progress = True
        self.build_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.upload_status_signal.emit("Building firmware (Compiling)...", False)

        def task():
            sketch_dir = os.path.join(self._workspace_root, "firmware", "torotron_esp32")
            os.makedirs(sketch_dir, exist_ok=True)
            ino_path = os.path.join(sketch_dir, "torotron_esp32.ino")
            fqbn = self._selected_fqbn()
            build_dir = os.path.join(self._workspace_root, ".build", "arduino", re.sub(r"[^a-zA-Z0-9_.-]", "_", fqbn))
            os.makedirs(build_dir, exist_ok=True)

            try:
                # Write sketch
                with open(ino_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(code_text)
                
                required_libs = self._required_libraries_from_code(code_text)
                libs_ok, libs_msg = self._ensure_required_libraries(cli_path, required_libs)
                if not libs_ok:
                    self.upload_status_signal.emit(f"❌ {libs_msg}", True)
                    return

                res = self._compile_only(cli_path, fqbn, build_dir, sketch_dir)
                if res.returncode == 0:
                    self._build_successful = True
                    self._log("✅ Build successful.")
                    self.upload_status_signal.emit("✅ Build complete. Ready for Upload.", False)
                else:
                    self._build_successful = False
                    err = (res.stderr or res.stdout or "Compilation failed").strip()
                    self.upload_status_signal.emit(f"❌ Build failed: {self._summarize_upload_error(err)}", True)
                    self._log(f"❌ Build failed:\n{err}")
            except Exception as e:
                self.upload_status_signal.emit(f"❌ Build error: {e}", True)
            finally:
                self._preflight_in_progress = False
                QtCore.QMetaObject.invokeMethod(self, "_update_button_states", QtCore.Qt.QueuedConnection)

        threading.Thread(target=task, daemon=True).start()

    def _compile_only(self, cli_path, fqbn, build_dir, sketch_dir):
        """Runs arduino-cli compile without uploading."""
        cmd = [
            cli_path, "compile",
            "--fqbn", fqbn,
            "--build-path", build_dir,
            sketch_dir
        ]
        self._log(f"Compiling: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=self._workspace_root,
            env=self._cli_env()
        )

    @QtCore.pyqtSlot()
    def _update_button_states(self):
        is_connected = getattr(self.mw.serial_mgr, "is_connected", False)
        self.build_btn.setEnabled(True)
        self.upload_btn.setEnabled(self._build_successful and is_connected)
        
        # update tooltips to help the user
        if not is_connected:
            self.upload_btn.setToolTip("Upload disabled: Hardware not connected.")
        elif not self._build_successful:
            self.upload_btn.setToolTip("Upload disabled: Build the firmware first.")
        else:
            self.upload_btn.setToolTip("Ready to upload firmware to ESP32.")

    def _upload_built_sketch(self, cli_path, port, fqbn, build_dir, sketch_dir, upload_speed):
        """
        Upload precompiled binaries using Popen to capture real-time progress.
        Returns (returncode, full_output_text).
        """
        cmd = [
            cli_path, "upload",
            "--port", port,
            "--fqbn", fqbn,
            "--input-dir", build_dir,
            "--upload-property", f"upload.speed={upload_speed}",
            "--upload-property", f"upload_speed={upload_speed}",
            sketch_dir,
        ]
        self._log(f"CMD: {' '.join(cmd)}")
        
        full_output = []
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self._workspace_root,
                env=self._cli_env()
            )
            
            last_progress_time = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if not line:
                    continue
                
                full_output.append(line)
                match = re.search(r"(\d+)\s*%", line)
                if match:
                    percent = int(match.group(1))
                    now = time.time()
                    if now - last_progress_time >= 1.5:
                        self.upload_status_signal.emit(f"Uploading: {percent}% complete", False)
                        last_progress_time = now
                
                self._log(f"[UPLOAD] {line.strip()}")
            
            return process.returncode, "".join(full_output)
        except Exception as e:
            err_msg = f"Upload process failed to start: {e}"
            self._log(f"❌ {err_msg}")
            return -1, err_msg

    def _trigger_bootloader_mode(self, port: str):
        """Best-effort ESP32 auto-boot sequence via DTR/RTS before upload attempt."""
        try:
            with serial.Serial(port=port, baudrate=115200, timeout=0.2, write_timeout=0.2) as ser:
                # Common ESP32 auto-program sequence (active-low via USB-UART bridge):
                # IO0 low + reset pulse, then release IO0.
                ser.dtr = False
                ser.rts = False
                time.sleep(0.05)

                ser.dtr = True   # IO0 low
                ser.rts = False
                time.sleep(0.10)

                ser.rts = True   # EN low (reset)
                time.sleep(0.12)

                ser.rts = False  # EN high (boot)
                time.sleep(0.12)

                ser.dtr = False  # IO0 high (release)
                time.sleep(0.08)
            return True
        except Exception as e:
            self._log(f"Bootloader trigger skipped on {port}: {e}")
            return False

    def _candidate_upload_ports(self, preferred_port: str):
        """Return a list of COM ports to attempt, starting with the preferred one."""
        available = [p.device for p in serial.tools.list_ports.comports()]
        if preferred_port in available:
            # Shift preferred to front
            available.remove(preferred_port)
            return [preferred_port] + available
        return available if available else [preferred_port]

    def _run_upload_process(self, cli_path: str, port: str, fqbn: str, required_libs):
        """Background thread: write .ino → compile once → retry upload safely."""
        sketch_dir = os.path.join(self._workspace_root, "firmware", "torotron_esp32")
        os.makedirs(sketch_dir, exist_ok=True)
        ino_path = os.path.join(sketch_dir, "torotron_esp32.ino")
        build_dir = os.path.join(self._workspace_root, ".build", "arduino", re.sub(r"[^a-zA-Z0-9_.-]", "_", fqbn))
        os.makedirs(build_dir, exist_ok=True)

        was_connected = getattr(self.mw.serial_mgr, "is_connected", False)

        try:
            # 1. Write sketch atomically
            tmp_path = ino_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.code_edit.toPlainText())
            os.replace(tmp_path, ino_path)

            # 2. Release serial port so arduino-cli can claim it
            if was_connected:
                self.upload_status_signal.emit("Releasing serial port...", False)
                self.mw.serial_mgr.disconnect()
                time.sleep(1.2)

            # 3. Upload pre-built binaries
            self.upload_status_signal.emit("Initializing upload process...", False)

            # Upload retries for ESP32 bootloader timing issues.
            upload_ok = False
            last_err = ""
            speed_plan = [460800, 115200]
            attempt = 0
            for speed in speed_plan:
                ports = self._candidate_upload_ports(port)
                for target_port in ports:
                    attempt += 1
                    self.upload_status_signal.emit(
                        f"Uploading attempt {attempt}: {target_port} @ {speed}...",
                        False,
                    )

                    # Allow USB re-enumeration window after reset/disconnect.
                    time.sleep(1.0 if attempt == 1 else 1.5)

                    # Try to place ESP32 in bootloader mode before each upload attempt.
                    self.upload_status_signal.emit(f"Preparing bootloader on {target_port}...", False)
                    self._trigger_bootloader_mode(target_port)

                    ret_code, output = self._upload_built_sketch(
                        cli_path=cli_path,
                        port=target_port,
                        fqbn=fqbn,
                        build_dir=build_dir,
                        sketch_dir=sketch_dir,
                        upload_speed=speed,
                    )

                    if ret_code == 0:
                        upload_ok = True
                        port = target_port
                        break

                    last_err = output.strip() if output else "Unknown upload error"
                    self._log(f"Upload attempt failed ({target_port} @ {speed}):\n{last_err}")

                    # If bootloader handshake failed, keep retrying with next strategy.
                    if "no serial data received" in last_err.lower():
                        continue
                    if "failed to connect" in last_err.lower():
                        continue

                if upload_ok:
                    break

            if upload_ok:
                self.upload_status_signal.emit("✅ Upload successful!", False)
                self._log("✅ Firmware uploaded to ESP32 successfully.")
                self._build_successful = False # Reset build state after successful upload
                self.upload_btn.setEnabled(False) 
                
                # --- DIGITAL TWIN TRIGGER ---
                # After successful upload, notify MainWindow to initialize Twin sync
                if hasattr(self.mw, "on_firmware_upload_success"):
                    self.mw.on_firmware_upload_success(port)
            else:
                # Final assisted fallback for boards that require manual BOOT/RESET timing.
                lower_err = (last_err or "").lower()
                if "no serial data received" in lower_err or "failed to connect to esp32" in lower_err:
                    self._log("Manual boot fallback: Hold BOOT, press RESET once, keep BOOT held for ~2 seconds.")
                    self.upload_status_signal.emit("Manual boot mode: hold BOOT, tap RESET now...", True)
                    time.sleep(3.0)
                    m_code, m_out = self._upload_built_sketch(
                        cli_path=cli_path,
                        port=port,
                        fqbn=fqbn,
                        build_dir=build_dir,
                        sketch_dir=sketch_dir,
                        upload_speed=115200,
                    )
                    if m_code == 0:
                        self.upload_status_signal.emit("✅ Upload successful (manual boot mode)!", False)
                        self._log("✅ Firmware uploaded to ESP32 successfully (manual boot mode).")
                        upload_ok = True
                        if hasattr(self.mw, "on_firmware_upload_success"):
                            self.mw.on_firmware_upload_success(port)
                    else:
                        last_err = m_out.strip() if m_out else "Manual upload failed"

            if not upload_ok:
                short_err = self._summarize_upload_error(last_err)
                self.upload_status_signal.emit(f"❌ {short_err}", True)
                self._log(f"❌ Upload failed:\n{last_err}")

        except subprocess.TimeoutExpired:
            self.upload_status_signal.emit("❌ Timeout: upload took too long", True)
        except FileNotFoundError:
            self.upload_status_signal.emit("❌ arduino-cli not found during upload", True)
        except Exception as e:
            self.upload_status_signal.emit(f"❌ Unexpected upload error: {e}", True)

        finally:
            # Reconnection handled by MainWindow.on_firmware_upload_success if successful
            pass

            self.upload_status_signal.emit("Ready.", False)

    def _summarize_upload_error(self, output: str) -> str:
        """Produce a concise user-friendly error line from CLI output."""
        text = output or "Unknown upload error"
        lower = text.lower()
        if "no upload port provided" in lower or "port" in lower and "not found" in lower:
            return "COM port not available. Reconnect ESP32 and retry"
        if "failed to open port" in lower or "access is denied" in lower:
            return "COM port is busy or blocked. Close serial monitor and retry"
        if "failed to connect to esp32" in lower or "no serial data received" in lower:
            return "ESP32 did not enter bootloader. Hold BOOT and press RESET once, then retry upload"
        if "no such file or directory" in lower and "arduino-cli" in lower:
            return "arduino-cli executable not found"
        if "unknown fqbn" in lower or "platform esp32:esp32 is not installed" in lower:
            return "ESP32 board core missing. Install: arduino-cli core install esp32:esp32"
        if "creating temp dir for extraction" in lower or "one drive" in lower or "onedrive" in lower:
            return "Library install path issue (OneDrive/temp). Use local runtime folders and retry"
        if "compilation error" in lower or "error:" in lower:
            return "Compilation failed. Check detailed log output"

        for line in text.splitlines():
            clean = line.strip()
            if clean:
                return clean[:140]
        return "Upload failed"

    # ─────────────────────────────────────────────────────────────────────────
    # arduino-cli missing — friendly dialog
    # ─────────────────────────────────────────────────────────────────────────

    def _show_cli_missing_dialog(self):
        """Shows a helpful dialog with install instructions when cli is missing."""
        self._log("❌ arduino-cli not found. See the install dialog.")
        if hasattr(self.mw, "show_toast"):
            self.mw.show_toast("arduino-cli not found", "error")

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("arduino-cli Not Found")
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText(
            "<b>arduino-cli was not found on this machine.</b>"
        )
        msg.setInformativeText(
            "arduino-cli is required to compile and upload firmware.<br><br>"
            "<b>Option 1 — Standalone install (recommended):</b><br>"
            "Download from <a href='https://arduino.github.io/arduino-cli/latest/installation/'>"
            "arduino.github.io/arduino-cli</a><br>"
            "or run in PowerShell:<br>"
            "<code>winget install Arduino.ArduinoCLI</code><br><br>"
            "<b>Option 2 — Arduino IDE 2 bundled CLI:</b><br>"
            "Install Arduino IDE 2 from <a href='https://www.arduino.cc/en/software'>arduino.cc</a>.<br><br>"
            "<b>After installing:</b><br>"
            "• Restart ToRoTRoN<br>"
            "• Install ESP32 boards: <code>arduino-cli core install esp32:esp32</code><br><br>"
            "In the meantime, use <b>📋 COPY</b> to paste the code into Arduino IDE manually."
        )
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.setStyleSheet("""
            QMessageBox {
                background: white;
                font-family: 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
            }
            QLabel { color: #212121; font-size: 13px; }
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1565c0; }
        """)
        msg.exec_()

    # ─────────────────────────────────────────────────────────────────────────
    # Status update (runs on main thread via signal)
    # ─────────────────────────────────────────────────────────────────────────

    def on_upload_status(self, msg: str, is_error: bool):
        if msg is None: return
        self.status_label.setText(msg)
        if is_error:
            self.status_label.setStyleSheet("color: #ff5555; font-size: 11px;")
            if hasattr(self.mw, "show_toast"):
                self.mw.show_toast(msg.replace("❌", "").strip(), "error", duration=4500)
        elif "SUCCESS" in msg.upper() or "✅" in msg:
            self.status_label.setStyleSheet("color: #4caf50; font-size: 11px; font-weight: bold;")
            if hasattr(self.mw, "show_toast"):
                if "PREFLIGHT" in msg.upper():
                    self.mw.show_toast("Preflight passed", "success", duration=2200)
                else:
                    self.mw.show_toast("ESP32 upload successful", "success", duration=2600)
        else:
            self.status_label.setStyleSheet("color: #4a90e2; font-size: 10px;")

        if "Ready" in msg:
            self._upload_in_progress = False
            self.upload_btn.setEnabled(True)
            self.build_btn.setEnabled(True)
            if hasattr(self.mw, "port_scan_timer"):
                self.mw.port_scan_timer.start(5000)

        # Help user with SHA-256 boot errors
        if "SHA-256" in msg:
            self.status_label.setText("⚠ ESP32 Boot Error: SHA-256 Mismatch. Try DIO mode or lower baud.")
            self.status_label.setStyleSheet("color: #ff9800; font-size: 10px;")
