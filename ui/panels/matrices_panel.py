from PyQt5 import QtWidgets, QtGui, QtCore
import numpy as np

class MatricesPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.sliders = {} # Store slider widgets for each joint
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Top: Matrix Display
        header_matrices = QtWidgets.QLabel("TRANSFORM MATRICES")
        header_matrices.setStyleSheet("color: #4ecdc4; font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(header_matrices)

        self.refresh_btn = QtWidgets.QPushButton("Update Matrices")
        self.refresh_btn.clicked.connect(self.update_display)
        layout.addWidget(self.refresh_btn)
        
        self.text_area = QtWidgets.QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QtGui.QFont("Consolas", 10))
        self.text_area.setStyleSheet("background-color: #1a1a1a; color: #4CAF50; border: 1px solid #333;")
        layout.addWidget(self.text_area)

        # Bottom: Joint Control Sliders
        header_sliders = QtWidgets.QLabel("JOINT ROTATION CONTROLS")
        header_sliders.setStyleSheet("color: #ffa500; font-size: 14px; font-weight: bold; margin-top: 15px; padding: 5px;")
        layout.addWidget(header_sliders)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #1a1a1a; border: none;")
        
        self.slider_container = QtWidgets.QWidget()
        self.slider_layout = QtWidgets.QVBoxLayout(self.slider_container)
        self.slider_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_area.setWidget(self.slider_container)
        
        layout.addWidget(self.scroll_area)

    def refresh_sliders(self):
        """Clears and rebuilds sliders based on confirmed joints"""
        # Clear existing
        while self.slider_layout.count():
            item = self.slider_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.sliders = {}
        
        joint_data = self.mw.joint_tab.joints
        if not joint_data:
            empty_msg = QtWidgets.QLabel("No joints created yet.")
            empty_msg.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
            self.slider_layout.addWidget(empty_msg)
            return

        for child_name, data in joint_data.items():
            # Container for each joint's control
            group = QtWidgets.QFrame()
            group.setStyleSheet("background-color: #222; border-radius: 5px; margin-bottom: 5px; border: 1px solid #333;")
            glay = QtWidgets.QVBoxLayout(group)
            glay.setContentsMargins(10, 5, 10, 5)
            
            # Label: Custom Name Only
            custom_name = data.get('custom_name', f"{data['parent']} \u2192 {child_name}")
            lbl = QtWidgets.QLabel(f"{custom_name} ({['X','Y','Z'][data['axis']]})")
            lbl.setStyleSheet("color: #ffa500; font-weight: bold; font-size: 11px;")
            glay.addWidget(lbl)
            
            # Slider Row
            row = QtWidgets.QHBoxLayout()
            
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(int(data['min'] * 10), int(data['max'] * 10))
            slider.setValue(int(data.get('current_angle', 0.0) * 10))
            
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(data['min'], data['max'])
            spin.setValue(data.get('current_angle', 0.0))
            spin.setFixedWidth(60)
            spin.setDecimals(1)
            
            # Connect
            slider.valueChanged.connect(lambda v, c=child_name, s=spin: self.on_slider_move(c, v/10.0, s))
            spin.valueChanged.connect(lambda v, c=child_name, sl=slider: self.on_spin_move(c, v, sl))
            
            row.addWidget(slider)
            row.addWidget(spin)
            glay.addLayout(row)
            
            self.slider_layout.addWidget(group)
            self.sliders[child_name] = {'slider': slider, 'spin': spin}

    def on_slider_move(self, child_name, value, spinbox):
        spinbox.blockSignals(True)
        spinbox.setValue(value)
        spinbox.blockSignals(False)
        self.apply_rotation(child_name, value)
        
        # Sync the Joint Panel slider if it's currently showing this joint
        if hasattr(self.mw.joint_tab, 'active_joint_control') and self.mw.joint_tab.active_joint_control == child_name:
            self.mw.joint_tab.joint_control_slider.blockSignals(True)
            self.mw.joint_tab.joint_control_slider.setValue(int(value * 10))
            self.mw.joint_tab.joint_control_slider.blockSignals(False)
            self.mw.joint_tab.joint_control_spinbox.blockSignals(True)
            self.mw.joint_tab.joint_control_spinbox.setValue(value)
            self.mw.joint_tab.joint_control_spinbox.blockSignals(False)

    def sync_slider(self, child_name, value):
        """External call to update a slider value without triggering events"""
        if child_name in self.sliders:
            data = self.sliders[child_name]
            data['slider'].blockSignals(True)
            data['slider'].setValue(int(value * 10))
            data['slider'].blockSignals(False)
            data['spin'].blockSignals(True)
            data['spin'].setValue(value)
            data['spin'].blockSignals(False)
            self.update_display()

    def on_spin_move(self, child_name, value, slider):
        slider.blockSignals(True)
        slider.setValue(int(value * 10))
        slider.blockSignals(False)
        self.apply_rotation(child_name, value)

    def apply_rotation(self, child_name, angle):
        """Apply rotation using the JointPanel's unified logic"""
        if child_name not in self.mw.joint_tab.joints:
            return
            
        # Call the JointPanel's logic to handle the actual 3D rotation
        # This ensures the object rotates exactly the same way as in the Joint tab
        self.mw.joint_tab.apply_joint_rotation(child_name, angle)
        
        # Refresh matrix display
        self.update_display()

    def update_display(self):
        self.text_area.clear()
        robot = self.mw.robot
        
        # Only show joints that exist in the Joint tab's "CREATED JOINTS" list
        created_joints = getattr(self.mw.joint_tab, 'joints', {})
        
        if not created_joints:
            self.text_area.append("No active joints created yet.")
            self.text_area.append("\nUse the 'Joint' tab to create a link first.")
            return

        self.text_area.append("--- ACTIVE JOINT MATRICES ---")
        self.text_area.append("")

        for child_name, data in created_joints.items():
            parent_name = data['parent']
            joint_id = data.get('joint_id', f"joint_{parent_name}_{child_name}")
            custom_name = data.get('custom_name', joint_id)
            
            if joint_id in robot.joints:
                joint = robot.joints[joint_id]
                self.text_area.append(f"Matrix: {custom_name}")
                
                # Full relative transform (Offset * Rotation)
                rot = joint.get_matrix()
                offset = joint.child_link.t_offset
                t_rel = offset @ rot
                
                self.text_area.append(self.format_matrix(t_rel))
                self.text_area.append("-" * 35) # Separator
                self.text_area.append("")

    def format_matrix(self, mat):
        lines = []
        for row in mat:
            lines.append("  ".join([f"{x:7.3f}" for x in row]))
        return "\n".join(lines)
