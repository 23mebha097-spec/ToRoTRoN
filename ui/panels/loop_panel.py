from PyQt5 import QtWidgets, QtCore
import json
import time

class LoopPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.recording = [] # List of frames (dict of joint_id: angle)
        self.is_recording = False
        self.is_playing = False
        self.current_frame_idx = 0
        
        self.record_timer = QtCore.QTimer()
        self.record_timer.timeout.connect(self._capture_frame)
        
        self.play_timer = QtCore.QTimer()
        self.play_timer.timeout.connect(self._play_next_frame)
        
        self.init_ui()

    def _group_style(self):
        return """
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #1976d2;
            }
        """

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        header = QtWidgets.QLabel("LOOP MODE")
        header.setStyleSheet("font-weight: bold; font-size: 16px; color: #1976d2; margin-bottom: 5px;")
        layout.addWidget(header)

        # --- Control Slider ---
        slider_group = QtWidgets.QGroupBox("Timeline Control")
        slider_group.setStyleSheet(self._group_style())
        slider_layout = QtWidgets.QVBoxLayout(slider_group)
        
        self.timeline_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setFixedHeight(40)
        self.timeline_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 8px; background: #eee; border-radius: 4px; }
            QSlider::handle:horizontal {
                background: white;
                border: 2px solid #1976d2;
                width: 18px;
                height: 18px;
                margin-top: -6px;
                border-radius: 9px;
            }
        """)
        self.timeline_slider.valueChanged.connect(self.on_slider_scrub)
        slider_layout.addWidget(self.timeline_slider)
        
        self.frame_label = QtWidgets.QLabel("Frame: 0/0")
        self.frame_label.setAlignment(QtCore.Qt.AlignCenter)
        slider_layout.addWidget(self.frame_label)
        
        layout.addWidget(slider_group)

        # --- Action Buttons ---
        btn_grid = QtWidgets.QGridLayout()
        btn_grid.setSpacing(10)

        self.btn_rec_start = QtWidgets.QPushButton("⏺ Record Start")
        self.btn_rec_start.setFixedHeight(45)
        self.btn_rec_start.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_rec_start.setStyleSheet("background-color: #ffebee; color: #c62828; font-weight: bold; border: 1px solid #ffcdd2; border-radius: 6px;")
        self.btn_rec_start.clicked.connect(self.start_recording)
        
        self.btn_rec_stop = QtWidgets.QPushButton("⏹ Record Stop")
        self.btn_rec_stop.setFixedHeight(45)
        self.btn_rec_stop.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_rec_stop.setStyleSheet("background-color: #f5f5f5; color: #424242; font-weight: bold; border: 1px solid #e0e0e0; border-radius: 6px;")
        self.btn_rec_stop.clicked.connect(self.stop_recording)
        self.btn_rec_stop.setEnabled(False)

        self.btn_loop_start = QtWidgets.QPushButton("▶ Start Loop")
        self.btn_loop_start.setFixedHeight(45)
        self.btn_loop_start.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_loop_start.setStyleSheet("background-color: #e3f2fd; color: #1565c0; font-weight: bold; border: 1px solid #bbdefb; border-radius: 6px;")
        self.btn_loop_start.clicked.connect(self.start_loop)
        
        self.btn_loop_stop = QtWidgets.QPushButton("⏹ End Loop")
        self.btn_loop_stop.setFixedHeight(45)
        self.btn_loop_stop.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_loop_stop.setStyleSheet("background-color: #f5f5f5; color: #424242; font-weight: bold; border: 1px solid #e0e0e0; border-radius: 6px;")
        self.btn_loop_stop.clicked.connect(self.stop_loop)
        self.btn_loop_stop.setEnabled(False)

        btn_grid.addWidget(self.btn_rec_start, 0, 0)
        btn_grid.addWidget(self.btn_rec_stop, 0, 1)
        btn_grid.addWidget(self.btn_loop_start, 1, 0)
        btn_grid.addWidget(self.btn_loop_stop, 1, 1)

        layout.addLayout(btn_grid)
        
        # --- Joint Control Section (Digital Twin Interface) ---
        self.joints_group = QtWidgets.QGroupBox("Live Joint Controls")
        self.joints_group.setStyleSheet(self._group_style())
        joints_layout = QtWidgets.QVBoxLayout(self.joints_group)
        
        self.joints_scroll = QtWidgets.QScrollArea()
        self.joints_scroll.setWidgetResizable(True)
        self.joints_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.joints_scroll.setStyleSheet("background: #fdfdfd; border: 1px solid #e0e0e0; border-radius: 5px;")
        
        self.joints_container = QtWidgets.QWidget()
        self.joints_layout = QtWidgets.QVBoxLayout(self.joints_container)
        self.joints_layout.setAlignment(QtCore.Qt.AlignTop)
        self.joints_scroll.setWidget(self.joints_container)
        
        joints_layout.addWidget(self.joints_scroll)
        layout.addWidget(self.joints_group)

        layout.addStretch()
        
        self.sliders = {}  # {joint_id: {'slider': slider, 'spin': spin}}
        
        # Monitor timer to update the UI frequently (checks for new joints)
        self.monitor_timer = QtCore.QTimer(self)
        self.monitor_timer.timeout.connect(self.sync_sliders_to_robot)
        self.monitor_timer.start(300) 

    def sync_sliders_to_robot(self):
        """Update or create sliders based on the current robot joints."""
        if not self.isVisible() and not self.is_recording: return
        
        robot = self.mw.robot
        current_joints = list(robot.joints.keys())
        
        # Check if the set of joints has changed (need rebuild)
        existing_joints = list(self.sliders.keys())
        if sorted(current_joints) != sorted(existing_joints):
            self._rebuild_sliders(current_joints)
            
        # Update values if not interacting
        for jid in current_joints:
            if jid in self.sliders:
                slider = self.sliders[jid]['slider']
                spin = self.sliders[jid]['spin']
                
                # Only update if the user isn't actively dragging it
                if not slider.isSliderDown():
                    val = robot.joints[jid].current_deg
                    slider.blockSignals(True)
                    slider.setValue(int(val * 10))
                    slider.blockSignals(False)
                    
                    spin.blockSignals(True)
                    spin.setValue(val)
                    spin.blockSignals(False)

    def _rebuild_sliders(self, joint_ids):
        # Clear existing
        while self.joints_layout.count():
            item = self.joints_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self.sliders.clear()
        
        if not joint_ids:
            empty = QtWidgets.QLabel("No active joints. Create joints in the Joint tab.")
            empty.setStyleSheet("color: #9e9e9e; font-style: italic;")
            self.joints_layout.addWidget(empty)
            return

        for jid in sorted(joint_ids):
            joint = self.mw.robot.joints[jid]
            
            # Container
            group = QtWidgets.QFrame()
            group.setStyleSheet("background: transparent; border-radius: 4px; margin-bottom: 2px;")
            glay = QtWidgets.QVBoxLayout(group)
            glay.setContentsMargins(5, 5, 5, 5)
            
            # Label
            lbl = QtWidgets.QLabel(f"● {jid}")
            lbl.setStyleSheet("color: #1976d2; font-weight: bold; font-family: 'Consolas', monospace;")
            glay.addWidget(lbl)
            
            # Row for slider + spin
            row = QtWidgets.QHBoxLayout()
            
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(int(joint.min_limit * 10), int(joint.max_limit * 10))
            slider.setValue(int(joint.current_deg * 10))
            slider.setCursor(QtCore.Qt.PointingHandCursor)
            slider.setStyleSheet("""
                QSlider::groove:horizontal { height: 6px; background: #eee; border-radius: 3px; border: 1px solid #ccc; }
                QSlider::handle:horizontal {
                    background: white; border: 2px solid #1976d2;
                    width: 14px; height: 14px; margin-top: -4px; border-radius: 7px;
                }
            """)
            
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(joint.min_limit, joint.max_limit)
            spin.setValue(joint.current_deg)
            spin.setFixedWidth(70)
            spin.setStyleSheet("""
                QDoubleSpinBox {
                    background: white; color: #333; border: 1px solid #ccc;
                    border-radius: 3px; padding: 2px;
                }
            """)
            
            slider.valueChanged.connect(lambda v, c=jid, s=spin: self.on_slider_move(c, v/10.0, s))
            spin.valueChanged.connect(lambda v, c=jid, sl=slider: self.on_spin_move(c, v, sl))
            
            row.addWidget(slider)
            row.addWidget(spin)
            glay.addLayout(row)
            
            self.joints_layout.addWidget(group)
            self.sliders[jid] = {'slider': slider, 'spin': spin}

    def on_slider_move(self, jid, value, spinbox):
        spinbox.blockSignals(True)
        spinbox.setValue(value)
        spinbox.blockSignals(False)
        self.apply_rotation(jid, value)

    def on_spin_move(self, jid, value, slider):
        slider.blockSignals(True)
        slider.setValue(int(value * 10))
        slider.blockSignals(False)
        self.apply_rotation(jid, value)

    def apply_rotation(self, jid, angle):
        if jid not in self.mw.robot.joints: return
        
        # Apply to local robot instance
        joint = self.mw.robot.joints[jid]
        joint.current_deg = angle
        
        # Hardware sync if needed
        if hasattr(self.mw, 'serial_mgr') and self.mw.serial_mgr.is_connected:
            speed = float(getattr(self.mw, 'current_speed', 50))
            self.mw.serial_mgr.send_command(jid, angle, speed=speed)
            
        # Update 3D
        self.mw.robot.update_kinematics()
        if hasattr(self.mw, 'canvas'):
            self.mw.canvas.update_transforms(self.mw.robot)
            
        # Sync to joint tab if present
        if hasattr(self.mw, 'joint_tab'):
            self._sync_joint_panel_ui(jid, angle)
            
    def _sync_joint_panel_ui(self, joint_id, value):
        """Silently syncs the JointPanel UI if it's currently displaying this joint."""
        jt = self.mw.joint_tab
        link_name = None
        for name, data in getattr(jt, 'joints', {}).items():
            if data.get('joint_id') == joint_id:
                link_name = name
                break

        if link_name:
            jt.joints[link_name]['current_angle'] = value
            if getattr(jt, 'active_joint_control', None) == link_name:
                if hasattr(jt, 'joint_control_slider'):
                    jt.joint_control_slider.blockSignals(True)
                    jt.joint_control_slider.setValue(int(value * 10))
                    jt.joint_control_slider.blockSignals(False)
                if hasattr(jt, 'joint_control_spinbox'):
                    jt.joint_control_spinbox.blockSignals(True)
                    jt.joint_control_spinbox.setValue(value)
                    jt.joint_control_spinbox.blockSignals(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_sliders_to_robot()

    def start_recording(self):
        self.recording = []
        self.is_recording = True
        self.btn_rec_start.setEnabled(False)
        self.btn_rec_stop.setEnabled(True)
        self.btn_loop_start.setEnabled(False)
        self.record_timer.start(100) # 10 FPS
        self.mw.log("Loop Mode: Recording started.")

    def stop_recording(self):
        self.is_recording = False
        self.record_timer.stop()
        self.btn_rec_start.setEnabled(True)
        self.btn_rec_stop.setEnabled(False)
        self.btn_loop_start.setEnabled(len(self.recording) > 0)
        
        self.timeline_slider.setRange(0, len(self.recording) - 1)
        self.timeline_slider.setValue(0)
        self._update_label()
        self.mw.log(f"Loop Mode: Recording finished. Captured {len(self.recording)} frames.")

    def start_loop(self):
        if not self.recording: return
        self.is_playing = True
        self.current_frame_idx = 0
        self.btn_loop_start.setEnabled(False)
        self.btn_loop_stop.setEnabled(True)
        self.btn_rec_start.setEnabled(False)
        self.play_timer.start(100)
        self.mw.log("Loop Mode: Playing sequence.")

    def stop_loop(self):
        self.is_playing = False
        self.play_timer.stop()
        self.btn_loop_start.setEnabled(True)
        self.btn_loop_stop.setEnabled(False)
        self.btn_rec_start.setEnabled(True)
        self.mw.log("Loop Mode: Sequence stopped.")

    def _capture_frame(self):
        frame = {}
        for jid, joint in self.mw.robot.joints.items():
            frame[jid] = joint.current_deg
        self.recording.append(frame)
        self.timeline_slider.setRange(0, len(self.recording) - 1)
        self.timeline_slider.setValue(len(self.recording) - 1)
        self._update_label()

    def _play_next_frame(self):
        if not self.recording: return
        self.current_frame_idx = (self.current_frame_idx + 1) % len(self.recording)
        self.timeline_slider.setValue(self.current_frame_idx)
        self._apply_frame(self.recording[self.current_frame_idx])
        self._update_label()

    def on_slider_scrub(self, val):
        if not self.recording: return
        self.current_frame_idx = val
        if not self.is_playing:
            self._apply_frame(self.recording[val])
        self._update_label()

    def _apply_frame(self, frame_data):
        for jid, angle in frame_data.items():
            if jid in self.mw.robot.joints:
                self.mw.robot.joints[jid].current_deg = angle
                
                # Send to Hardware (Digital Twin Sync)
                if hasattr(self.mw, 'serial_mgr') and self.mw.serial_mgr.is_connected:
                    speed = float(getattr(self.mw, 'current_speed', 50))
                    # Use send_command for real-time mirroring
                    self.mw.serial_mgr.send_command(jid, angle, speed=speed)
        
        # Recalculate kinematics and update 3D view
        self.mw.robot.update_kinematics()
        if hasattr(self.mw, 'canvas'):
            self.mw.canvas.update_transforms(self.mw.robot)
        # Update sliders in joint panel if visible
        if hasattr(self.mw, 'joint_tab'):
            for jid, angle in frame_data.items():
                self._sync_joint_panel_ui(jid, angle)

    def _update_label(self):
        total = len(self.recording)
        curr = self.timeline_slider.value() + 1 if total > 0 else 0
        self.frame_label.setText(f"Frame: {curr}/{total}")
