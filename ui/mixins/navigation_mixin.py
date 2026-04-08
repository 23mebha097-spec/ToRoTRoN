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
        
        # --- BASE PROTECTION RULE: The Base is functionally fixed at (0,0,0) ---
        if link.is_base:
            self.log(f"⚠️ Locked: '{name}' is the Base and its position is frozen.")
            return
        
        if link.parent_joint:
            # Solve for local offset in parent-joint frame
            parent_world = link.parent_joint.parent_link.t_world
            joint_rot = link.parent_joint.get_matrix()
            
            # Child_World = Parent_World @ Joint_Matrix @ Child_Offset
            # => Child_Offset = Inv(Joint_Matrix) @ Inv(Parent_World) @ Matrix
            inv_parent = np.linalg.inv(parent_world)
            inv_joint = np.linalg.inv(joint_rot)
            
            link.t_offset = inv_joint @ inv_parent @ matrix
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
            
            # Switch to Simulation Panel
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
                self.add_sim_object_item(name)

    def add_sim_object_item(self, name):
        """Helper to add a simulation object to the list with a delete button."""
        item = QtWidgets.QListWidgetItem(self.sim_objects_list)
        item.setText(name)
        
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(10, 2, 5, 2)
        layout.setSpacing(8)
        
        # Icon (Blue Box)
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(12, 12)
        pixmap.fill(QtGui.QColor("#1976d2"))
        icon_label.setPixmap(pixmap)
        icon_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)
        
        # Name
        name_label = QtWidgets.QLabel(name)
        name_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #1976d2; border: none;")
        name_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        # Delete Button
        del_btn = QtWidgets.QPushButton()
        del_btn.setIcon(widget.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        del_btn.setIconSize(QtCore.QSize(14, 14))
        del_btn.setFixedSize(28, 28)
        del_btn.setCursor(QtCore.Qt.PointingHandCursor)
        del_btn.setToolTip(f"Delete {name}")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffebee;
            }
        """)
        # Capture name in lambda
        del_btn.clicked.connect(lambda checked, n=name: self.remove_sim_object(n))
        layout.addWidget(del_btn)
        
        item.setSizeHint(QtCore.QSize(0, 36))
        self.sim_objects_list.addItem(item)
        self.sim_objects_list.setItemWidget(item, widget)

    def remove_sim_object(self, name):
        """Permanently removes a simulation object from the workspace."""
        # Confirmation dialog
        reply = QtWidgets.QMessageBox.question(self, 'Delete Object', 
            f"Are you sure you want to delete '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            if name in self.robot.links:
                # 1. Remove from Robot Model
                self.robot.remove_link(name)
                
                # 2. Remove actor from 3D scene
                self.canvas.remove_actor(name)
                
                # 3. Synchronize graphics state
                self.canvas.fixed_actors.discard(name)
                
                # 4. Refresh both simulation and main component lists
                self.refresh_sim_objects_list()
                
                if hasattr(self, 'links_list'):
                    # Manually remove from the main links list widget
                    for i in range(self.links_list.count()):
                        it = self.links_list.item(i)
                        if it and it.text() == name:
                            self.links_list.takeItem(i)
                            break
                
                self.log(f"🗑️ Deleted simulation object: {name}")
                self.show_toast(f"Deleted {name}", "success")
                self.canvas.plotter.render()

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
            
            # --- COMPLIANCE CHECK: Base, Aligned, or Jointed cannot be moved ---
            is_aligned = False
            if hasattr(self, 'alignment_cache'):
                for (p, c), pt in self.alignment_cache.items():
                    if c == name:
                        is_aligned = True; break
            
            is_locked = link.is_base or link.parent_joint or is_aligned
            
            ratio = self.canvas.grid_units_per_cm
            self.pick_x.setValue(link.pick_pos[0] / ratio)
            self.pick_y.setValue(link.pick_pos[1] / ratio)
            self.pick_z.setValue(link.pick_pos[2] / ratio)
            
            self.place_x.setValue(link.place_pos[0] / ratio)
            self.place_y.setValue(link.place_pos[1] / ratio)
            self.place_z.setValue(link.place_pos[2] / ratio)
            
            for sb in [self.pick_x, self.pick_y, self.pick_z, self.place_x, self.place_y, self.place_z]:
                sb.blockSignals(False)
                sb.setEnabled(not is_locked)
                # Visual cue for locked status
                if is_locked:
                    sb.setStyleSheet("background: #f5f5f5; color: #9e9e9e; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; padding: 2px 4px; font-weight: bold;")
                else:
                    color = "#1976d2" if "pick" in str(sb.objectName()).lower() or sb == self.pick_x or sb == self.pick_y or sb == self.pick_z else "#388E3C"
                    sb.setStyleSheet(f"background: white; color: {color}; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; padding: 2px 4px; font-weight: bold;")
            
            # Refresh Property Display
            self.simulation_tab.refresh_object_info(name)

    def save_sim_object_coords(self):
        """Saves current spinbox values back to the selected simulation object."""
        current_item = self.sim_objects_list.currentItem()
        if not current_item:
            return
            
        name = current_item.text()
        if name in self.robot.links:
            link = self.robot.links[name]
            if link.is_base:
                return
            ratio = self.canvas.grid_units_per_cm
            link.pick_pos = [self.pick_x.value() * ratio, self.pick_y.value() * ratio, self.pick_z.value() * ratio]
            link.place_pos = [self.place_x.value() * ratio, self.place_y.value() * ratio, self.place_z.value() * ratio]
            # self.log(f"Saved Pick/Place for {name}")
      
    def update_live_ui(self):
        """Updates the Live Point (LP) coordinates and handles Pick-and-Place simulation logic."""
        if not hasattr(self, 'live_x'):
            return
            
        tcp_link = None
        custom_tcp = getattr(self, 'custom_tcp_name', None)
        if custom_tcp and custom_tcp in self.robot.links:
            tcp_link = self.robot.links[custom_tcp]
        
        if not tcp_link:
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
            # Use Tool Point for accurate LP display
            pos, _, _ = self.get_link_tool_point(tcp_link)
            
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

    def get_link_tool_point(self, link, return_vec=False):
        """
        Calculates the Tool Center Point (TCP) in World and Local coords.
        - If the link has related child joints ('Gripper'), calculates midpoint between fingers.
        - Otherwise, calculates the center-top point of the mesh bounds.
        """
        if not link:
            if return_vec: return np.zeros(3), np.zeros(3), None
            return np.zeros(3), np.zeros(3), 0.0

        # 1. Identify 'Fingers' (ONLY child links of joints explicitly marked as 'Gripper')
        fingers = []
        for joint in link.child_joints:
            if getattr(joint, 'is_gripper', False) and joint.child_link:
                fingers.append(joint.child_link)

        # --- Priority 1: User-Defined Custom TCP (Live Point) ---
        if hasattr(link, 'custom_tcp_offset') and link.custom_tcp_offset is not None:
            local_tool_point = np.array(link.custom_tcp_offset)
            world_tool_point = (link.t_world @ np.append(local_tool_point, 1.0))[:3]
            
            # Use multi-finger gap estimation if available, otherwise 0
            gap = 0.0
            if fingers:
                # Still try to find gap if fingers are present for logic
                pts_world = []
                for f in fingers:
                    if f.mesh:
                        b = f.mesh.bounds
                        c_finger = (b[0] + b[1]) / 2.0
                        pts_world.append((f.t_world @ np.append(c_finger, 1.0))[:3])
                
                if len(pts_world) >= 2:
                    for i in range(len(pts_world)):
                        for j in range(i + 1, len(pts_world)):
                            gap = max(gap, np.linalg.norm(pts_world[i] - pts_world[j]))
            
            if return_vec:
                return world_tool_point, local_tool_point, None
            return world_tool_point, local_tool_point, gap

        # 2. Case: Multiple Fingers (Midpoint TCP Fallback)
        if len(fingers) >= 2:
            pts_world = []
            pts_local = []
            for f in fingers:
                if f.mesh:
                    # LOCAL center of finger mesh in finger's own frame
                    b = f.mesh.bounds
                    c_finger = (b[0] + b[1]) / 2.0
                    
                    # Store world point
                    w_pt = (f.t_world @ np.append(c_finger, 1.0))[:3]
                    pts_world.append(w_pt)
                    
                    # Store point in hand's local frame
                    inv_hand = np.linalg.inv(link.t_world)
                    pt_in_hand = (inv_hand @ np.append(w_pt, 1.0))[:3]
                    pts_local.append(pt_in_hand)
            
            if pts_local:
                local_tool_point = np.mean(pts_local, axis=0) # Midpoint in HAND frame
                world_tool_point = (link.t_world @ np.append(local_tool_point, 1.0))[:3]
                
                # Identify the two most distant fingers for primary span
                max_span_centers = 0.0
                best_indices = (0, 1)
                best_vec = np.array([1.0, 0.0, 0.0])
                
                for i in range(len(pts_world)):
                    for j in range(i + 1, len(pts_world)):
                        v = pts_world[i] - pts_world[j]
                        d = np.linalg.norm(v)
                        if d > max_span_centers:
                            max_span_centers = d
                            best_vec = v
                            best_indices = (i, j)
                if np.linalg.norm(best_vec) > 1e-9:
                    best_vec /= np.linalg.norm(best_vec)

                # --- NEW: ACCOUNT FOR FINGER DEPTH & APPROACH AXIS ---
                # We need to know how far the fingers reach to "cover" the object.
                # Convention: approach axis is the Hand's Z-axis (pointing 'forward').
                approach_axis = link.t_world[:3, 2]
                if np.linalg.norm(approach_axis) > 1e-9:
                    approach_axis /= np.linalg.norm(approach_axis)

                finger_depth = 0.0
                depth_samples = []
                for f in fingers:
                    if f.mesh:
                        # Project finger mesh vertices onto the approach axis
                        v_w = (f.t_world[:3, :3] @ f.mesh.vertices.T).T + f.t_world[:3, 3]
                        p_depth = v_w @ approach_axis
                        depth_samples.append(np.ptp(p_depth))
                
                if depth_samples:
                    finger_depth = np.max(depth_samples)

                # --- NEW: ACCOUNT FOR FINGER THICKNESS (Real Gap) ---
                # The 'max_span' should be the CLEAR SPACE between fingers, not center-to-center.
                # We project each finger's mesh onto the span axis to find the inner bounds.
                real_gap = max_span_centers
                if best_indices[0] < len(fingers) and best_indices[1] < len(fingers):
                    f1, f2 = fingers[best_indices[0]], fingers[best_indices[1]]
                    
                    # Project meshes onto best_vec
                    if f1.mesh and f2.mesh:
                        # f1 vertices in world
                        v1_w = (f1.t_world[:3, :3] @ f1.mesh.vertices.T).T + f1.t_world[:3, 3]
                        v2_w = (f2.t_world[:3, :3] @ f2.mesh.vertices.T).T + f2.t_world[:3, 3]
                        
                        p1 = v1_w @ best_vec
                        p2 = v2_w @ best_vec
                        
                        # The gap is the distance between the closest points of the two ranges
                        # range1: [min(p1), max(p1)], range2: [min(p2), max(p2)]
                        # Since best_vec points from f2 to f1 (v = pts[i]-pts[j]),
                        # range1 is further along best_vec. So gap = min(p1) - max(p2)
                        real_gap = max(0.0, np.min(p1) - np.max(p2))

                if return_vec:
                    # Provide all finger positions relative to hand for complex width calculation
                    return world_tool_point, local_tool_point, {
                        "fingers_world": pts_world, 
                        "primary_axis": best_vec, 
                        "approach_axis": approach_axis,
                        "finger_depth": finger_depth,
                        "real_gap": real_gap,
                        "centers_span": max_span_centers
                    }
                
                return world_tool_point, local_tool_point, real_gap

        
        # 3. Fallback: Standard leaf or mesh-top point
        if not link.mesh:
            res = (link.t_world[:3, 3], np.zeros(3), None)
            return res if return_vec else (res[0], res[1], 0.0)
            
        bounds = link.mesh.bounds 
        center_x = (bounds[0][0] + bounds[1][0]) / 2.0
        center_y = (bounds[0][1] + bounds[1][1]) / 2.0
        top_z = bounds[1][2]
        
        local_tool_point = np.array([center_x, center_y, top_z])
        world_tool_point = (link.t_world @ np.append(local_tool_point, 1.0))[:3]
        
        if return_vec:
            return world_tool_point, local_tool_point, None
        return world_tool_point, local_tool_point, None


    def _handle_sim_pick_place(self, tcp_link, tcp_pos, ratio):
        """Monitors proximity to P1/P2 and manages object attachment using the Tool Point."""
        sim_tab = self.simulation_tab
        
        # Calculate the actual Tool Point (Live Point) and Finger Gap
        tool_pos, tool_local, gap_dist = self.get_link_tool_point(tcp_link)
        
        # P1 & P2 in World Coords
        p1 = np.array([sim_tab.pick_x.value(), sim_tab.pick_y.value(), sim_tab.pick_z.value()]) * ratio
        p2 = np.array([sim_tab.place_x.value(), sim_tab.place_y.value(), sim_tab.place_z.value()]) * ratio
        
        # DYNAMIC THRESHOLD based on gap or CAD size
        if gap_dist:
            THRESHOLD = (gap_dist / 2.0) + (1.0 * ratio) # Gap radius + 1cm buffer
        else:
            THRESHOLD = 2.5 * ratio 
        
        # Current selected object in the list
        item = sim_tab.objects_list.currentItem()
        if not item: return
        obj_name = item.text()
        if obj_name not in self.robot.links: return
        obj_link = self.robot.links[obj_name]
        
        # --- COMPLIANCE CHECK ---
        is_aligned = False
        if hasattr(self, 'alignment_cache'):
            for (p, c), pt in self.alignment_cache.items():
                if c == obj_name: is_aligned = True; break
        if obj_link.is_base or obj_link.parent_joint or is_aligned: return

        # STATE A: We are NOT gripping, look for P1 (Pick)
        if not sim_tab.gripped_object:
            dist_p1 = np.linalg.norm(tool_pos - p1)
            
            # FIT CHECK: If using fingers, check if object is too wide
            if gap_dist and obj_link.mesh:
                obj_size = np.max(obj_link.mesh.bounds[1] - obj_link.mesh.bounds[0])
                if obj_size > gap_dist and dist_p1 < 5.0 * ratio:
                    self.log(f"⚠ Warning: {obj_name} is too large for the current finger gap!")
            
            # Auto-Open gripper while approaching P1
            if dist_p1 < 10.0 * ratio:
                self._control_gripper_fingers(close=False)
            
            if dist_p1 < THRESHOLD:
                self.log(f"🧲 GRIPPED: {obj_name} at P1")
                sim_tab.gripped_object = obj_name
                # Store relative transform from TCP Frame to Object
                inv_tcp = np.linalg.inv(tcp_link.t_world)
                sim_tab.grip_offset = inv_tcp @ obj_link.t_world
                
                # AUTO-CLOSE GRIPPER
                self._control_gripper_fingers(close=True)
                self.show_toast(f"Gripped {obj_name}", "success")

        # STATE B: We ARE gripping, update object and look for P2 (Place)
        else:
            if sim_tab.gripped_object == obj_name:
                # FOLLOW THE ROBOT
                obj_link.t_offset = tcp_link.t_world @ sim_tab.grip_offset
                self.canvas.update_transforms(self.robot)
                
                # Refresh property display (it's moving!)
                sim_tab.refresh_object_info(obj_name)
                
                # Check for Place (P2)
                dist_p2 = np.linalg.norm(tool_pos - p2)
                if dist_p2 < THRESHOLD:
                     self.log(f"📦 PLACED: {obj_name} at P2")
                     sim_tab.gripped_object = None
                     sim_tab.grip_offset = None
                     
                     # AUTO-OPEN GRIPPER
                     self._control_gripper_fingers(close=False)
                     self.show_toast(f"Placed {obj_name}", "success")
                     
                     # STOP SIMULATION
                     sim_tab.start_btn.setChecked(False)
                     sim_tab.toggle_pick_place_sim(False)

    def _compute_finger_gap(self):
        """
        Measures the current distance between finger tips (world space).
        Returns gap in canvas units, or None if not a multi-finger gripper.
        """
        tcp_link = None
        # Find the TCP / Hand link using existing helper
        if hasattr(self, 'simulation_tab'):
            tcp_link = self.simulation_tab._get_tcp_link()
        if not tcp_link:
            return None

        _, _, gap = self.get_link_tool_point(tcp_link)
        return gap  # canvas units, or None

    def _control_gripper_fingers(self, close=True, target_gap_world=None, apply=True):
        """
        Moves gripper master joints to open/close the fingers.

        Args:
            close (bool): True = close fully, False = open fully.
            target_gap_world (float | None): If provided, use binary search
                to find the joint angle that produces this gap (canvas units).
            apply (bool): If True, sets joint values instantly. If False,
                returns a dict of {joint_name: target_angle}.
        """
        master_joints = [
            j for j_name, j in self.robot.joints.items()
            if getattr(j, 'is_gripper', False) and j_name in self.robot.joint_relations
        ]

        if not master_joints:
            return {} if not apply else None

        targets = {}

        # ── Case A: Precise gap targeting via bisection ──────────────────────
        if target_gap_world is not None:
            # Snapshot current values so we can revert during/after bisection
            saved = {j.name: j.current_value for j in master_joints}

            for joint in master_joints:
                lo, hi = joint.min_limit, joint.max_limit
                best_mid = joint.current_value

                for _ in range(20):
                    mid = (lo + hi) / 2.0
                    joint.current_value = mid
                    # Propagate slaves for measurement
                    for s_id, ratio in self.robot.joint_relations[joint.name]:
                        if s_id in self.robot.joints:
                            self.robot.joints[s_id].current_value = mid * ratio
                    self.robot.update_kinematics()

                    gap_now = self._compute_finger_gap()
                    if gap_now is None: break

                    if gap_now > target_gap_world:
                        lo = mid
                    else:
                        hi = mid
                    best_mid = mid

                targets[joint.name] = best_mid

            # Revert to original state (we only wanted to find the targets)
            for j in master_joints:
                j.current_value = saved[j.name]
                for s_id, ratio in self.robot.joint_relations[j.name]:
                    if s_id in self.robot.joints:
                        self.robot.joints[s_id].current_value = saved[j.name] * ratio
            self.robot.update_kinematics()

            if apply:
                for j_name, val in targets.items():
                    self.robot.joints[j_name].current_value = val
                    for s_id, ratio in self.robot.joint_relations[j_name]:
                        if s_id in self.robot.joints:
                            self.robot.joints[s_id].current_value = val * ratio
                self.robot.update_kinematics()
                self.canvas.update_transforms(self.robot)
                return None
            return targets

        # ── Case B: Full open / close ─────────────────────────────────────────
        for joint in master_joints:
            target = joint.max_limit if close else joint.min_limit
            targets[joint.name] = target
            if apply:
                joint.current_value = target
                for s_id, ratio in self.robot.joint_relations[joint.name]:
                    if s_id in self.robot.joints:
                        self.robot.joints[s_id].current_value = target * ratio

        if apply:
            self.robot.update_kinematics()
            self.canvas.update_transforms(self.robot)
            return None
        return targets

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
        # Disable dragging for all tabs except 'Links' or 'Simulation'
        is_links = index == self.panel_stack.indexOf(self.links_tab)
        is_sim = index == self.panel_stack.indexOf(self.simulation_tab)
        self.canvas.enable_drag = (is_links or is_sim)

        # Toggle Gripper Surface button (only visible in Joint Mode)
        if hasattr(self, 'gripper_surface_btn'):
            self.gripper_surface_btn.setVisible(index == self.panel_stack.indexOf(self.joint_tab))

        # Identify current widget and trigger refreshes
        widget = self.panel_stack.widget(index)
        if not widget: return

        # Refresh joint list if entering Gripper tab
        if hasattr(self, 'gripper_tab') and widget == self.gripper_tab:
            self.gripper_tab.refresh_joints()
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
