from PyQt5 import QtWidgets


class HardwareMixin:
    """Methods for serial port connection and hardware management."""

    def refresh_ports(self, silent=False):
        """Update the list of available COM ports."""
        current = self.port_combo.currentText()
        ports = self.serial_mgr.get_available_ports()
        
        # Avoid clearing if lists are same to prevent flickering
        existing = [self.port_combo.itemText(i) for i in range(self.port_combo.count())]
        if set(ports) == set(existing) and ports:
            return

        self.port_combo.clear()
        self.port_combo.addItems(ports)
        
        # Auto-selection logic
        if ports:
            # Try to restore previous or find ESP32-like device
            found_idx = -1
            for i, p in enumerate(ports):
                if current and p == current:
                    found_idx = i
                    break
                if any(kw in p.upper() for kw in ["CP210", "CH340", "USB SERIAL", "ESP32"]):
                    found_idx = i
            
            if found_idx != -1:
                self.port_combo.setCurrentIndex(found_idx)
            else:
                self.port_combo.setCurrentIndex(0)
        else:
            self.port_combo.addItem("No Ports found")

    def refresh_ports_silently(self):
        """Timer callback to scan ports without logging unless count changes."""
        self.refresh_ports(silent=True)

    def toggle_connection(self):
        """Connect or disconnect from the selected serial port."""
        if not self.serial_mgr.is_connected:
            port = self.port_combo.currentText()
            if port == "No Ports found":
                self.log("Cannot connect: No serial ports detected.")
                return
                
            if self.serial_mgr.connect(port):
                self.connect_btn.setText("Disconnect")
                self.connect_btn.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold;")
            
            # Update Hardware Badge in Program Panel
            if hasattr(self, 'program_tab'):
                self.program_tab.update_hw_badge()
        else:
            self.serial_mgr.disconnect()
            self.connect_btn.setText("Connect")
            self.connect_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
            
            # Update Hardware Badge in Program Panel
            if hasattr(self, 'program_tab'):
                self.program_tab.update_hw_badge()
