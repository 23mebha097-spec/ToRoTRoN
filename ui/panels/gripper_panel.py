from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np

class TypeOnlyDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def stepBy(self, steps): pass
    def wheelEvent(self, event): event.ignore()

class GripperPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # --- HEADER ---
        header = QtWidgets.QLabel("GRIPPER CONTROL")
        header.setStyleSheet("font-weight: bold; font-size: 16px; color: #2e7d32; margin-bottom: 5px;")
        layout.addWidget(header)

        # --- JOINT SELECTION BOX ---
        selection_group = QtWidgets.QGroupBox("1. SELECT GRIPPER JOINT")
        selection_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #616161;
            }
        """)
        sel_layout = QtWidgets.QVBoxLayout(selection_group)
        
        self.joints_list = QtWidgets.QListWidget()
        self.joints_list.setFixedHeight(120)
        self.joints_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #f5f5f5; }
            QListWidget::item:selected { background: #e8f5e9; color: #2e7d32; }
        """)
        self.joints_list.itemClicked.connect(self.on_joint_selected)
        sel_layout.addWidget(self.joints_list)

        self.mark_gripper_check = QtWidgets.QCheckBox("Mark as Gripper")
        self.mark_gripper_check.setStyleSheet("font-weight: bold; color: #2e7d32; padding: 5px;")
        self.mark_gripper_check.toggled.connect(self.on_mark_toggled)
        sel_layout.addWidget(self.mark_gripper_check)
        
        layout.addWidget(selection_group)

        # --- MANUAL CONTROL BOX ---
        control_group = QtWidgets.QGroupBox("2. MANUAL ACTIONS")
        control_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #616161;
            }
        """)
        ctrl_layout = QtWidgets.QVBoxLayout(control_group)

        # Precision Stroke
        ctrl_layout.addWidget(QtWidgets.QLabel("Precision Stroke:"))
        self.stroke_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.stroke_slider.setRange(0, 100)
        self.stroke_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background: #eee; border-radius: 3px; }
            QSlider::handle:horizontal { background: white; border: 2px solid #2e7d32; width: 14px; height: 14px; margin-top: -5px; border-radius: 7px; }
        """)
        self.stroke_slider.valueChanged.connect(self.on_stroke_changed)
        ctrl_layout.addWidget(self.stroke_slider)

        layout.addWidget(control_group)

        layout.addStretch()

    def refresh_joints(self):
        """Update the list of available joints, showing all joints involved in relations."""
        self.joints_list.clear()
        
        related_joints = set()
        for master, slaves in self.mw.robot.joint_relations.items():
            related_joints.add(master)
            for slave_id, _ in slaves:
                related_joints.add(slave_id)
        
        # Populate the list with all related joints
        for name, joint in self.mw.robot.joints.items():
            if name in related_joints:
                # Show parent and child link names for easier ID
                display_name = f"{joint.parent_link.name} → {joint.child_link.name} ({name})"
                item = QtWidgets.QListWidgetItem(display_name)
                item.setData(QtCore.Qt.UserRole, name) # Store real joint ID
                self.joints_list.addItem(item)

    def on_joint_selected(self, item):
        name = item.data(QtCore.Qt.UserRole)
        if not name: return
        joint = self.mw.robot.joints[name]
        self.mark_gripper_check.blockSignals(True)
        self.mark_gripper_check.setChecked(joint.is_gripper)
        self.mark_gripper_check.blockSignals(False)
        
        # Sync slider with current joint value
        val_pct = int((joint.current_value - joint.min_limit) / (joint.max_limit - joint.min_limit) * 100)
        self.stroke_slider.blockSignals(True)
        self.stroke_slider.setValue(val_pct)
        self.stroke_slider.blockSignals(False)

    def on_mark_toggled(self, checked):
        item = self.joints_list.currentItem()
        if not item: return
        
        name = item.data(QtCore.Qt.UserRole)
        robot = self.mw.robot
        
        # 1. Update selected joint
        robot.joints[name].is_gripper = checked
        
        # 2. PROJECTION: Propagate to ALL related joints (Master <-> Slave)
        # Identify the full "Relation Chain"
        rel_chain = {name}
        if name in robot.joint_relations:
            for s_id, _ in robot.joint_relations[name]: rel_chain.add(s_id)
        else:
            for m_id, slaves in robot.joint_relations.items():
                if any(s[0] == name for s in slaves):
                    rel_chain.add(m_id)
                    for sid, _ in slaves: rel_chain.add(sid)
        
        for j_id in rel_chain:
            if j_id in robot.joints:
                robot.joints[j_id].is_gripper = checked
        
        self.mw.log(f"🔗 Gripper Linkage: All {len(rel_chain)} related joints marked as {'Gripper' if checked else 'Standard'}")
        
        # Sync with JointPanel UI
        if hasattr(self.mw.joint_tab, 'gripper_checkbox'):
            self.mw.joint_tab.gripper_checkbox.blockSignals(True)
            self.mw.joint_tab.gripper_checkbox.setChecked(checked)
            self.mw.joint_tab.gripper_checkbox.blockSignals(False)
            self.mw.joint_tab.refresh_links()

    def _propagate_relation(self, joint_name, value):
        """Propagate movement across related joints (bidirectional)."""
        robot = self.mw.robot
        
        # 1. If this is a master, propagate to all slaves
        if joint_name in robot.joint_relations:
            for slave_id, ratio in robot.joint_relations[joint_name]:
                if slave_id in robot.joints:
                    slave_joint = robot.joints[slave_id]
                    slave_val = np.clip(value * ratio, slave_joint.min_limit, slave_joint.max_limit)
                    self._update_joint_silent(slave_id, slave_val)
                    
        # 2. If this is a slave, find the master and update it (and then other slaves)
        else:
            for master_id, slaves in robot.joint_relations.items():
                for slave_id, ratio in slaves:
                    if slave_id == joint_name and abs(ratio) > 1e-6:
                        # master * ratio = slave -> master = slave / ratio
                        master_val = value / ratio
                        master_joint = robot.joints.get(master_id)
                        if master_joint:
                            master_val = np.clip(master_val, master_joint.min_limit, master_joint.max_limit)
                            self._update_joint_silent(master_id, master_val)
                            
                            # Recursively update other slaves of this master
                            for other_slave_id, other_ratio in robot.joint_relations[master_id]:
                                if other_slave_id != joint_name:
                                    other_val = np.clip(master_val * other_ratio, 
                                                        robot.joints[other_slave_id].min_limit, 
                                                        robot.joints[other_slave_id].max_limit)
                                    self._update_joint_silent(other_slave_id, other_val)
                        break

    def _update_joint_silent(self, joint_id, value):
        """Update a joint value and sync UI without triggering signals."""
        if joint_id not in self.mw.robot.joints: return
        
        joint = self.mw.robot.joints[joint_id]
        joint.current_value = value
        
        # Sync JointPanel local data
        if hasattr(self.mw, 'joint_tab'):
            # Find the link name for this joint_id
            link_name = None
            for name, data in self.mw.joint_tab.joints.items():
                if data.get('joint_id') == joint_id:
                    link_name = name
                    break
            if link_name:
                self.mw.joint_tab.joints[link_name]['current_angle'] = value
                # If this is the active control in joint tab, update its slider
                if self.mw.joint_tab.active_joint_control == link_name:
                    self.mw.joint_tab.joint_control_slider.blockSignals(True)
                    self.mw.joint_tab.joint_control_slider.setValue(int(value * 10))
                    self.mw.joint_tab.joint_control_slider.blockSignals(False)
                    self.mw.joint_tab.joint_control_spinbox.blockSignals(True)
                    self.mw.joint_tab.joint_control_spinbox.setValue(value)
                    self.mw.joint_tab.joint_control_spinbox.blockSignals(False)
        
        # Sync MatricesPanel
        if hasattr(self.mw, 'matrices_tab'):
            self.mw.matrices_tab.sync_slider(link_name if link_name else joint_id, value)

    def on_stroke_changed(self, value):
        item = self.joints_list.currentItem()
        if not item: return
        
        name = item.data(QtCore.Qt.UserRole)
        joint = self.mw.robot.joints[name]
        # Map percentage to joint limits
        target = joint.min_limit + (value / 100.0) * (joint.max_limit - joint.min_limit)
        
        # Move selected joint
        joint.current_value = target
        
        # Propagate to all related joints (bidirectional)
        self._propagate_relation(name, target)
        
        self.mw.robot.update_kinematics()
        self.mw.canvas.update_transforms(self.mw.robot)
