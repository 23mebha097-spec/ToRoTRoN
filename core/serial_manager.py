import serial
import serial.tools.list_ports
import threading
import time

class SerialManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.serial_port = None
        self.is_connected = False
        self.baudrate = 115200
        self.port_name = None
        
    def get_available_ports(self):
        """Returns a list of available COM port names."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
        
    def connect(self, port_name, baudrate=115200):
        """Opens the serial connection."""
        try:
            if self.is_connected:
                self.disconnect()
                
            self.serial_port = serial.Serial(port_name, baudrate, timeout=0.1)
            
            # --- ESP32 STABILITY FIX ---
            # Explicitly release DTR/RTS to prevent the board from staying in 'Boot/Download' mode
            self.serial_port.dtr = False
            self.serial_port.rts = False
            
            self.port_name = port_name
            self.baudrate = baudrate
            self.is_connected = True
            self.mw.log_signal.emit(f"Connected to ESP32 on {port_name} (DTR/RTS Released).")
            
            # Start a background listener thread
            self.stop_listener = False
            self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listener_thread.start()
            
            return True
        except Exception as e:
            self.mw.log(f"Failed to connect to {port_name}: {e}")
            self.is_connected = False
            return False
            
    def disconnect(self):
        """Closes the serial connection."""
        self.stop_listener = True
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.mw.log("Disconnected from serial port.")
        
    def _listen_loop(self):
        """Background thread to read incoming messages from ESP32."""
        while not self.stop_listener and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Print ESP32 messages to the main console
                        # Use a prefix to distinguish hardware messages
                        self.mw.log_signal.emit(f"[ESP32]: {line}")
            except Exception:
                break
            time.sleep(0.01)

    def send_command(self, joint_id, angle, speed=0):
        """Sends a joint command to the ESP32: 'joint_id:angle:speed\\n'"""
        if not self.is_connected or not self.serial_port:
            return
            
        try:
            # Format: joint_id:angle:speed\n
            # e.g. shoulder:45.00:10.00\n
            command = f"{joint_id}:{angle:.2f}:{speed:.2f}\n"
            self.mw.log(f"📡 Serial Tx: {command.strip()}")
            self.serial_port.write(command.encode('utf-8'))
        except Exception as e:
            self.mw.log(f"Serial Send Error: {e}")
            self.disconnect()
