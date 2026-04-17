from PyQt5 import QtWidgets


class HardwareMixin:
    """Methods for serial port connection and hardware management."""

    @staticmethod
    def _raw_port(port_text: str) -> str:
        if not port_text:
            return ""
        return port_text.split("(", 1)[0].strip().upper()

    def _safe_log(self, message: str):
        """Log only after main console is initialized during UI bootstrap."""
        if hasattr(self, "console"):
            self.log(message)

    def _set_connection_button_ui(self, connected: bool):
        """Keep top-bar connection button style/text in sync with serial state."""
        if connected:
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setStyleSheet(
                "background-color: #2e7d32; color: white; font-weight: bold; border-radius: 6px; padding: 8px 18px; font-size: 13px;"
            )
            self.port_combo.setEnabled(False)
        else:
            self.connect_btn.setText("Connect")
            self.connect_btn.setStyleSheet(
                "background-color: #d32f2f; color: white; font-weight: bold; border-radius: 6px; padding: 8px 18px; font-size: 13px;"
            )
            self.port_combo.setEnabled(True)

    @staticmethod
    def _is_esp32_like_port(port_text: str) -> bool:
        if not port_text:
            return False
        text = port_text.upper()
        keywords = [
            "ESP32",
            "CP210",
            "CH340",
            "USB SERIAL",
            "USB JTAG",
            "SILICON LABS",
            "UART",
        ]
        return any(keyword in text for keyword in keywords)

    def _is_esp32_port(self, port_text: str) -> bool:
        """Prefer metadata-based ESP32 detection from SerialManager; fallback to text matching."""
        if hasattr(self.serial_mgr, "is_esp32_label"):
            try:
                return self.serial_mgr.is_esp32_label(port_text)
            except Exception:
                pass
        return self._is_esp32_like_port(port_text)

    def _best_port_index(self, ports, current_text, connected_port_text):
        """Pick best UI selection: connected port > previous port > ESP32-like > first."""
        if not ports:
            return -1

        connected_raw = self._raw_port(connected_port_text)
        current_raw = self._raw_port(current_text)

        if connected_raw:
            for idx, label in enumerate(ports):
                if self._raw_port(label) == connected_raw:
                    return idx

        if current_raw:
            for idx, label in enumerate(ports):
                if self._raw_port(label) == current_raw:
                    return idx

        for idx, port in enumerate(ports):
            if self._is_esp32_port(port):
                return idx

        return 0

    def refresh_ports(self, silent=False):
        """Update the list of available COM ports."""
        current = self.port_combo.currentText()
        ports = self.serial_mgr.get_available_ports()
        connected_port = self.serial_mgr.port_name if self.serial_mgr.is_connected else ""
        port_raw_set = {self._raw_port(p) for p in ports}
        connected_raw = self._raw_port(connected_port)
        
        # Avoid clearing if lists are same to prevent flickering
        existing = [self.port_combo.itemText(i) for i in range(self.port_combo.count())]
        if set(ports) == set(existing) and ports:
            self._set_connection_button_ui(self.serial_mgr.is_connected)

            # If connected and the device disappears, auto-disconnect to prevent stale state.
            if self.serial_mgr.is_connected and connected_raw and connected_raw not in port_raw_set:
                self.serial_mgr.disconnect()
                self._set_connection_button_ui(False)
                if not silent:
                    self._safe_log("ESP32 disconnected (port no longer available).")
                if hasattr(self, "program_tab"):
                    self.program_tab.update_hw_badge()
            return

        self.port_combo.clear()
        if ports:
            self.port_combo.addItems(ports)
        
        # Auto-selection logic
        if ports:
            best_idx = self._best_port_index(ports, current, connected_port)
            self.port_combo.setCurrentIndex(best_idx)

            if not silent:
                selected = self.port_combo.currentText()
                if self._is_esp32_port(selected):
                    self._safe_log(f"ESP32 detected: {selected}")
                else:
                    self._safe_log(f"Serial port detected: {selected}")
        else:
            self.port_combo.addItem("No ESP32/Serial device detected")

        # If connected and selected port disappears, disconnect and update UI.
        if self.serial_mgr.is_connected and connected_raw and connected_raw not in port_raw_set:
            self.serial_mgr.disconnect()
            self._set_connection_button_ui(False)
            if not silent:
                self._safe_log("ESP32 disconnected (port no longer available).")
            if hasattr(self, "program_tab"):
                self.program_tab.update_hw_badge()
        else:
            self._set_connection_button_ui(self.serial_mgr.is_connected)

    def refresh_ports_silently(self):
        """Timer callback to scan ports without logging unless count changes."""
        self.refresh_ports(silent=True)

    def toggle_connection(self):
        """Connect or disconnect from the selected serial port."""
        if not self.serial_mgr.is_connected:
            port = self.port_combo.currentText()
            if not port or "detected" in port.lower():
                self.log("Cannot connect: No serial ports detected.")
                return
                
            if self.serial_mgr.connect(port):
                self._set_connection_button_ui(True)
            
            # Update Hardware Badge in Program Panel
            if hasattr(self, 'program_tab'):
                self.program_tab.update_hw_badge()
        else:
            self.serial_mgr.disconnect()
            self._set_connection_button_ui(False)
            
            # Update Hardware Badge in Program Panel
            if hasattr(self, 'program_tab'):
                self.program_tab.update_hw_badge()
