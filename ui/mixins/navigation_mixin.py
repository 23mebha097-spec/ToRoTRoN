from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np

from core.firmware_gen import generate_esp32_firmware


class ToastNotification(QtWidgets.QFrame):
    """Animated toast notification that slides in from bottom-right and auto-fades."""
    
    COLORS = {
        'success': ('#4caf50', '✓'),
        'error': ('#d32f2f', '✗'),
        'warning': ('#ff9800', '⚠'),
        'info': ('#1976d2', 'ℹ'),
    }
    
    def __init__(self, parent, message, toast_type='info', duration=3000):
        super().__init__(parent)
        color, icon = self.COLORS.get(toast_type, self.COLORS['info'])
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                border: none;
            }}
        """)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)
        
        icon_label = QtWidgets.QLabel(icon)
        icon_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; background: transparent;")
        layout.addWidget(icon_label)
        
        text_label = QtWidgets.QLabel(message)
        text_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        text_label.setWordWrap(True)
        layout.addWidget(text_label, 1)
        
        self.setFixedWidth(320)
        self.adjustSize()
        self.setFixedHeight(max(self.sizeHint().height(), 44))
        
        # Position off-screen (bottom-right)
        self.target_y = parent.height() - self.height() - 20
        self.move(parent.width() - self.width() - 20, parent.height())
        self.show()
        self.raise_()
        
        # Slide-in animation
        self.slide_anim = QtCore.QPropertyAnimation(self, b"pos")
        self.slide_anim.setDuration(300)
        self.slide_anim.setStartValue(self.pos())
        self.slide_anim.setEndValue(QtCore.QPoint(parent.width() - self.width() - 20, self.target_y))
        self.slide_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.slide_anim.start()
        
        # Fade-out after duration
        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._start_fade)
        self.fade_timer.start(duration)
    
    def _start_fade(self):
        self.effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.fade_anim = QtCore.QPropertyAnimation(self.effect, b"opacity")
        self.fade_anim.setDuration(400)
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.setEasingCurve(QtCore.QEasingCurve.InCubic)
        self.fade_anim.finished.connect(self.deleteLater)
        self.fade_anim.start()


class NavigationMixin:
    """Methods for panel switching, simulation, speed, terminal, styling, and code generation."""

    def on_deselect(self):
        """Clears list selections when 3D selection is cancelled (Esc)."""
        self.links_list.clearSelection()
        self.links_list.setCurrentItem(None)
        self.set_base_btn.setText("Set as Base")
        
        # Reset Align Tool selection state
        self.align_tab.reset_panel()

    def on_focus_base(self):
        if not self.robot.base_link:
            self.log("No Base set to focus on.")
            return
        
        base_name = self.robot.base_link.name
        if base_name in self.canvas.actors:
            actor = self.canvas.actors[base_name]
            bounds = actor.GetBounds()
            self.canvas.focus_on_bounds(bounds)
            self.log(f"Focused camera on Base: {base_name}")

    def sync_link_transform(self, name, matrix):
        """Saves a 3D visual transformation back to the robot link model."""
        if name not in self.robot.links:
            return
            
        link = self.robot.links[name]
        
        # We need to save the new transform as 't_offset'
        # If the link has a parent, we must save the offset RELATIVE to that parent
        if link.parent_joint:
            parent_world = link.parent_joint.parent_link.t_world
            joint_rot = link.parent_joint.get_matrix()
            
            # T_world = T_parent_world @ T_offset @ T_joint_rot
            # => T_offset = Inv(T_parent_world) @ T_world @ Inv(T_joint_rot)
            inv_parent = np.linalg.inv(parent_world)
            inv_joint = np.linalg.inv(joint_rot)
            
            link.t_offset = inv_parent @ matrix @ inv_joint
        else:
            # It's a root/floating link, offset is absolute world position
            link.t_offset = matrix
            
        self.robot.update_kinematics()
        self.update_link_colors()
        self.log(f"Synced coordinates for: {name}")
        # Re-run kinematics to ensure the whole branch moves correctly
        self.robot.update_kinematics()

    def switch_panel(self, index):
        self.panel_stack.setCurrentIndex(index)
        
        # Update button styles
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1976d2;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-size: 13px;
                        font-weight: bold;
                        padding: 6px 18px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f5f5f5;
                        color: #424242;
                        border: none;
                        border-radius: 6px;
                        font-size: 13px;
                        font-weight: bold;
                        padding: 6px 18px;
                    }
                    QPushButton:hover { background-color: #e3f2fd; color: #1976d2; }
                """)

    def toggle_simulation(self, checked):
        """Toggles between Edit Mode and Simulation Mode."""
        if checked:
            # Enter Simulation Mode
            self.log("Entering Simulation Mode...")
            
            # Hide Navigation Bar
            self.findChild(QtWidgets.QWidget, "nav_bar_widget").setVisible(False)
            
            # Switch to Simulation Panel (Index 5)
            self.panel_stack.setCurrentWidget(self.simulation_tab)
            self.simulation_tab.refresh_joints()
            
            # Disable other controls if needed
            self.save_btn.setEnabled(False)
            self.load_btn.setEnabled(False)
            
        else:
            # Exit Simulation Mode
            self.log("Exiting Simulation Mode...")
            
            # Show Navigation Bar
            self.findChild(QtWidgets.QWidget, "nav_bar_widget").setVisible(True)
            
            # Switch back to previous panel
            self.switch_panel(0)
            
            # Enable controls
            self.save_btn.setEnabled(True)
            self.load_btn.setEnabled(True)
            
            # Remove any speed overlay from canvas
            self.canvas.plotter.remove_actor("speed_overlay")
            # Clear rotation disc overlays and ghost trails
            self.canvas.clear_rotation_discs()
            self.canvas.clear_joint_ghosts()
            self.canvas.plotter.render()

    def on_speed_change(self, value):
        self.current_speed = value
        # Sync slider and spinbox without infinite loop
        if self.speed_slider.value() != value:
            self.speed_slider.blockSignals(True)
            self.speed_slider.setValue(value)
            self.speed_slider.blockSignals(False)
        if self.speed_spin.value() != value:
            self.speed_spin.blockSignals(True)
            self.speed_spin.setValue(value)
            self.speed_spin.blockSignals(False)
        self.show_speed_overlay()

    def show_speed_overlay(self):
        """Displays current speed percentage on the 3D canvas temporarily"""
        text = f"Speed: {self.current_speed}%"
        self.canvas.plotter.add_text(
            text, 
            position='lower_right', 
            font_size=12, 
            color='#1976d2', 
            name="speed_overlay"
        )
        self.canvas.plotter.render()

    def on_tab_changed(self, index):
        # Disable dragging for all tabs except 'Links' (index 0)
        # This prevents accidental movement while Aligning or Creating Joints
        self.canvas.enable_drag = (index == 0)
        
        widget = self.panel_stack.widget(index)
        if hasattr(widget, 'refresh_links'):
            widget.refresh_links()
        if hasattr(widget, 'update_display'):
            widget.update_display()
        if hasattr(widget, 'refresh_sliders'):
            widget.refresh_sliders()

    def log(self, text):
        """Logs a message to the terminal with color-coded formatting."""
        import html as html_mod
        safe = html_mod.escape(str(text))
        
        # Determine color and prefix
        lower = safe.lower()
        if any(k in lower for k in ['error', '❌', 'fail', 'missing dependency']):
            color = '#f44336'
            prefix = '<span style="color:#f44336;">✗</span>'
        elif any(k in lower for k in ['success', 'finished', 'loaded', 'saved', 'ready', '✅']):
            color = '#4caf50'
            prefix = '<span style="color:#4caf50;">✓</span>'
        elif any(k in lower for k in ['warning', '⚠', 'skip', 'caution']):
            color = '#ff9800'
            prefix = '<span style="color:#ff9800;">⚠</span>'
        elif any(k in lower for k in ['📡', '🧪', '⚡', 'uploading', 'running', 'simulation', 'generating']):
            color = '#42a5f5'
            prefix = '<span style="color:#42a5f5;">›</span>'
        else:
            color = '#d4d4d4'
            prefix = '<span style="color:#757575;">›</span>'
        
        html = f'{prefix} <span style="color:{color};">{safe}</span>'
        self.console.append(html)
        
        # Auto-show terminal on errors
        if '#f44336' in color and not self.terminal_btn.isChecked():
            self.terminal_btn.setChecked(True)
            self.toggle_terminal()
    
    def toggle_terminal(self):
        """Show/hide the terminal console."""
        if self.terminal_btn.isChecked():
            self.console.setVisible(True)
            self.right_splitter.setSizes([500, 250])
        else:
            self.console.setVisible(False)
            self.right_splitter.setSizes([800, 0])

    def on_generate_code(self):
        """Generates ESP32 code and populates the sidebar panel."""
        if not self.robot.joints:
            self.log("⚠️ No joints defined! Add some joints first.")
            self.show_toast("No joints defined yet", "warning")
            return
            
        code = generate_esp32_firmware(self.robot, default_speed=self.current_speed)
        self.code_drawer.set_code(code)
        
        # Expand the splitter to show the code panel (Width 400 suggested)
        self.code_drawer.show()
        self.main_splitter.setSizes([350, 450, 400])
        
        self.log("⚡ ESP32 Code Generated in Sidebar.")
        self.show_toast("Firmware built successfully", "success")

    def show_toast(self, message, toast_type='info', duration=3000):
        """Show an animated toast notification at the bottom-right of the window."""
        ToastNotification(self, message, toast_type, duration)

    def apply_styles(self):
        # Premium light theme with blue, white, black, and grey
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f5f5f5;
                color: #212121;
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                font-size: 18px;
            }
            QLabel {
                font-size: 18px;
            }
            QTabWidget::pane {
                border: 1px solid #bbb;
                background-color: white;
            }
            QTabBar::tab {
                background: #e0e0e0;
                padding: 10px;
                border: 1px solid #bbb;
                color: #212121;
            }
            QTabBar::tab:selected {
                background: #1976d2;
                color: white;
            }
            QPushButton {
                background-color: white;
                border: 2px solid #e0e0e0;
                padding: 10px 15px;
                border-radius: 8px;
                color: #212121;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: white;
                color: #1976d2;
                border: 2px solid #1976d2;
            }
            QPushButton:pressed {
                background-color: #e3f2fd;
                color: #1976d2;
                border: 2px solid #1976d2;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #9e9e9e;
                border: 2px solid #e0e0e0;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #bbb;
                color: #212121;
            }
            QTextEdit {
                background-color: white;
                color: #1565c0;
                font-family: 'Consolas', monospace;
                border: 1px solid #bbb;
            }
            QSplitter::handle {
                background-color: #bbb;
            }
            QSplitter::handle:horizontal:hover, QSplitter::handle:vertical:hover {
                background-color: #1976d2;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #212121;
                selection-background-color: #1976d2;
            }
        """)
