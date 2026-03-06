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
            
            # Refresh Simulation Objects list
            self.refresh_sim_objects_list()
            
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

    def refresh_sim_objects_list(self):
        """Clears and re-populates the simulation objects list from the robot model."""
        if not hasattr(self, 'sim_objects_list'):
            return
            
        self.sim_objects_list.clear()
        for name, link in self.robot.links.items():
            if getattr(link, 'is_sim_obj', False):
                item = QtWidgets.QListWidgetItem(name)
                item.setIcon(self.make_sim_obj_icon("#1976d2")) # Blue box icon
                self.sim_objects_list.addItem(item)

    def make_sim_obj_icon(self, color_str):
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtGui.QColor(color_str))
        return QtGui.QIcon(pixmap)

    def on_sim_object_clicked(self, item):
        """Selects and focuses on the sim object in the 3D scene."""
        name = item.text()
        if name in self.canvas.actors:
            self.canvas.select_actor(name)
        
        # Load Pick/Place coordinates into UI
        if name in self.robot.links:
            link = self.robot.links[name]
            
            # Block signals to avoid self-triggering save while loading
            for sb in [self.pick_x, self.pick_y, self.pick_z, self.place_x, self.place_y, self.place_z]:
                sb.blockSignals(True)
            
            ratio = self.canvas.grid_units_per_cm
            self.pick_x.setValue(link.pick_pos[0] / ratio)
            self.pick_y.setValue(link.pick_pos[1] / ratio)
            self.pick_z.setValue(link.pick_pos[2] / ratio)
            
            self.place_x.setValue(link.place_pos[0] / ratio)
            self.place_y.setValue(link.place_pos[1] / ratio)
            self.place_z.setValue(link.place_pos[2] / ratio)
            
            for sb in [self.pick_x, self.pick_y, self.pick_z, self.place_x, self.place_y, self.place_z]:
                sb.blockSignals(False)

    def save_sim_object_coords(self):
        """Saves current spinbox values back to the selected simulation object."""
        current_item = self.sim_objects_list.currentItem()
        if not current_item:
            return
            
        name = current_item.text()
        if name in self.robot.links:
            link = self.robot.links[name]
            ratio = self.canvas.grid_units_per_cm
            link.pick_pos = [self.pick_x.value() * ratio, self.pick_y.value() * ratio, self.pick_z.value() * ratio]
            link.place_pos = [self.place_x.value() * ratio, self.place_y.value() * ratio, self.place_z.value() * ratio]
            # self.log(f"Saved Pick/Place for {name}")
      
    def update_live_ui(self):
        """Updates the Live Point (LP) coordinates and handles Pick-and-Place simulation logic."""
        if not hasattr(self, 'live_x'):
            return
            
        # 1. Identify leaf link (TCP)
        tcp_link = None
        for link in self.robot.links.values():
            if link.parent_joint and not link.child_joints:
                tcp_link = link
                break
        
        if not tcp_link:
            for link in self.robot.links.values():
                if not link.is_base:
                    tcp_link = link
                    break
        
        if tcp_link:
            pos = tcp_link.t_world[:3, 3]
            self.live_x.blockSignals(True)
            self.live_y.blockSignals(True)
            self.live_z.blockSignals(True)
            
            ratio = self.canvas.grid_units_per_cm
            self.live_x.setValue(pos[0] / ratio)
            self.live_y.setValue(pos[1] / ratio)
            self.live_z.setValue(pos[2] / ratio)
            
            self.live_x.blockSignals(False)
            self.live_y.blockSignals(False)
            self.live_z.blockSignals(False)

            # 2. Pick-and-Place Simulation Logic (MAGNET MODE)
            sim_tab = self.simulation_tab
            if hasattr(sim_tab, 'is_sim_active') and sim_tab.is_sim_active:
                self._handle_sim_pick_place(tcp_link, pos, ratio)

    def _handle_sim_pick_place(self, tcp_link, tcp_pos, ratio):
        """Monitors proximity to P1/P2 and manages object attachment."""
        sim_tab = self.simulation_tab
        
        # P1 & P2 in World Coords
        p1 = np.array([sim_tab.pick_x.value(), sim_tab.pick_y.value(), sim_tab.pick_z.value()]) * ratio
        p2 = np.array([sim_tab.place_x.value(), sim_tab.place_y.value(), sim_tab.place_z.value()]) * ratio
        
        THRESHOLD = 2.0 * ratio # 2cm grab radius
        
        # Current selected object in the list
        item = sim_tab.objects_list.currentItem()
        if not item: return
        obj_name = item.text()
        if obj_name not in self.robot.links: return
        obj_link = self.robot.links[obj_name]

        # STATE A: We are NOT gripping, look for P1 (Pick)
        if not sim_tab.gripped_object:
            dist_p1 = np.linalg.norm(tcp_pos - p1)
            if dist_p1 < THRESHOLD:
                self.log(f"🧲 GRIPPED: {obj_name} at P1")
                sim_tab.gripped_object = obj_name
                # Store relative transform from TCP to Object
                inv_tcp = np.linalg.inv(tcp_link.t_world)
                sim_tab.grip_offset = inv_tcp @ obj_link.t_world
                
                # AUTO-CLOSE GRIPPER: Animate any joints with relations
                self._control_gripper_fingers(close=True)
                self.show_toast(f"Gripped {obj_name}", "success")

        # STATE B: We ARE gripping, update object and look for P2 (Place)
        else:
            if sim_tab.gripped_object == obj_name:
                # FOLLOW THE ROBOT
                obj_link.t_offset = tcp_link.t_world @ sim_tab.grip_offset
                # Important: update actor world pos immediately for feedback
                self.canvas.update_transforms(self.robot)
                
                # Check for Place (P2)
                dist_p2 = np.linalg.norm(tcp_pos - p2)
                if dist_p2 < THRESHOLD:
                     self.log(f"📦 PLACED: {obj_name} at P2")
                     sim_tab.gripped_object = None
                     sim_tab.grip_offset = None
                     
                     # AUTO-OPEN GRIPPER
                     self._control_gripper_fingers(close=False)
                     self.show_toast(f"Placed {obj_name}", "success")

    def _control_gripper_fingers(self, close=True):
        """Automatically moves joints that have relations (the 'gripper')."""
        for j_name, joint in self.robot.joints.items():
            # Check if this joint is a 'master' in a relation (likely a finger)
            if j_name in self.robot.joint_relations:
                # Simple logic: close = move toward max limit, open = move toward min
                # You can customize this if you know specific gripper ranges
                target = joint.max_limit if close else joint.min_limit
                
                # Note: We don't animate with time.sleep here because we are in the UI thread 
                # inside a transform update. We just snap it for simulation clarity.
                joint.current_value = target
                # Also move slaves
                for s_id, ratio in self.robot.joint_relations[j_name]:
                    if s_id in self.robot.joints:
                        self.robot.joints[s_id].current_value = target * ratio
                        
        self.robot.update_kinematics()
        self.canvas.update_transforms(self.robot)

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
        # Disable dragging for all tabs except 'Links' (index 0) or 'Simulation' (index 5)
        # This prevents accidental movement while Aligning or Creating Joints
        # In Simulation Mode, we allow dragging but only for 'Simulation Objects' (logic in canvas)
        self.canvas.enable_drag = (index == 0 or index == 5)
        
        widget = self.panel_stack.widget(index)
        if hasattr(widget, 'refresh_links'):
            widget.refresh_links()
        if hasattr(widget, 'update_display'):
            widget.update_display()
        if hasattr(widget, 'refresh_sliders'):
            widget.refresh_sliders()
            
        # Update live point display
        self.update_live_ui()

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
