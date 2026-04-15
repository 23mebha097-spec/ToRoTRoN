from PyQt5 import QtWidgets, QtCore, QtGui
import os
import subprocess
import threading
import time
import shutil


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
    os.path.join(os.getcwd(), "tools", "arduino-cli.exe"),
    os.path.join(os.getcwd(), "arduino-cli.exe"),
]

# ESP32-S3 FQBN — override via the UI combo if needed
_FQBN_ESP32_S3 = "esp32:esp32:esp32s3"


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
            "esp32:esp32:esp32s3        (ESP32-S3)",
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

        self.upload_btn = QtWidgets.QPushButton("🚀 UPLOAD")
        self.upload_btn.setToolTip("Compile and Upload to ESP32-S3 via arduino-cli")
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
        self.hide()

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

    def upload_code(self):
        """Validates prerequisites then spawns upload thread."""
        # 1. Find arduino-cli
        cli_path = _find_arduino_cli()
        if not cli_path:
            self._show_cli_missing_dialog()
            return

        # 2. Validate COM port
        port = ""
        if hasattr(self.mw, "serial_mgr") and self.mw.serial_mgr.port_name:
            port = self.mw.serial_mgr.port_name
        if not port:
            port = self.mw.port_combo.currentText()
        port = port.split()[0].strip()  # strip description suffix

        if not port or port.lower() in ("no ports found", ""):
            self.mw.log("⚠️ No COM port selected. Choose a port in the top bar.")
            self.on_upload_status("Select a COM port first!", True)
            return

        self.upload_btn.setEnabled(False)
        self.mw.log(f"🚀 Uploading to {port} via {os.path.basename(cli_path)}...")

        thread = threading.Thread(
            target=self._run_upload_process,
            args=(cli_path, port, self._selected_fqbn()),
            daemon=True,
        )
        thread.start()

    def _run_upload_process(self, cli_path: str, port: str, fqbn: str):
        """Background thread: write .ino → compile → upload."""
        # 1. Write sketch to firmware directory
        sketch_dir = os.path.join(os.getcwd(), "firmware", "torotron_esp32")
        os.makedirs(sketch_dir, exist_ok=True)
        ino_path = os.path.join(sketch_dir, "torotron_esp32.ino")

        try:
            with open(ino_path, "w", encoding="utf-8") as f:
                f.write(self.code_edit.toPlainText())
        except OSError as e:
            self.upload_status_signal.emit(f"Write error: {e}", True)
            return

        # 2. Release serial port so arduino-cli can claim it
        was_connected = getattr(self.mw.serial_mgr, "is_connected", False)
        if was_connected:
            self.upload_status_signal.emit("Releasing serial port...", False)
            self.mw.serial_mgr.disconnect()
            time.sleep(2)

        try:
            # 3. Compile + Upload
            self.upload_status_signal.emit(
                f"Compiling & uploading ({fqbn})… this may take ~30 s", False
            )
            cmd = [
                cli_path,
                "compile",
                "--upload",
                "--port", port,
                "--fqbn", fqbn,
                sketch_dir,
            ]

            self.mw.log(f"CMD: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2-minute hard timeout
            )

            if result.returncode == 0:
                self.upload_status_signal.emit("✅ Upload successful!", False)
                self.mw.log("✅ Firmware uploaded to ESP32-S3 successfully.")
            else:
                err = (result.stderr or result.stdout or "Unknown error").strip()
                # Trim to first meaningful line for status bar
                short_err = err.split("\n")[0][:120]
                self.upload_status_signal.emit(f"❌ {short_err}", True)
                self.mw.log(f"❌ Upload failed:\n{err}")

        except subprocess.TimeoutExpired:
            self.upload_status_signal.emit("❌ Timeout — upload took too long", True)
        except FileNotFoundError:
            self.upload_status_signal.emit("❌ arduino-cli disappeared during upload", True)
        except Exception as e:
            self.upload_status_signal.emit(f"❌ Unexpected error: {e}", True)

        finally:
            # 4. Reconnect serial
            if was_connected:
                self.upload_status_signal.emit("Reconnecting serial…", False)
                time.sleep(4)  # wait for ESP32 reboot
                try:
                    self.mw.serial_mgr.connect(port)
                except Exception:
                    pass
            self.upload_status_signal.emit("Ready.", False)

    # ─────────────────────────────────────────────────────────────────────────
    # arduino-cli missing — friendly dialog
    # ─────────────────────────────────────────────────────────────────────────

    def _show_cli_missing_dialog(self):
        """Shows a helpful dialog with install instructions when cli is missing."""
        self.mw.log("❌ arduino-cli not found. See the install dialog.")

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
        self.status_label.setText(msg)
        if is_error:
            self.status_label.setStyleSheet("color: #ff5555; font-size: 11px;")
        elif "SUCCESS" in msg.upper() or "✅" in msg:
            self.status_label.setStyleSheet("color: #4caf50; font-size: 11px; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #4a90e2; font-size: 10px;")

        if "Ready" in msg:
            self.upload_btn.setEnabled(True)
