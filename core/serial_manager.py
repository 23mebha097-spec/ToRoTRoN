import serial
import serial.tools.list_ports
import threading
import time
from collections import defaultdict


ESP32_VIDS = {
    0x303A,  # Espressif native USB (S2/S3/C3)
    0x10C4,  # Silicon Labs CP210x bridge
    0x1A86,  # QinHeng CH340/CH9102 bridge
    0x0403,  # FTDI bridges used by some dev boards
}


class SerialManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.serial_port = None
        self.is_connected = False
        self.baudrate = 115200
        self.port_name = None
        self.last_heartbeat_rx = 0
        self.stop_heartbeat = False
        self.stop_listener = False
        self._write_lock = threading.Lock()
        self._last_sent = {}  # {joint_id: (angle, speed, timestamp)}
        self._min_send_interval_s = 0.02  # 50 Hz per joint max TX rate
        self._angle_deadband_deg = 0.1
        self._speed_deadband = 0.5
        self._rx_counters = defaultdict(int)
        self.last_error = ""
        self._port_meta = {}  # {label: {device, is_esp32, vid, pid}}

    def _log(self, message):
        """Thread-safe log dispatch to MainWindow console."""
        if hasattr(self.mw, "log_signal"):
            self.mw.log_signal.emit(str(message))
        elif hasattr(self.mw, "log"):
            self.mw.log(str(message))

    @staticmethod
    def _normalize_text(value):
        return (value or "").strip().upper()

    def _is_esp32_port_info(self, p):
        vid = getattr(p, "vid", None)
        pid = getattr(p, "pid", None)

        if isinstance(vid, int) and vid in ESP32_VIDS:
            return True

        blob = " ".join([
            self._normalize_text(getattr(p, "description", "")),
            self._normalize_text(getattr(p, "manufacturer", "")),
            self._normalize_text(getattr(p, "product", "")),
            self._normalize_text(getattr(p, "hwid", "")),
        ])
        keywords = ["ESP32", "USB JTAG", "CP210", "CH340", "CH910", "SILICON LABS"]
        return any(k in blob for k in keywords)

    def is_esp32_label(self, label):
        meta = self._port_meta.get(label)
        if meta is not None:
            return bool(meta.get("is_esp32"))

        text = self._normalize_text(label)
        fallback_keywords = ["ESP32", "USB JTAG", "CP210", "CH340", "CH910", "SILICON LABS"]
        return any(k in text for k in fallback_keywords)
        
    def get_available_ports(self):
        """Return UI labels for serial ports; ESP32 candidates are listed first."""
        ports = serial.tools.list_ports.comports()

        entries = []
        self._port_meta = {}

        for p in ports:
            parts = []
            if getattr(p, "description", None) and p.description != "n/a":
                parts.append(p.description)

            vendor = getattr(p, "manufacturer", None)
            product = getattr(p, "product", None)
            extra = " - ".join([x for x in [vendor, product] if x])
            if extra:
                parts.append(extra)

            vid = getattr(p, "vid", None)
            pid = getattr(p, "pid", None)
            if isinstance(vid, int) and isinstance(pid, int):
                parts.append(f"VID:{vid:04X} PID:{pid:04X}")

            details = " | ".join(parts) if parts else "Unknown Device"
            label = f"{p.device} ({details})"
            is_esp = self._is_esp32_port_info(p)
            if is_esp:
                label = f"{p.device} (ESP32 Candidate | {details})"

            entries.append((0 if is_esp else 1, p.device, label))
            self._port_meta[label] = {
                "device": p.device,
                "is_esp32": is_esp,
                "vid": vid,
                "pid": pid,
            }

        entries.sort(key=lambda x: (x[0], x[1]))
        return [entry[2] for entry in entries]
        
    def connect(self, port_name, baudrate=115200):
        """Opens the serial connection. Supports 'COMx' or 'COMx (Desc)' formats."""
        # Strip description if present: "COM6 (USB-Serial)" -> "COM6"
        raw_port = port_name.split("(", 1)[0].strip()
        self.last_error = ""

        if self.is_connected:
            self.disconnect()

        last_exc = None
        for attempt in range(1, 6):
            try:
                self.serial_port = serial.Serial(raw_port, baudrate, timeout=0.05, write_timeout=0.2)

                # --- ESP32 STABILITY FIX ---
                # Explicitly release DTR/RTS to prevent the board from staying in 'Boot/Download' mode.
                # Some flaky USB drivers fail on control-line writes immediately after open.
                try:
                    self.serial_port.dtr = False
                    self.serial_port.rts = False
                except Exception:
                    pass

                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()

                # Store canonical raw COM name (e.g., COM5) for stable matching.
                self.port_name = raw_port
                self.baudrate = baudrate
                self.is_connected = True
                self.last_heartbeat_rx = time.time()
                self._last_sent.clear()
                self._rx_counters.clear()
                self.mw.log_signal.emit(f"Connected to ESP32 on {raw_port} (DTR/RTS Released).")

                # Start a background listener thread
                self.stop_listener = False
                self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self.listener_thread.start()

                # Start Heartbeat thread
                self.stop_heartbeat = False
                self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
                self.heartbeat_thread.start()

                # Initial ping to establish liveness quickly after connect
                self._write_line("PING")
                return True

            except Exception as e:
                last_exc = e
                if self.serial_port and getattr(self.serial_port, "is_open", False):
                    try:
                        self.serial_port.close()
                    except Exception:
                        pass
                self.serial_port = None

                # Retries help with transient USB re-enumeration right after reset/upload.
                if attempt < 5:
                    time.sleep(0.5 + (attempt * 0.15))

        self.is_connected = False
        self.last_error = self._diagnose_connect_error(raw_port, last_exc)
        self._log(f"Failed to connect to {port_name}: {self.last_error}")
        return False

    def _diagnose_connect_error(self, raw_port, exc):
        """Return a user-facing serial connection diagnosis with probable causes."""
        if exc is None:
            return "Unknown serial connection error"

        text = str(exc)
        low = text.lower()
        hints = []

        if "access is denied" in low:
            hints.append("port is busy (Arduino IDE Serial Monitor / another app)")
        if "permissionerror(13" in low and "access is denied" not in low:
            hints.append("USB serial driver/device is unstable or reconnecting")
        if "cannot configure port" in low or "device attached to the system is not functioning" in low:
            hints.append("USB device/driver is in a bad state")
        if "file not found" in low or "could not open port" in low:
            hints.append("port disappeared or COM mapping changed")

        if not hints:
            hints.append("unknown cause")

        hint_text = "; ".join(hints)
        return (
            f"{text}. Likely cause: {hint_text}. "
            f"Try unplug/replug the board, close serial tools, and reconnect {raw_port}."
        )
            
    def disconnect(self):
        """Closes the serial connection."""
        self.stop_listener = True
        self.stop_heartbeat = True
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.is_connected = False
        self._log("Disconnected from serial port.")

    def _write_line(self, line):
        """Thread-safe serial line write with newline termination."""
        if not self.is_connected or not self.serial_port or not self.serial_port.is_open:
            return False
        payload = (line if line.endswith("\n") else f"{line}\n").encode("utf-8")
        with self._write_lock:
            self.serial_port.write(payload)
        return True
        
    def _listen_loop(self):
        """Background thread to read incoming messages from ESP32."""
        while not self.stop_listener and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        if line.startswith("PONG") or "ACK" in line or "READY" in line or line.startswith("BOOT"):
                            self.last_heartbeat_rx = time.time()
                            if line.startswith("PONG"):
                                self._rx_counters["PONG"] += 1
                                continue
                            if line.startswith("ACK"):
                                self._rx_counters["ACK"] += 1
                            
                        # Print ESP32 messages to the main console
                        self.mw.log_signal.emit(f"[ESP32]: {line}")
            except Exception:
                break
            time.sleep(0.01)

    def send_command(self, joint_id, angle, speed=0):
        """Sends a joint command to the ESP32: 'joint_id:angle:speed\\n'"""
        if not self.is_connected or not self.serial_port:
            return
            
        try:
            # Coalesce near-identical high-frequency commands per joint
            now = time.time()
            prev = self._last_sent.get(joint_id)
            if prev:
                prev_angle, prev_speed, prev_ts = prev
                if (
                    abs(angle - prev_angle) <= self._angle_deadband_deg and
                    abs(float(speed) - prev_speed) <= self._speed_deadband and
                    (now - prev_ts) < self._min_send_interval_s
                ):
                    return

            # Format: joint_id:angle:speed\n
            # e.g. shoulder:45.00:10.00\n
            command = f"{joint_id}:{angle:.2f}:{speed:.2f}\n"
            self._write_line(command)
            self._last_sent[joint_id] = (float(angle), float(speed), now)
        except Exception as e:
            self._log(f"Serial Send Error: {e}")
            self.disconnect()

    def _heartbeat_loop(self):
        """Sends a periodic 'PING' command to check if ESP32 is alive."""
        while not self.stop_heartbeat and self.is_connected:
            try:
                if self.serial_port and self.serial_port.is_open:
                    self._write_line("PING")
            except:
                pass
            time.sleep(1.0)

    @property
    def is_alive(self):
        """Returns True if we've heard from the ESP32 in the last 5 seconds."""
        if not self.is_connected: return False
        return (time.time() - self.last_heartbeat_rx) < 5.0
