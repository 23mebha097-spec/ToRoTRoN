from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np

class TypeOnlyDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def stepBy(self, steps): pass
    def wheelEvent(self, event): event.ignore()

class SimulationPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.sliders = {}
        self.matrix_labels = {}
        self.init_ui()

    def init_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        title = QtWidgets.QLabel("SIMULATION MODE")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #1976d2; margin-bottom: 10px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(title)
        
        # --- TAB NAVIGATION ---
        tab_layout = QtWidgets.QHBoxLayout()
        tab_layout.setSpacing(10)
        
        self.joints_btn = self.create_tab_button("Joints", "assets/panel.png")
        self.matrices_btn = self.create_tab_button("Matrices", "assets/matrices.png")
        self.objects_btn = self.create_tab_button("Objects", "assets/simulation.png")
        
        self.joints_btn.clicked.connect(lambda: self.switch_view(0))
        self.matrices_btn.clicked.connect(lambda: self.switch_view(1))
        self.objects_btn.clicked.connect(lambda: self.switch_view(2))
        
        tab_layout.addWidget(self.joints_btn)
        tab_layout.addWidget(self.matrices_btn)
        tab_layout.addWidget(self.objects_btn)
        self.layout.addLayout(tab_layout)
        
        # --- STACKED VIEW ---
        self.stack = QtWidgets.QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # 1. Joints View (Sliders)
        self.joints_view = QtWidgets.QWidget()
        self.joints_layout = QtWidgets.QVBoxLayout(self.joints_view)
        self.joints_layout.setContentsMargins(0,0,0,0)
        
        # Scroll Area for sliders
        scroll_joints = QtWidgets.QScrollArea()
        scroll_joints.setWidgetResizable(True)
        scroll_joints.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_layout.setSpacing(15)
        
        scroll_joints.setWidget(self.scroll_content)
        self.joints_layout.addWidget(scroll_joints)
        self.stack.addWidget(self.joints_view)
        
        # 2. Matrices View
        self.matrices_view = QtWidgets.QWidget()
        self.matrices_layout = QtWidgets.QVBoxLayout(self.matrices_view)
        self.matrices_layout.setContentsMargins(0,0,0,0)
        
        scroll_matrices = QtWidgets.QScrollArea()
        scroll_matrices.setWidgetResizable(True)
        scroll_matrices.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.matrices_content = QtWidgets.QWidget()
        self.matrices_scroll_layout = QtWidgets.QVBoxLayout(self.matrices_content)
        self.matrices_scroll_layout.setAlignment(QtCore.Qt.AlignTop)
        self.matrices_scroll_layout.setSpacing(15)
        
        scroll_matrices.setWidget(self.matrices_content)
        self.matrices_layout.addWidget(scroll_matrices)
        self.stack.addWidget(self.matrices_view)

        # 3. Simulation Objects View (Consolidated from floating panel)
        self.objects_view = QtWidgets.QWidget()
        self.objects_layout = QtWidgets.QVBoxLayout(self.objects_view)
        self.objects_layout.setContentsMargins(0, 5, 0, 0)
        self.objects_layout.setSpacing(10)

        # Header Buttons
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QVBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.import_btn = QtWidgets.QPushButton("📦 Import Object")
        self.import_btn.setFixedHeight(45)
        self.import_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #1976d2;
                border: 2px solid #1976d2;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #e3f2fd; }
        """)
        self.import_btn.clicked.connect(self.main_window.import_mesh)
        btn_layout.addWidget(self.import_btn)

        self.update_btn = QtWidgets.QPushButton("🔄 Update Position")
        self.update_btn.setFixedHeight(45)
        self.update_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.update_btn.setToolTip("Automatically move the selected object to P1 coordinates")
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #388e3c;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2e7d32; }
        """)
        self.update_btn.clicked.connect(self.update_object_position)
        btn_layout.addWidget(self.update_btn)

        self.start_btn = QtWidgets.QPushButton("🚀 Start Simulation")
        self.start_btn.setFixedHeight(45)
        self.start_btn.setCheckable(True)
        self.start_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.start_btn.setToolTip("Enable automatic pick-and-place tracking between P1 and P2")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #fdd835;
                color: #212121;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:checked {
                background-color: #ff9800;
                color: white;
            }
            QPushButton:hover { background-color: #fbc02d; }
        """)
        self.start_btn.clicked.connect(self.toggle_pick_place_sim)
        btn_layout.addWidget(self.start_btn)

        self.objects_layout.addWidget(btn_container)

        # Simulation State
        self.is_sim_active = False
        self.gripped_object = None
        self.grip_offset = None # Relative transform

        # Objects List
        list_label = QtWidgets.QLabel("Simulation Objects:")
        list_label.setStyleSheet("font-weight: bold; color: #424242; font-size: 13px;")
        self.objects_layout.addWidget(list_label)

        self.objects_list = QtWidgets.QListWidget()
        self.objects_list.setFixedHeight(180)
        self.objects_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 6px;
                background: white;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background: #e3f2fd; color: #1976d2; }
        """)
        self.objects_list.itemClicked.connect(self.main_window.on_sim_object_clicked)
        self.objects_layout.addWidget(self.objects_list)

        # Coordinate Grid
        coord_container = QtWidgets.QWidget()
        coord_layout = QtWidgets.QVBoxLayout(coord_container)
        coord_layout.setContentsMargins(5, 5, 5, 5)
        coord_layout.setSpacing(5)

        points_grid = QtWidgets.QGridLayout()
        points_grid.setSpacing(6)

        # Exposing widgets to main_window for Mixin access
        self.main_window.sim_objects_list = self.objects_list

        # P1 Row
        p1_lbl = QtWidgets.QLabel("P1")
        p1_lbl.setStyleSheet("font-weight: bold; color: #1976d2; font-size: 13px;")
        self.pick_x = self.create_coord_sb("#1976d2")
        self.pick_y = self.create_coord_sb("#1976d2")
        self.pick_z = self.create_coord_sb("#1976d2")
        
        points_grid.addWidget(p1_lbl, 0, 0)
        points_grid.addWidget(self.pick_x, 0, 1)
        points_grid.addWidget(self.pick_y, 0, 2)
        points_grid.addWidget(self.pick_z, 0, 3)

        # P2 Row
        p2_lbl = QtWidgets.QLabel("P2")
        p2_lbl.setStyleSheet("font-weight: bold; color: #388E3C; font-size: 13px;")
        self.place_x = self.create_coord_sb("#388E3C")
        self.place_y = self.create_coord_sb("#388E3C")
        self.place_z = self.create_coord_sb("#388E3C")
        
        points_grid.addWidget(p2_lbl, 1, 0)
        points_grid.addWidget(self.place_x, 1, 1)
        points_grid.addWidget(self.place_y, 1, 2)
        points_grid.addWidget(self.place_z, 1, 3)

        # LP Row
        lp_lbl = QtWidgets.QLabel("LP")
        lp_lbl.setStyleSheet("font-weight: bold; color: #D32F2F; font-size: 13px;")
        self.live_x = self.create_coord_sb("#D32F2F")
        self.live_y = self.create_coord_sb("#D32F2F")
        self.live_z = self.create_coord_sb("#D32F2F")
        for sb in [self.live_x, self.live_y, self.live_z]:
            sb.setReadOnly(True)

        points_grid.addWidget(lp_lbl, 2, 0)
        points_grid.addWidget(self.live_x, 2, 1)
        points_grid.addWidget(self.live_y, 2, 2)
        points_grid.addWidget(self.live_z, 2, 3)

        # Back-link coordinates back to main_window for Mixin methods
        self.main_window.pick_x, self.main_window.pick_y, self.main_window.pick_z = self.pick_x, self.pick_y, self.pick_z
        self.main_window.place_x, self.main_window.place_y, self.main_window.place_z = self.place_x, self.place_y, self.place_z
        self.main_window.live_x, self.main_window.live_y, self.main_window.live_z = self.live_x, self.live_y, self.live_z

        coord_layout.addLayout(points_grid)
        self.objects_layout.addWidget(coord_container)
        self.objects_layout.addStretch()

        self.stack.addWidget(self.objects_view)
        
        # Initial State
        self.switch_view(0)

    def create_coord_sb(self, color):
        sb = TypeOnlyDoubleSpinBox()
        sb.setRange(-9999, 9999)
        sb.setDecimals(1)
        sb.setSuffix(" cm")
        sb.setFixedWidth(78)
        sb.setFixedHeight(32)
        sb.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        sb.setStyleSheet(f"""
            QDoubleSpinBox {{
                background: white;
                color: {color};
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
                padding: 2px 4px;
                font-weight: bold;
            }}
            QDoubleSpinBox:focus {{ border-color: {color}; }}
        """)
        sb.valueChanged.connect(self.main_window.save_sim_object_coords)
        return sb

    def update_object_position(self):
        """Moves the selected simulation object to P1 coordinates."""
        current_item = self.objects_list.currentItem()
        if not current_item:
            self.main_window.log("⚠️ Select an object from the list first.")
            self.main_window.show_toast("No object selected", "warning")
            return
            
        name = current_item.text()
        if name in self.main_window.robot.links:
            link = self.main_window.robot.links[name]
            ratio = self.main_window.canvas.grid_units_per_cm
            
            # Target P1 Position (scaled to graph units)
            px = self.pick_x.value() * ratio
            py = self.pick_y.value() * ratio
            pz = self.pick_z.value() * ratio
            
            # Apply transformation (keep existing rotation if any)
            t_new = np.identity(4)
            t_new[:3, :3] = link.t_offset[:3, :3]
            t_new[:3, 3] = [px, py, pz]
            link.t_offset = t_new
            
            # Update visuals
            self.main_window.robot.update_kinematics()
            self.main_window.canvas.update_transforms(self.main_window.robot)
            
            self.main_window.log(f"✅ Object '{name}' moved to P1: ({self.pick_x.value()}, {self.pick_y.value()}, {self.pick_z.value()}) cm")
            self.main_window.show_toast(f"Moved {name} to P1", "success")

    def toggle_pick_place_sim(self, checked):
        """Enable automated pick-and-place monitoring."""
        self.is_sim_active = checked
        if checked:
            self.main_window.log("🚀 SIMULATION MONITOR ACTIVE: Robot will now auto-grip at P1 and place at P2.")
            self.start_btn.setText("🛑 Stop Simulation")
            self.start_btn.setStyleSheet("background-color: #f44336; color: white; border-radius: 8px; font-weight: bold; font-size: 14px;")
        else:
            self.main_window.log("🛑 Simulation Monitor Stopped.")
            self.start_btn.setText("🚀 Start Simulation")
            self.start_btn.setStyleSheet("background-color: #fdd835; color: #212121; border-radius: 8px; font-weight: bold; font-size: 14px;")
            
            # Reset state
            self.gripped_object = None
            self.grip_offset = None
            self.main_window.canvas.clear_highlights()
            self.main_window.canvas.plotter.render()

    def create_tab_button(self, text, icon_path):
        btn = QtWidgets.QPushButton(text)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setIconSize(QtCore.QSize(24, 24))
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: black;
                font-weight: bold;
                border: 1px solid #bbb;
                border-radius: 8px;
                padding: 5px;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        return btn

    def switch_view(self, index):
        self.stack.setCurrentIndex(index)
        
        # Style active button
        active_style = """
            QPushButton {
                background-color: #1976d2;
                color: black;
                font-weight: bold;
                border: 1px solid #0d47a1;
                border-radius: 8px;
                padding: 5px;
                text-align: left;
                padding-left: 15px;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #f5f5f5;
                color: black;
                font-weight: bold;
                border: 1px solid #bbb;
                border-radius: 8px;
                padding: 5px;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """
        
        if index == 0:
            self.joints_btn.setStyleSheet(active_style)
            self.matrices_btn.setStyleSheet(inactive_style)
        else:
            self.joints_btn.setStyleSheet(inactive_style)
            self.matrices_btn.setStyleSheet(active_style)
            self.refresh_matrices()

    def refresh_joints(self):
        # Reset ghost angle tracking dict on each refresh
        self._last_ghost_angle = {}  # joint_name -> last angle a ghost was snapped
        # Clear existing items in Joint View
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.sliders = {}
        robot = self.main_window.robot
        
        if not robot.joints:
            no_joints_label = QtWidgets.QLabel("No joints found. Create joints in 'Joint' tab first.")
            no_joints_label.setStyleSheet("color: #757575; font-style: italic;")
            no_joints_label.setAlignment(QtCore.Qt.AlignCenter)
            self.scroll_layout.addWidget(no_joints_label)
            return

        for name, joint in robot.joints.items():
            # Skip slave joints - we only show master/independent controls
            is_slave = False
            for master, slaves in robot.joint_relations.items():
                if any(s_id == name for s_id, r in slaves):
                    is_slave = True
                    break
            if is_slave:
                continue

            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            
            # Header
            header = QtWidgets.QLabel(f"{name} ({joint.joint_type})")
            header.setStyleSheet("font-weight: bold;")
            layout.addWidget(header)
            
            # Sub-header
            sub_header = QtWidgets.QLabel(f"{joint.parent_link.name} -> {joint.child_link.name}")
            sub_header.setStyleSheet("font-size: 10px; color: #666;")
            layout.addWidget(sub_header)
            # Slider
            slider_layout = QtWidgets.QHBoxLayout()
            
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setMinimum(int(joint.min_limit))
            slider.setMaximum(int(joint.max_limit))
            slider.setValue(int(joint.current_value))
            slider.setCursor(QtCore.Qt.PointingHandCursor)
            slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    height: 8px;
                    background: #f0f0f0;
                    border-radius: 4px;
                    border: 1px solid #ddd;
                }
                QSlider::sub-page:horizontal {
                    background: #bbdefb;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: white;
                    border: 2px solid #1976d2;
                    width: 16px;
                    height: 16px;
                    margin-top: -5px;
                    margin-bottom: -5px;
                    border-radius: 8px;
                }
                QSlider::handle:horizontal:hover {
                    background: #e3f2fd;
                }
            """)
            
            slider_layout.addWidget(slider)
            
            # Manual Spinbox
            val_spin = TypeOnlyDoubleSpinBox()
            val_spin.setRange(joint.min_limit, joint.max_limit)
            val_spin.setValue(joint.current_value)
            val_spin.setSuffix("°")
            val_spin.setDecimals(1)
            val_spin.setFixedWidth(70)
            val_spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
            val_spin.setStyleSheet("""
                QDoubleSpinBox {
                    background: white;
                    color: #1976d2;
                    border: 1px solid #1976d2;
                    border-radius: 3px;
                    padding: 2px;
                    font-weight: bold;
                }
            """)
            slider_layout.addWidget(val_spin)
            
            layout.addLayout(slider_layout)
            
            # Separator
            line = QtWidgets.QFrame()
            line.setFrameShape(QtWidgets.QFrame.HLine)
            line.setFrameShadow(QtWidgets.QFrame.Sunken)
            line.setStyleSheet("color: #ddd;")
            layout.addWidget(line)
            
            self.scroll_layout.addWidget(container)
            
            self.sliders[name] = {
                'slider': slider,
                'spinbox': val_spin,
                'joint': joint
            }
            
            slider.valueChanged.connect(lambda val, n=name: self.on_slider_change(n, val))
            val_spin.valueChanged.connect(lambda val, n=name: self.on_slider_change(n, val))

    def refresh_matrices(self):
        # Clear existing items in Matrices View
        while self.matrices_scroll_layout.count():
            item = self.matrices_scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self.matrix_labels = {}
        robot = self.main_window.robot
        
        if not robot.joints:
            label = QtWidgets.QLabel("No joints/matrices available.")
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.matrices_scroll_layout.addWidget(label)
            return

        for name, joint in robot.joints.items():
            # Skip slave joints - we only show master/independent matrices
            is_slave = False
            for master, slaves in robot.joint_relations.items():
                if any(s_id == name for s_id, r in slaves):
                    is_slave = True
                    break
            if is_slave:
                continue

            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            
            header = QtWidgets.QLabel(f"Matrix: {name} (cm)")
            header.setStyleSheet("font-weight: bold; color: #1565c0;")
            layout.addWidget(header)
            
            # Get Matrix string
            matrix = joint.get_matrix()
            mat_str = self.format_matrix(matrix)
            
            mat_label = QtWidgets.QLabel(mat_str)
            mat_label.setStyleSheet("font-family: Consolas; font-size: 24px; font-weight: bold; color: #1976d2; background: #fff; padding: 15px; border: 1px solid #ddd;")
            layout.addWidget(mat_label)
            
            self.matrices_scroll_layout.addWidget(container)
            self.matrix_labels[name] = mat_label

    def format_matrix(self, matrix):
        # Scale translation to CM based on adjustable graph ratio
        ratio = self.main_window.canvas.grid_units_per_cm
        mat_cm = np.copy(matrix)
        mat_cm[:3, 3] /= ratio
        
        lines = []
        for row in mat_cm:
            line = "  ".join([f"{val:6.2f}" for val in row])
            lines.append(f"[ {line} ]")
        return "\n".join(lines)

    def on_slider_change(self, name, value):
        if name in self.sliders:
            data = self.sliders[name]
            joint = data['joint']
            
            # Update Joint Model
            joint.current_value = float(value)
            
            # Propagation to related slave joints
            if name in self.main_window.robot.joint_relations:
                for slave_id, ratio in self.main_window.robot.joint_relations[name]:
                    slave_joint = self.main_window.robot.joints.get(slave_id)
                    if slave_joint:
                        slave_joint.current_value = float(value) * ratio
            
            # Update Spinbox and Slider without infinite loop
            if data['slider'].value() != int(value):
                data['slider'].blockSignals(True)
                data['slider'].setValue(int(value))
                data['slider'].blockSignals(False)
            if data['spinbox'].value() != float(value):
                data['spinbox'].blockSignals(True)
                data['spinbox'].setValue(float(value))
                data['spinbox'].blockSignals(False)
            
            # Update Robot Kinematics
            self.main_window.robot.update_kinematics()
            
            # Update Graphics
            self.main_window.canvas.update_transforms(self.main_window.robot)
            
            # Update Live Point Coordinates UI
            if hasattr(self.main_window, 'update_live_ui'):
                self.main_window.update_live_ui()


            # --- GHOST SHADOW TRAIL ---
            # Sample a ghost every GHOST_STEP degrees of movement
            try:
                GHOST_STEP = 3  # degrees between ghost snapshots
                _last = self._last_ghost_angle.get(name, None)
                _cur_angle = float(value)
                if _last is None or abs(_cur_angle - _last) >= GHOST_STEP:
                    import numpy as _np2
                    
                    # 1. Master Joint Trail
                    _link = joint.child_link
                    _mesh = _link.mesh
                    _transform = _np2.copy(_link.t_world)
                    _col = getattr(_link, 'color', '#888888') or '#888888'
                    self.main_window.canvas.add_joint_ghost(
                        _link.name,
                        mesh=_mesh, transform=_transform,
                        color=_col
                    )
                    
                    # 2. Related (Slave) Joint Trails
                    if name in self.main_window.robot.joint_relations:
                        for slave_id, ratio in self.main_window.robot.joint_relations[name]:
                            slave_joint = self.main_window.robot.joints.get(slave_id)
                            if slave_joint:
                                s_link = slave_joint.child_link
                                s_mesh = s_link.mesh
                                s_transform = _np2.copy(s_link.t_world)
                                s_col = getattr(s_link, 'color', '#888888') or '#888888'
                                self.main_window.canvas.add_joint_ghost(
                                    s_link.name,
                                    mesh=s_mesh, transform=s_transform,
                                    color=s_col
                                )
                    
                    self._last_ghost_angle[name] = _cur_angle
            except Exception:
                pass

            # Show Speed Overlay on 3D Canvas
            self.main_window.show_speed_overlay()
            
            self.main_window.canvas.plotter.render()
            
            # Send command to hardware with current speed
            if hasattr(self.main_window, 'serial_mgr') and self.main_window.serial_mgr.is_connected:
                joint_id = name
                self.main_window.serial_mgr.send_command(joint_id, float(value), speed=float(self.main_window.current_speed))
            
            # Update Matrices if visible
            if self.stack.currentIndex() == 1:
                self.refresh_matrices()
