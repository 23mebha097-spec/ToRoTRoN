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
        header_matrices.setStyleSheet("color: #1976d2; font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(header_matrices)

        self.refresh_btn = QtWidgets.QPushButton("Update Matrices")
        self.refresh_btn.clicked.connect(self.update_display)
        layout.addWidget(self.refresh_btn)
        
        self.text_area = QtWidgets.QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QtGui.QFont("Consolas", 10))
        self.text_area.setStyleSheet("background-color: white; color: #1565c0; border: 1px solid #e0e0e0;")
        layout.addWidget(self.text_area)

        # Bottom: Joint Control Sliders
        header_sliders = QtWidgets.QLabel("Joint Rotation Controls")
        header_sliders.setStyleSheet("color: #1976d2; font-size: 15px; font-weight: bold; margin-top: 15px; padding: 5px;")
        layout.addWidget(header_sliders)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: white; border: none;")
        
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
            empty_msg.setStyleSheet("color: #9e9e9e; font-style: italic; padding: 10px;")
            self.slider_layout.addWidget(empty_msg)
            return

        for child_name, data in joint_data.items():
            # Hide slave joints - their movement is driven by the master
            joint_id = data.get('joint_id', child_name)
            is_slave = False
            for master, slaves in self.mw.robot.joint_relations.items():
                if any(s_id == joint_id for s_id, r in slaves):
                    is_slave = True
                    break
            
            if is_slave:
                continue

            # Container for each joint's control
            group = QtWidgets.QFrame()
            group.setStyleSheet("background-color: transparent; border-radius: 5px; margin-bottom: 5px;")
            glay = QtWidgets.QVBoxLayout(group)
            glay.setContentsMargins(10, 8, 10, 8)
            
            # Label: Custom Name Only
            custom_name = data.get('custom_name', f"{data['parent']} \u2192 {child_name}")
            lbl = QtWidgets.QLabel(f"{custom_name} ({['X','Y','Z'][data['axis']]})")
            lbl.setStyleSheet("color: #1976d2; font-weight: bold; font-size: 13px;")
            glay.addWidget(lbl)
            
            # Slider Row
            row = QtWidgets.QHBoxLayout()
            
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(int(data['min'] * 10), int(data['max'] * 10))
            slider.setValue(int(data.get('current_angle', 0.0) * 10))
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
            
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(data['min'], data['max'])
            spin.setValue(data.get('current_angle', 0.0))
            spin.setFixedWidth(70)
            spin.setStyleSheet("""
                QDoubleSpinBox {
                    background: white;
                    color: #1976d2;
                    border: 1px solid #1976d2;
                    border-radius: 3px;
                    padding: 2px;
                    font-weight: bold;
                }
            """)
            
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

        self.text_area.append("--- ACTIVE JOINT MATRICES (cm) ---")
        self.text_area.append("")

        for child_name, data in created_joints.items():
            # Skip slave joints - we only show master/independent matrices
            joint_id = data.get('joint_id', child_name)
            is_slave = False
            for master, slaves in robot.joint_relations.items():
                if any(s_id == joint_id for s_id, r in slaves):
                    is_slave = True
                    break
            
            if is_slave:
                continue

            parent_name = data['parent']
            joint_id = data.get('joint_id', f"joint_{parent_name}_{child_name}")
            custom_name = data.get('custom_name', joint_id)
            
            if joint_id in robot.joints:
                joint = robot.joints[joint_id]
                self.text_area.append(f"Matrix: {custom_name} (cm)")
                
                # Full relative transform (Offset * Rotation)
                rot = joint.get_matrix()
            if joint.child_link:
                offset = joint.child_link.t_offset
                t_rel = offset @ rot
                
                # Calculation summary in CM
                ratio = self.mw.canvas.grid_units_per_cm
                tx, ty, tz = t_rel[:3, 3] / ratio
                self.text_area.append(f"  Pos (cm):  X: {tx:.3f}, Y: {ty:.3f}, Z: {tz:.3f}")
                
                # Full 4x4 matrix
                self.text_area.append(self.format_matrix(t_rel))
                self.text_area.append("-" * 40)
                self.text_area.append("-" * 35) # Separator
                self.text_area.append("")

    def format_matrix(self, mat):
        # Scale translation to CM based on adjustable graph ratio
        ratio = self.mw.canvas.grid_units_per_cm
        mat_cm = np.copy(mat)
        mat_cm[:3, 3] /= ratio
        
        lines = []
        for row in mat_cm:
            lines.append("  ".join([f"{x:7.3f}" for x in row]))
        return "\n".join(lines)
