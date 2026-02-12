from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np

class JointPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.selected_object = None
        self.parent_object = None
        self.child_object = None
        self.axis_point1 = None
        self.axis_point2 = None
        
        # Undo/Redo history
        self.history = []  # List of (parent, child) tuples
        self.history_index = -1
        
        # Active joints storage
        self.joints = {}  # {child_object_name: {parent, axis, min, max, current_angle, alignment_point}}
        self.active_joint_control = None  # Currently selected joint for control
        
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Object List
        self.objects_list = QtWidgets.QListWidget()
        self.objects_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                color: #212121;
                border: none;
                font-size: 14px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QListWidget::item:selected {
                background-color: #1976d2;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #1565c0;
            }
        """)
        self.objects_list.itemClicked.connect(self.on_object_clicked)
        layout.addWidget(self.objects_list)
        # Section 2 is being removed as requested
        self.axis_section = QtWidgets.QWidget()
        self.axis_section.setVisible(False)
        
        # --- ROTATION AXIS & LIMITS SECTION (appears after CREATE JOINT) ---
        self.rotation_section = QtWidgets.QWidget()
        self.rotation_section.setStyleSheet("background-color: white; padding: 10px; border: 1px solid #e0e0e0;")
        self.rotation_section.setVisible(False)
        
        rot_layout = QtWidgets.QVBoxLayout(self.rotation_section)
        rot_layout.setSpacing(10)
        
        # Section header
        rot_header = QtWidgets.QLabel("3. ROTATION AXIS & LIMITS")
        rot_header.setStyleSheet("color: #1976d2; font-size: 14px; font-weight: bold; padding: 5px;")
        rot_layout.addWidget(rot_header)
        
        # Joint name input
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("Joint Name:")
        name_label.setStyleSheet("color: #616161; font-size: 12px;")
        name_layout.addWidget(name_label)
        
        self.joint_name_input = QtWidgets.QLineEdit()
        self.joint_name_input.setPlaceholderText("e.g. Shoulder_Pivot")
        self.joint_name_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: #1976d2;
                border: 1px solid #bbb;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        name_layout.addWidget(self.joint_name_input)
        rot_layout.addLayout(name_layout)
        
        # Axis selection
        axis_label = QtWidgets.QLabel("Select rotation axis:")
        axis_label.setStyleSheet("color: #616161; font-size: 12px; padding: 5px;")
        rot_layout.addWidget(axis_label)
        
        axis_buttons_row = QtWidgets.QHBoxLayout()
        self.axis_group = QtWidgets.QButtonGroup()
        
        self.axis_x_radio = QtWidgets.QRadioButton("X Axis")
        self.axis_x_radio.setStyleSheet("color: #d32f2f; font-size: 12px;")
        self.axis_group.addButton(self.axis_x_radio, 0)
        axis_buttons_row.addWidget(self.axis_x_radio)
        
        self.axis_y_radio = QtWidgets.QRadioButton("Y Axis")
        self.axis_y_radio.setStyleSheet("color: #1976d2; font-size: 12px;")
        self.axis_group.addButton(self.axis_y_radio, 1)
        axis_buttons_row.addWidget(self.axis_y_radio)
        
        self.axis_z_radio = QtWidgets.QRadioButton("Z Axis")
        self.axis_z_radio.setStyleSheet("color: #1565c0; font-size: 12px;")
        self.axis_z_radio.setChecked(True)  # Default to Z
        self.axis_group.addButton(self.axis_z_radio, 2)
        axis_buttons_row.addWidget(self.axis_z_radio)
        
        rot_layout.addLayout(axis_buttons_row)
        
        # Rotation limits
        limits_label = QtWidgets.QLabel("Rotation limits (degrees):")
        limits_label.setStyleSheet("color: #616161; font-size: 12px; padding: 5px;")
        rot_layout.addWidget(limits_label)
        
        limits_row = QtWidgets.QHBoxLayout()
        
        min_label = QtWidgets.QLabel("Min:")
        min_label.setStyleSheet("color: #616161; font-size: 11px;")
        limits_row.addWidget(min_label)
        
        self.min_limit_spin = QtWidgets.QDoubleSpinBox()
        self.min_limit_spin.setRange(-360, 360)
        self.min_limit_spin.setValue(-180)
        self.min_limit_spin.setStyleSheet("background-color: white; color: #212121; border: 1px solid #bbb; padding: 5px;")
        self.min_limit_spin.valueChanged.connect(self.update_slider_range)
        limits_row.addWidget(self.min_limit_spin)
        
        max_label = QtWidgets.QLabel("Max:")
        max_label.setStyleSheet("color: #616161; font-size: 11px;")
        limits_row.addWidget(max_label)
        
        self.max_limit_spin = QtWidgets.QDoubleSpinBox()
        self.max_limit_spin.setRange(-360, 360)
        self.max_limit_spin.setValue(180)
        self.max_limit_spin.setStyleSheet("background-color: white; color: #212121; border: 1px solid #bbb; padding: 5px;")
        self.max_limit_spin.valueChanged.connect(self.update_slider_range)
        limits_row.addWidget(self.max_limit_spin)
        
        rot_layout.addLayout(limits_row)
        
        # Test Rotation Slider
        test_label = QtWidgets.QLabel("Test rotation:")
        test_label.setStyleSheet("color: #616161; font-size: 12px; padding: 5px;")
        rot_layout.addWidget(test_label)
        
        slider_row = QtWidgets.QHBoxLayout()
        
        self.rotation_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rotation_slider.setRange(-1800, 1800)  # -180 to 180 degrees (x10 for precision)
        self.rotation_slider.setValue(0)
        self.rotation_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #e0e0e0;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #1976d2;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)
        self.rotation_slider.valueChanged.connect(self.on_slider_changed)
        slider_row.addWidget(self.rotation_slider)
        
        # Direct angle input spinbox
        self.rotation_spinbox = QtWidgets.QDoubleSpinBox()
        self.rotation_spinbox.setRange(-180, 180)
        self.rotation_spinbox.setValue(0)
        self.rotation_spinbox.setSuffix("°")
        self.rotation_spinbox.setDecimals(1)
        self.rotation_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: white;
                color: #1976d2;
                border: 2px solid #1976d2;
                border-radius: 3px;
                padding: 5px;
                font-size: 12px;
                font-weight: bold;
                min-width: 80px;
            }
        """)
        self.rotation_spinbox.valueChanged.connect(self.on_spinbox_changed)
        slider_row.addWidget(self.rotation_spinbox)
        
        rot_layout.addLayout(slider_row)
        
        # Confirm button
        self.confirm_joint_btn = QtWidgets.QPushButton("CONFIRM JOINT")
        self.confirm_joint_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
        """)
        self.confirm_joint_btn.clicked.connect(self.confirm_joint)
        rot_layout.addWidget(self.confirm_joint_btn)
        
        layout.addWidget(self.rotation_section)
        
        # Parent/Child Selection Buttons
        buttons_container = QtWidgets.QWidget()
        buttons_container.setStyleSheet("background-color: white; padding: 10px; border: 1px solid #e0e0e0;")
        buttons_layout = QtWidgets.QHBoxLayout(buttons_container)
        buttons_layout.setSpacing(10)
        
        # Parent Button
        self.parent_btn = QtWidgets.QPushButton("parent object")
        self.parent_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffcdd2;
                color: #000;
                border: 2px solid #d32f2f;
                border-radius: 5px;
                padding: 15px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ef9a9a;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #9e9e9e;
                border-color: #bbb;
            }
        """)
        self.parent_btn.clicked.connect(self.set_as_parent)
        self.parent_btn.setEnabled(False)
        buttons_layout.addWidget(self.parent_btn)
        
        # Child Button
        self.child_btn = QtWidgets.QPushButton("child object")
        self.child_btn.setStyleSheet("""
            QPushButton {
                background-color: #bbdefb;
                color: #000;
                border: 2px solid #1976d2;
                border-radius: 5px;
                padding: 15px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #90caf9;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #9e9e9e;
                border-color: #bbb;
            }
        """)
        self.child_btn.clicked.connect(self.set_as_child)
        self.child_btn.setEnabled(False)
        buttons_layout.addWidget(self.child_btn)
        
        layout.addWidget(buttons_container)
        
        # --- UNDO/REDO BUTTONS ---
        undo_redo_container = QtWidgets.QWidget()
        undo_redo_container.setStyleSheet("background-color: white; padding: 5px; border: 1px solid #e0e0e0;")
        undo_redo_layout = QtWidgets.QHBoxLayout(undo_redo_container)
        undo_redo_layout.setSpacing(10)
        
        self.undo_btn = QtWidgets.QPushButton("Undo")
        self.undo_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        self.undo_btn.clicked.connect(self.undo_selection)
        undo_redo_layout.addWidget(self.undo_btn)
        
        self.redo_btn = QtWidgets.QPushButton("Redo")
        self.redo_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffb74d;
            }
        """)
        self.redo_btn.clicked.connect(self.redo_selection)
        undo_redo_layout.addWidget(self.redo_btn)
        
        layout.addWidget(undo_redo_container)
        
        # --- JOINT CONTROL SECTION (appears when clicking jointed object) ---
        self.joint_control_section = QtWidgets.QWidget()
        self.joint_control_section.setStyleSheet("background-color: white; padding: 10px; border: 1px solid #e0e0e0;")
        self.joint_control_section.setVisible(False)
        
        jc_layout = QtWidgets.QVBoxLayout(self.joint_control_section)
        jc_layout.setSpacing(10)
        
        # Header
        jc_header = QtWidgets.QLabel("JOINT CONTROL")
        jc_header.setStyleSheet("color: #ff9800; font-size: 14px; font-weight: bold; padding: 5px;")
        jc_layout.addWidget(jc_header)
        
        # Joint info
        self.joint_info_label = QtWidgets.QLabel("No joint selected")
        self.joint_info_label.setStyleSheet("color: #616161; font-size: 11px; padding: 3px;")
        jc_layout.addWidget(self.joint_info_label)
        
        # Control slider
        jc_slider_label = QtWidgets.QLabel("Rotation:")
        jc_slider_label.setStyleSheet("color: #616161; font-size: 12px; padding: 3px;")
        jc_layout.addWidget(jc_slider_label)
        
        jc_slider_row = QtWidgets.QHBoxLayout()
        
        self.joint_control_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.joint_control_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #e0e0e0;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ff9800;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)
        self.joint_control_slider.valueChanged.connect(self.on_joint_control_changed)
        jc_slider_row.addWidget(self.joint_control_slider)
        
        self.joint_control_spinbox = QtWidgets.QDoubleSpinBox()
        self.joint_control_spinbox.setSuffix("°")
        self.joint_control_spinbox.setDecimals(1)
        self.joint_control_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: white;
                color: #ff9800;
                border: 2px solid #ff9800;
                border-radius: 3px;
                padding: 5px;
                font-size: 12px;
                font-weight: bold;
                min-width: 80px;
            }
        """)
        self.joint_control_spinbox.valueChanged.connect(self.on_joint_control_spinbox_changed)
        jc_slider_row.addWidget(self.joint_control_spinbox)
        
        jc_layout.addLayout(jc_slider_row)
        
        layout.addWidget(self.joint_control_section)
        
        # --- 4. CREATED JOINTS SECTION ---
        header_joints = QtWidgets.QLabel("4. CREATED JOINTS")
        header_joints.setStyleSheet("color: #1976d2; font-size: 14px; font-weight: bold; margin-top: 20px; padding: 5px;")
        layout.addWidget(header_joints)
        
        self.joints_history_list = QtWidgets.QListWidget()
        self.joints_history_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                min-height: 200px;
            }
            QListWidget::item {
                border-bottom: 1px solid #e0e0e0;
                background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.joints_history_list)
        
        # Bottom stretch
        layout.addStretch()

    def refresh_joints_history(self):
        """Refresh the list of created joints with delete buttons"""
        self.joints_history_list.clear()
        
        for child_name, data in self.joints.items():
            item = QtWidgets.QListWidgetItem()
            self.joints_history_list.addItem(item)
            
            # Create custom widget for the item
            widget = QtWidgets.QWidget()
            item_layout = QtWidgets.QHBoxLayout(widget)
            item_layout.setContentsMargins(10, 8, 10, 8)
            item_layout.setSpacing(10)
            
            # Label: Custom Name Only
            display_name = data.get('custom_name', f"{data['parent']} \u2192 {child_name}")
            label = QtWidgets.QLabel(display_name)
            label.setStyleSheet("color: #212121; font-size: 13px; font-weight: bold;")
            item_layout.addWidget(label)
            
            item_layout.addStretch()
            
            # Axis/Limits info small
            axis_names = {0: "X", 1: "Y", 2: "Z"}
            info = QtWidgets.QLabel(f"Axis: {axis_names[data['axis']]}")
            info.setStyleSheet("color: #757575; font-size: 11px; margin-right: 5px;")
            item_layout.addWidget(info)
            
            # Delete Button
            del_btn = QtWidgets.QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setCursor(QtCore.Qt.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffebee;
                    color: #d32f2f;
                    border: 1px solid #ffcdd2;
                    border-radius: 12px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                    color: white;
                    border: 1px solid #d32f2f;
                }
            """)
            del_btn.clicked.connect(lambda checked, name=child_name: self.delete_joint(name))
            item_layout.addWidget(del_btn)
            
            item.setSizeHint(widget.sizeHint())
            self.joints_history_list.setItemWidget(item, widget)

    def delete_joint(self, child_name):
        """Delete a joint and reset the child's transform"""
        if child_name not in self.joints:
            return
            
        joint_data = self.joints[child_name]
        parent_name = joint_data['parent']
        joint_name = joint_data.get('joint_id', f"joint_{parent_name}_{child_name}")
        
        self.mw.log(f"Deleting joint: {joint_name}")
        
        # 1. Remove from Robot Model Core
        self.mw.robot.remove_joint(joint_name)
        
        # 2. Reset world transform to the offset (0 rotation position)
        child_link = self.mw.robot.links[child_name]
        child_link.t_world = child_link.t_offset.copy()
        
        # 3. Remove from UI data structures
        del self.joints[child_name]
        
        # 3. If it was active in control, hide it
        if self.active_joint_control == child_name:
            self.joint_control_section.setVisible(False)
            self.active_joint_control = None
            
        # 4. Refresh UI
        self.refresh_links()
        self.refresh_joints_history()
        
        # Refresh Matrices Panel Sliders
        if hasattr(self.mw, 'matrices_tab'):
            self.mw.matrices_tab.refresh_sliders()
        # 5. Update canvas
        self.mw.robot.update_kinematics()
        self.mw.canvas.update_transforms(self.mw.robot)
        self.mw.log(f"Joint deleted successfully.")

    def select_object(self, name):
        """Selection logic for external calls"""
        self.selected_object = name
        self.parent_btn.setEnabled(True)
        self.child_btn.setEnabled(True)
        self.mw.canvas.select_actor(name)

    def set_as_parent(self):
        """Set selected object as parent"""
        if not self.selected_object:
            return
            
        self.parent_object = self.selected_object
        self.mw.log(f"Parent set to: {self.parent_object}")
        self.save_to_history()
        self.mw.canvas.deselect_all()
        self.refresh_links()
        
        # Section 2 is gone, so we don't call check_show_axis_section
        self.parent_btn.setEnabled(False)
        self.child_btn.setEnabled(False)
        self.selected_object = None
        
        # New: Check for cached alignment
        if self.parent_object and self.child_object:
            self.check_for_cached_alignment()

    def set_as_child(self):
        """Set selected object as child"""
        if not self.selected_object:
            return
        
        if self.selected_object in self.joints:
            self.mw.log(f"Error: {self.selected_object} is already a jointed child.")
            return
            
        self.child_object = self.selected_object
        self.mw.log(f"Child set to: {self.child_object}")
        self.save_to_history()
        self.mw.canvas.deselect_all()
        self.refresh_links()
        
        # Section 2 is gone, so we don't call check_show_axis_section
        self.parent_btn.setEnabled(False)
        self.child_btn.setEnabled(False)
        self.selected_object = None
        
        # New: Check for cached alignment
        if self.parent_object and self.child_object:
            self.check_for_cached_alignment()

    def check_for_cached_alignment(self):
        """Check if an alignment exists for the current parent/child pair"""
        pair = (self.parent_object, self.child_object)
        if pair in self.mw.alignment_cache:
            self.alignment_point = self.mw.alignment_cache[pair]
            self.mw.log(f"Matched alignment point found for {pair}: {self.alignment_point}")
            self.create_joint()
        else:
            self.mw.log(f"No cached alignment found for {pair}. Objects must be aligned in 'Align' tab first.")
    def undo_selection(self):
        """Undo the last parent/child selection"""
        if self.history_index > 0:
            self.history_index -= 1
            parent, child = self.history[self.history_index]
            self.parent_object = parent
            self.child_object = child
            self.refresh_links()
            self.mw.log(f"Undo: Parent={parent}, Child={child}")
        else:
            self.mw.log("Nothing to undo.")

    def redo_selection(self):
        """Redo a previously undone selection"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            parent, child = self.history[self.history_index]
            self.parent_object = parent
            self.child_object = child
            self.refresh_links()
            self.mw.log(f"Redo: Parent={parent}, Child={child}")
        else:
            self.mw.log("Nothing to redo.")

    def save_to_history(self):
        """Save current parent/child state to history"""
        # Remove any "future" history if we're in the middle
        self.history = self.history[:self.history_index + 1]
        
        # Add current state
        self.history.append((self.parent_object, self.child_object))
        self.history_index = len(self.history) - 1

    def on_object_clicked(self, item):
        """When an object is clicked in the list"""
        object_name = item.text().replace("✓ ", "").replace("✓⭕ ", "")  # Remove indicators
        
        # Check if this object has a joint
        if object_name in self.joints:
            # Show joint control for this jointed object
            self.show_joint_control(object_name)
            
            # ALLOW jointed objects to be selected as parents!
            self.selected_object = object_name
            self.parent_btn.setEnabled(True)
            self.child_btn.setEnabled(False) # Still keep child disabled (one parent only)
        else:
            # Normal selection for parent/child assignment
            self.selected_object = object_name
            
            # Hide joint control
            self.joint_control_section.setVisible(False)
            self.active_joint_control = None
            
            # Highlight in 3D view (yellow)
            self.mw.canvas.select_actor(self.selected_object)
            
            # Enable buttons
            self.parent_btn.setEnabled(True)
            self.child_btn.setEnabled(True)
            
            self.mw.log(f"Selected: {self.selected_object}")

    def show_joint_control(self, object_name):
        """Show joint control section for a jointed object"""
        self.active_joint_control = object_name
        joint_data = self.joints[object_name]
        
        # Update info label
        axis_names = {0: "X", 1: "Y", 2: "Z"}
        axis_name = axis_names.get(joint_data['axis'], "?")
        custom_name = joint_data.get('custom_name', object_name)
        self.joint_info_label.setText(
            f"Joint: {custom_name} | Axis: {axis_name}"
        )
        
        # Setup slider
        min_val = int(joint_data['min'] * 10)
        max_val = int(joint_data['max'] * 10)
        current_val = int(joint_data['current_angle'] * 10)
        
        self.joint_control_slider.blockSignals(True)
        self.joint_control_slider.setRange(min_val, max_val)
        self.joint_control_slider.setValue(current_val)
        self.joint_control_slider.blockSignals(False)
        
        self.joint_control_spinbox.blockSignals(True)
        self.joint_control_spinbox.setRange(joint_data['min'], joint_data['max'])
        self.joint_control_spinbox.setValue(joint_data['current_angle'])
        self.joint_control_spinbox.blockSignals(False)
        
        # Show section
        self.joint_control_section.setVisible(True)
        self.mw.log(f"Joint control active for: {object_name}")

    def create_joint(self):
        """Create the joint between parent and child"""
        if not self.parent_object or not self.child_object or self.alignment_point is None:
            self.mw.log("Error: Parent, child, or alignment point not set.")
            return
        
        self.mw.log(f"Creating joint between {self.parent_object} and {self.child_object}...")
        self.mw.log(f"Joint pivot at: {self.alignment_point}")
        
        # Store original child transform for rotation testing
        child_link = self.mw.robot.links[self.child_object]
        self.original_child_transform = child_link.t_world.copy()
        
        # Show yellow arrow at alignment point
        self.show_joint_arrow()
        
        # Show rotation axis & limits section
        self.rotation_section.setVisible(True)
        
        # Update slider range based on limits
        self.update_slider_range()
        
        # Pre-fill joint name
        default_name = f"joint_{self.parent_object}_{self.child_object}"
        self.joint_name_input.setText(default_name)

    def update_slider_range(self):
        """Update slider range when min/max limits change"""
        if hasattr(self, 'rotation_slider'):
            min_val = int(self.min_limit_spin.value() * 10)
            max_val = int(self.max_limit_spin.value() * 10)
            self.rotation_slider.setRange(min_val, max_val)
            self.rotation_slider.setValue(0)
            
            # Also update spinbox range
            self.rotation_spinbox.setRange(self.min_limit_spin.value(), self.max_limit_spin.value())
            self.rotation_spinbox.setValue(0)

    def on_slider_changed(self, value):
        """Called when slider value changes - update spinbox and rotate"""
        angle_deg = value / 10.0
        
        # Update spinbox without triggering its signal
        self.rotation_spinbox.blockSignals(True)
        self.rotation_spinbox.setValue(angle_deg)
        self.rotation_spinbox.blockSignals(False)
        
        # Apply rotation
        self.test_rotation(value)

    def on_spinbox_changed(self, value):
        """Called when spinbox value changes - update slider and rotate"""
        slider_value = int(value * 10)
        
        # Update slider without triggering its signal
        self.rotation_slider.blockSignals(True)
        self.rotation_slider.setValue(slider_value)
        self.rotation_slider.blockSignals(False)
        
        # Apply rotation
        self.test_rotation(slider_value)

    def test_rotation(self, value):
        """Test rotate the child object based on slider value"""
        if not hasattr(self, 'original_child_transform') or not self.child_object or self.child_object not in self.mw.robot.links:
            return
        
        # Convert slider value to degrees
        angle_deg = value / 10.0
        angle_rad = np.radians(angle_deg)
        
        # Get selected axis
        if self.axis_x_radio.isChecked():
            axis = np.array([1, 0, 0])
        elif self.axis_y_radio.isChecked():
            axis = np.array([0, 1, 0])
        else:  # Z
            axis = np.array([0, 0, 1])
        
        # Create rotation matrix around the alignment point
        # R = T(pivot) * Rot(axis, angle) * T(-pivot)
        
        # Rodrigues' rotation formula
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0]
        ])
        
        R3x3 = np.eye(3) + np.sin(angle_rad) * K + (1 - np.cos(angle_rad)) * (K @ K)
        
        # Create 4x4 rotation matrix
        R = np.eye(4)
        R[:3, :3] = R3x3
        
        # Translate to origin, rotate, translate back
        T_to_origin = np.eye(4)
        T_to_origin[:3, 3] = -self.alignment_point
        
        T_from_origin = np.eye(4)
        T_from_origin[:3, 3] = self.alignment_point
        
        # Apply transformation: T_from * R * T_to * original
        child_link = self.mw.robot.links[self.child_object]
        child_link.t_world = T_from_origin @ R @ T_to_origin @ self.original_child_transform
        
        # Update visual
        self.mw.canvas.update_transforms(self.mw.robot)

    def show_joint_arrow(self):
        """Display a yellow arrow at the joint alignment point"""
        import pyvista as pv
        
        # Remove any existing arrow
        self.mw.canvas.plotter.remove_actor("joint_arrow")
        
        # Create arrow pointing up (Z direction by default) - MUCH SMALLER
        arrow_length = 0.4  # Reduced from 2.0 to 0.4 (20% of original size)
        arrow = pv.Arrow(
            start=self.alignment_point,
            direction=[0, 0, 1],
            scale=arrow_length
        )
        
        # Add to scene with yellow color
        self.mw.canvas.plotter.add_mesh(
            arrow,
            color="yellow",
            name="joint_arrow",
            pickable=False
        )
        self.mw.canvas.plotter.render()
        self.mw.log("Yellow arrow shown at joint location.")

    def confirm_joint(self):
        """Finalize the joint with selected axis and limits"""
        # Get selected axis
        if self.axis_x_radio.isChecked():
            axis = 0  # X
            axis_name = "X"
        elif self.axis_y_radio.isChecked():
            axis = 1  # Y
            axis_name = "Y"
        else:  # Z
            axis = 2  # Z
            axis_name = "Z"
        
        # Get limits
        min_limit = self.min_limit_spin.value()
        max_limit = self.max_limit_spin.value()
        
        child_link = self.mw.robot.links[self.child_object]
        parent_link = self.mw.robot.links[self.parent_object]
        
        # Get custom name and sanitize
        custom_name = self.joint_name_input.text().strip()
        if not custom_name:
            custom_name = f"joint_{self.parent_object}_{self.child_object}"
            
        # Robust sanitization: Only replace spaces. Let other chars (like -) stay.
        joint_id = custom_name.replace(" ", "_").replace("/", "_")
        
        # Check for duplicates or empty
        if not joint_id: joint_id = f"joint_{len(self.mw.robot.joints)}"
        
        # --- 1. PROPERLY ADD TO ROBOT MODEL ---
        joint = self.mw.robot.add_joint(joint_id, self.parent_object, self.child_object)
        
        # Calculate pivot point in Parent's Local Frame
        # Math: P_parent = inv(T_parent_world) * P_world
        t_parent_inv = np.linalg.inv(parent_link.t_world)
        pivot_local = (t_parent_inv @ np.append(self.alignment_point, 1))[:3]
        joint.origin = pivot_local
        
        # Set Axis (X, Y, or Z) - transformed to parent frame
        axis_vecs = [np.array([1,0,0]), np.array([0,1,0]), np.array([0,0,1])]
        # Convert global axis choice to parent local rotation axis
        # (Assuming the initial alignment made parent and child axes parallel to global)
        joint.axis = axis_vecs[axis]
        
        # Set Child Static Offset (relative to parent at 0 degrees)
        # Math: Child_Offset = inv(Parent_World) * Original_Aligned_Child_World
        # IMPORTANT: Use original_child_transform to ensure 0 deg = perfectly aligned position
        child_link.t_offset = t_parent_inv @ self.original_child_transform
        
        # Set Joint Limits
        joint.min_limit = min_limit
        joint.max_limit = max_limit
        joint.current_value = 0.0
        
        # --- 2. LOCAL STORAGE AND LOGGING ---
        # Store for UI tracking
        self.joints[self.child_object] = {
            'parent': self.parent_object,
            'axis': axis,
            'min': min_limit,
            'max': max_limit,
            'current_angle': 0.0,
            'alignment_point': self.alignment_point.copy(),
            'custom_name': custom_name,
            'joint_id': joint_id
        }
        
        self.mw.log(f"Joint confirmed and added to Robot model (ID: {joint_id})")
        
        # --- 3. AUTO-APPEND TO CODE EDITOR ---
        if hasattr(self.mw, 'program_tab'):
            current_code = self.mw.program_tab.code_edit.toPlainText()
            # If default text is there, clear it or append
            new_cmd = f"{joint_id} 0"
            if "Example Program" in current_code and len(current_code.splitlines()) < 10:
                self.mw.program_tab.code_edit.appendPlainText(new_cmd)
            else:
                self.mw.program_tab.code_edit.appendPlainText(new_cmd)
            self.mw.log(f"Auto-generated code: '{new_cmd}' added to Code tab.")
        self.mw.log(f"  Parent: {self.parent_object}")
        self.mw.log(f"  Child: {self.child_object}")
        self.mw.log(f"  Axis: {axis_name}")
        self.mw.log(f"  Limits: {min_limit}° to {max_limit}°")
        self.mw.log(f"  Pivot: {self.alignment_point}")
        
        # Remove arrow
        self.mw.canvas.plotter.remove_actor("joint_arrow")
        self.mw.canvas.plotter.render()
        
        # Reset UI
        self.reset_joint_ui()
        
        # Refresh joints list
        self.refresh_joints_history()
        
        # Refresh Matrices Panel Sliders
        if hasattr(self.mw, 'matrices_tab'):
            self.mw.matrices_tab.refresh_sliders()

    def on_joint_control_changed(self, value):
        """Handle joint control slider changes"""
        if not self.active_joint_control:
            return
        
        angle_deg = value / 10.0
        
        # Update spinbox
        self.joint_control_spinbox.blockSignals(True)
        self.joint_control_spinbox.setValue(angle_deg)
        self.joint_control_spinbox.blockSignals(False)
        
        # Apply rotation to joint
        self.apply_joint_rotation(self.active_joint_control, angle_deg)

    def on_joint_control_spinbox_changed(self, value):
        """Handle joint control spinbox changes"""
        if not self.active_joint_control:
            return
        
        slider_value = int(value * 10)
        
        # Update slider
        self.joint_control_slider.blockSignals(True)
        self.joint_control_slider.setValue(slider_value)
        self.joint_control_slider.blockSignals(False)
        
        # Apply rotation to joint
        self.apply_joint_rotation(self.active_joint_control, value)

    def apply_joint_rotation(self, child_name, angle_deg):
        """Apply rotation to a jointed object using the Robot core kinematics"""
        if child_name not in self.mw.robot.links:
            return
            
        child_link = self.mw.robot.links[child_name]
        joint = child_link.parent_joint
        
        if joint:
            # 1. Update the robot model state
            joint.current_value = angle_deg
            
            # 2. Trigger re-calculation of all world transforms
            # This handles multi-link chains correctly (e.g. Base -> Arm1 -> Arm2)
            self.mw.robot.update_kinematics()
            
            # 3. Synchronize local JointPanel data
            if child_name in self.joints:
                self.joints[child_name]['current_angle'] = angle_deg
                
            # 4. Synchronize MatricesPanel if it exists
            if hasattr(self.mw, 'matrices_tab'):
                self.mw.matrices_tab.sync_slider(child_name, angle_deg)
                
            # 5. Send command to hardware (ESP32)
            if hasattr(self.mw, 'serial_mgr'):
                # Use joint_id (e.g. joint_1) instead of display name for code consistency
                joint_id = self.joints[child_name].get('joint_id', child_name)
                # Send with default speed 0 for manual slider movement
                self.mw.serial_mgr.send_command(joint_id, angle_deg, speed=0)
                
            # 6. Push updated transforms to the 3D viewer
            self.mw.canvas.update_transforms(self.mw.robot)

    def reset_joint_ui(self):
        """Reset the joint creation UI"""
        self.parent_object = None
        self.child_object = None
        self.alignment_point = None
        
        self.axis_section.setVisible(False)
        self.rotation_section.setVisible(False)
        
        self.refresh_links()
        self.mw.log("Joint creation complete. Ready for next joint.")

    def refresh_links(self):
        """Refresh the object list with role indicators"""
        self.objects_list.clear()
        
        # Get all links from robot
        for name in self.mw.robot.links.keys():
            # Create item with colored box indicator and checkmark
            display_text = name
            
            # Check if this object has a joint (jointed child)
            if name in self.joints:
                display_text = f"✓⭕ {name}"  # Special indicator for jointed objects
            # Add checkmark for parent (white) or child (gray)
            elif name == self.parent_object:
                display_text = f"✓ {name}"  # White checkmark for parent
            elif name == self.child_object:
                display_text = f"✓ {name}"  # Gray checkmark for child
            
            item = QtWidgets.QListWidgetItem(display_text)
            
            # Color based on role
            if name in self.joints:
                # Jointed objects get orange color
                item.setForeground(QtGui.QColor("#ff9800"))  # Orange for jointed
                item.setBackground(QtGui.QColor("#fff3e0"))  # Light orange background
            elif name == self.parent_object:
                item.setForeground(QtGui.QColor("#d32f2f"))  # Red text for parent with checkmark
                item.setBackground(QtGui.QColor("#ffebee"))  # Light red background
            elif name == self.child_object:
                item.setForeground(QtGui.QColor("#1976d2"))  # Blue text for child with checkmark
                item.setBackground(QtGui.QColor("#e3f2fd"))  # Light blue background
            else:
                # Default alternating colors
                index = list(self.mw.robot.links.keys()).index(name)
                if index % 2 == 0:
                    item.setForeground(QtGui.QColor("#d32f2f"))  # Red
                else:
                    item.setForeground(QtGui.QColor("#1976d2"))  # Blue
            
            self.objects_list.addItem(item)
