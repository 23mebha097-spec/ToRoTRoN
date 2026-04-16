from PyQt5 import QtWidgets, QtCore, QtGui
import json
import numpy as np
import traceback


class TypeOnlyDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def stepBy(self, steps): pass
    def wheelEvent(self, event): event.ignore()

class SimulationPanel(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.sliders = {}
        self.matrix_labels = {}
        
        self._target_gripper_angles = {}
        self._env_collision_manager = None
        
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
        self.welding_btn = self.create_tab_button("Welding", "assets/simulation.png")
        self.painting_btn = self.create_tab_button("Painting", "assets/simulation.png")

        self.joints_btn.clicked.connect(lambda: self.switch_view(0))
        self.matrices_btn.clicked.connect(lambda: self.switch_view(1))
        self.objects_btn.clicked.connect(lambda: self.switch_view(2))
        self.welding_btn.clicked.connect(lambda: self.switch_view(3))
        self.painting_btn.clicked.connect(lambda: self.switch_view(4))
        
        tab_layout.addWidget(self.joints_btn)
        tab_layout.addWidget(self.matrices_btn)
        tab_layout.addWidget(self.objects_btn)
        tab_layout.addWidget(self.welding_btn)
        tab_layout.addWidget(self.painting_btn)
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

        self.import_btn = QtWidgets.QPushButton("ðŸ“¦ Import Object")
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

        self.update_btn = QtWidgets.QPushButton("ðŸ”„ Update Position")
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

        self.start_btn = QtWidgets.QPushButton("ðŸš€ Start Simulation")
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
        self.grip_fixed_rotation = None
        self.grip_local_center = None
        self.grip_anchor_world = None
        
        self.sim_timer = QtCore.QTimer(self)
        self.sim_timer.timeout.connect(self._safe_on_sim_tick)
        
        # Sequenced Motion State
        self.sim_state = "IDLE" 
        self.target_joint_values = {} 
        self.active_joint_index = 0
        self.current_tcp = None
        self.motion_speed = 5.0 # Initial default
        self.pick_place_plan = {}
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

        # --- OBJECT PROPERTIES PANEL ---
        self.prop_group = QtWidgets.QGroupBox("Object Info")
        self.prop_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: bold;
                color: #555;
            }
        """)
        prop_vbox = QtWidgets.QVBoxLayout(self.prop_group)
        prop_vbox.setSpacing(5)
        
        self.dim_label = QtWidgets.QLabel("Dimensions: ---")
        self.dim_label.setStyleSheet("font-size: 11px; color: #1976d2; font-weight: bold;")
        prop_vbox.addWidget(self.dim_label)
        
        self.pos_label = QtWidgets.QLabel("Current Pos: ---")
        self.pos_label.setStyleSheet("font-size: 11px; color: #424242;")
        prop_vbox.addWidget(self.pos_label)
        
        self.capture_btn = QtWidgets.QPushButton("ðŸŽ¯ Set Object as P1")
        self.capture_btn.setFixedHeight(30)
        self.capture_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.capture_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #1976d2;
                border: 1px solid #1976d2;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                margin-top: 5px;
            }
            QPushButton:hover { background-color: #e3f2fd; }
        """)
        self.capture_btn.clicked.connect(self.capture_object_to_p1)
        prop_vbox.addWidget(self.capture_btn)
        
        self.set_lp_btn = QtWidgets.QPushButton("ðŸŽ¯ Set as Live Point (TCP)")
        self.set_lp_btn.setFixedHeight(30)
        self.set_lp_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_lp_btn.setToolTip("Set the selected object as the Live Point (Tool Center Point)")
        self.set_lp_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #d32f2f;
                border: 1px solid #d32f2f;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                margin-top: 5px;
            }
            QPushButton:hover { background-color: #ffebee; }
        """)
        self.set_lp_btn.clicked.connect(self.set_custom_lp)
        prop_vbox.addWidget(self.set_lp_btn)
        
        self.objects_layout.addWidget(self.prop_group)

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

        # HOME Row
        home_lbl = QtWidgets.QLabel("HOME")
        home_lbl.setStyleSheet("font-weight: bold; color: #455A64; font-size: 13px;")
        home_lbl.setToolTip("Home position reached after the pick-and-place cycle completes")
        self.home_x = self.create_coord_sb("#455A64", save_on_change=False)
        self.home_y = self.create_coord_sb("#455A64", save_on_change=False)
        self.home_z = self.create_coord_sb("#455A64", save_on_change=False)

        points_grid.addWidget(home_lbl, 2, 0)
        points_grid.addWidget(self.home_x, 2, 1)
        points_grid.addWidget(self.home_y, 2, 2)
        points_grid.addWidget(self.home_z, 2, 3)

        # LP Row
        lp_lbl = QtWidgets.QLabel("LP")
        lp_lbl.setStyleSheet("font-weight: bold; color: #D32F2F; font-size: 13px;")
        self.live_x = self.create_coord_sb("#D32F2F")
        self.live_y = self.create_coord_sb("#D32F2F")
        self.live_z = self.create_coord_sb("#D32F2F")
        for sb in [self.live_x, self.live_y, self.live_z]:
            sb.setReadOnly(True)

        points_grid.addWidget(lp_lbl, 3, 0)
        points_grid.addWidget(self.live_x, 3, 1)
        points_grid.addWidget(self.live_y, 3, 2)
        points_grid.addWidget(self.live_z, 3, 3)

        # DIM Row (New: Industrial Dimensions)
        dim_lbl = QtWidgets.QLabel("DIM")
        dim_lbl.setStyleSheet("font-weight: bold; color: #7B1FA2; font-size: 13px;")
        dim_lbl.setToolTip("Object Dimensions (Length, Width, Height) in cm")
        self.obj_width = self.create_coord_sb("#7B1FA2")
        self.obj_depth = self.create_coord_sb("#7B1FA2")
        self.obj_height = self.create_coord_sb("#7B1FA2")
        
        points_grid.addWidget(dim_lbl, 4, 0)
        points_grid.addWidget(self.obj_width, 4, 1)
        points_grid.addWidget(self.obj_depth, 4, 2)
        points_grid.addWidget(self.obj_height, 4, 3)

        # SPEED Row
        speed_lbl = QtWidgets.QLabel("SPD")
        speed_lbl.setStyleSheet("font-weight: bold; color: #ff9800; font-size: 13px;")
        speed_lbl.setToolTip("Motion Speed (Degrees per Tick)")
        self.motion_speed_sb = QtWidgets.QDoubleSpinBox()
        self.motion_speed_sb.setRange(0.1, 20.0)
        self.motion_speed_sb.setValue(5.0)
        self.motion_speed_sb.setSuffix(" Â°/t")
        self.motion_speed_sb.setStyleSheet("""
            QDoubleSpinBox {
                background: white;
                color: #ff9800;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
                padding: 2px 4px;
                font-weight: bold;
            }
        """)
        self.motion_speed_sb.valueChanged.connect(self.update_motion_speed)
        
        points_grid.addWidget(speed_lbl, 5, 0)
        points_grid.addWidget(self.motion_speed_sb, 5, 1, 1, 3)

        # Back-link coordinates back to main_window for Mixin methods
        self.main_window.pick_x, self.main_window.pick_y, self.main_window.pick_z = self.pick_x, self.pick_y, self.pick_z
        self.main_window.place_x, self.main_window.place_y, self.main_window.place_z = self.place_x, self.place_y, self.place_z
        self.main_window.home_x, self.main_window.home_y, self.main_window.home_z = self.home_x, self.home_y, self.home_z
        self.main_window.live_x, self.main_window.live_y, self.main_window.live_z = self.live_x, self.live_y, self.live_z
        self.main_window.obj_width, self.main_window.obj_depth, self.main_window.obj_height = self.obj_width, self.obj_depth, self.obj_height

        coord_layout.addLayout(points_grid)
        self.objects_layout.addWidget(coord_container)
        self.objects_layout.addStretch()

        self.stack.addWidget(self.objects_view)

        # 4. Welding View (Blank â€” logic TBD)
        self.welding_view = QtWidgets.QWidget()
        welding_layout = QtWidgets.QVBoxLayout(self.welding_view)
        welding_layout.setContentsMargins(10, 10, 10, 10)
        welding_layout.setSpacing(15)

        welding_title = QtWidgets.QLabel("ðŸ”¥ WELDING MODE")
        welding_title.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #e65100; margin-bottom: 5px;"
        )
        welding_title.setAlignment(QtCore.Qt.AlignCenter)
        welding_layout.addWidget(welding_title)

        welding_header = QtWidgets.QLabel("WELDING ASSEMBLY")
        welding_header.setStyleSheet("color: #424242; font-size: 14px; font-weight: bold; margin-top: 5px;")
        welding_layout.addWidget(welding_header)

        self.weld_import_btn = QtWidgets.QPushButton("ðŸ“¥ Import STEP / STL")
        self.weld_import_btn.setFixedHeight(40)
        self.weld_import_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.weld_import_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #e65100;
                border: 2px solid #e65100;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #fff3e0; }
        """)
        self.weld_import_btn.clicked.connect(self.main_window.import_mesh)
        welding_layout.addWidget(self.weld_import_btn)

        self.weld_pick_btn = QtWidgets.QPushButton("â›ï¸ Select Welding Edges")
        self.weld_pick_btn.setFixedHeight(45)
        self.weld_pick_btn.setCheckable(True)
        self.weld_pick_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.weld_pick_btn.setStyleSheet("""
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
        """)
        self.weld_pick_btn.clicked.connect(self.toggle_welding_edge_picking)
        welding_layout.addWidget(self.weld_pick_btn)

        self.weld_edges_list = QtWidgets.QListWidget()
        self.weld_edges_list.setFixedHeight(150)
        self.weld_edges_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 6px;
                background: white;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #f0f0f0; }
        """)
        welding_layout.addWidget(self.weld_edges_list)

        weld_params_group = QtWidgets.QGroupBox("Weld Path Parameters")
        weld_params_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #5d4037;
            }
        """)
        weld_params = QtWidgets.QGridLayout(weld_params_group)
        weld_params.setSpacing(6)

        weld_params.addWidget(QtWidgets.QLabel("Weld Type:"), 0, 0)
        self.weld_type_combo = QtWidgets.QComboBox()
        self.weld_type_combo.addItems(["Auto", "Fillet", "Butt", "Lap"])
        self.weld_type_combo.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 3px 6px;")
        weld_params.addWidget(self.weld_type_combo, 0, 1)

        weld_params.addWidget(QtWidgets.QLabel("Step Size (mm):"), 1, 0)
        self.weld_step_sb = QtWidgets.QDoubleSpinBox()
        self.weld_step_sb.setRange(0.5, 100.0)
        self.weld_step_sb.setValue(5.0)
        self.weld_step_sb.setSuffix(" mm")
        self.weld_step_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        weld_params.addWidget(self.weld_step_sb, 1, 1)

        weld_params.addWidget(QtWidgets.QLabel("Offset (mm):"), 2, 0)
        self.weld_offset_sb = QtWidgets.QDoubleSpinBox()
        self.weld_offset_sb.setRange(-50.0, 50.0)
        self.weld_offset_sb.setValue(0.0)
        self.weld_offset_sb.setSuffix(" mm")
        self.weld_offset_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        weld_params.addWidget(self.weld_offset_sb, 2, 1)

        weld_params.addWidget(QtWidgets.QLabel("Torch Angle (deg):"), 3, 0)
        self.weld_torch_angle_sb = QtWidgets.QDoubleSpinBox()
        self.weld_torch_angle_sb.setRange(0.0, 180.0)
        self.weld_torch_angle_sb.setValue(45.0)
        self.weld_torch_angle_sb.setSuffix(" °")
        self.weld_torch_angle_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        weld_params.addWidget(self.weld_torch_angle_sb, 3, 1)

        weld_params.addWidget(QtWidgets.QLabel("Approach (mm):"), 4, 0)
        self.weld_approach_sb = QtWidgets.QDoubleSpinBox()
        self.weld_approach_sb.setRange(0.0, 500.0)
        self.weld_approach_sb.setValue(25.0)
        self.weld_approach_sb.setSuffix(" mm")
        self.weld_approach_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        weld_params.addWidget(self.weld_approach_sb, 4, 1)

        weld_params.addWidget(QtWidgets.QLabel("Retract (mm):"), 5, 0)
        self.weld_retract_sb = QtWidgets.QDoubleSpinBox()
        self.weld_retract_sb.setRange(0.0, 500.0)
        self.weld_retract_sb.setValue(25.0)
        self.weld_retract_sb.setSuffix(" mm")
        self.weld_retract_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        weld_params.addWidget(self.weld_retract_sb, 5, 1)

        weld_params.addWidget(QtWidgets.QLabel("Feed (mm/s):"), 6, 0)
        self.weld_feed_sb = QtWidgets.QDoubleSpinBox()
        self.weld_feed_sb.setRange(1.0, 500.0)
        self.weld_feed_sb.setValue(10.0)
        self.weld_feed_sb.setSuffix(" mm/s")
        self.weld_feed_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        weld_params.addWidget(self.weld_feed_sb, 6, 1)

        welding_layout.addWidget(weld_params_group)

        btn_row = QtWidgets.QHBoxLayout()
        clear_weld_btn = QtWidgets.QPushButton("🗑️ Clear Edges")
        clear_weld_btn.setFixedHeight(32)
        clear_weld_btn.setCursor(QtCore.Qt.PointingHandCursor)
        clear_weld_btn.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ccc; border-radius: 4px;")
        clear_weld_btn.clicked.connect(self.clear_welding_edges)
        btn_row.addWidget(clear_weld_btn)

        self.start_weld_btn = QtWidgets.QPushButton("▶ Start Welding")
        self.start_weld_btn.setFixedHeight(32)
        self.start_weld_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.start_weld_btn.setStyleSheet("""
            QPushButton {
                background-color: #e65100;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #ef6c00; }
            QPushButton:pressed { background-color: #d84315; }
        """)
        self.start_weld_btn.clicked.connect(self.start_welding_sequence)
        btn_row.addWidget(self.start_weld_btn)
        welding_layout.addLayout(btn_row)

        self.weld_summary_label = QtWidgets.QLabel("Selected edges: 0")
        self.weld_summary_label.setStyleSheet("color: #424242; font-size: 12px; font-weight: bold;")
        welding_layout.addWidget(self.weld_summary_label)

        self.weld_json_view = QtWidgets.QPlainTextEdit()
        self.weld_json_view.setReadOnly(True)
        self.weld_json_view.setPlaceholderText("Generated welding JSON will appear here...")
        self.weld_json_view.setMinimumHeight(220)
        self.weld_json_view.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                background: #fafafa;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        welding_layout.addWidget(self.weld_json_view)

        welding_info = QtWidgets.QLabel(
            "Select one or more edges on the imported workpiece. The generator will build a weld path JSON with approach, travel, and retract moves."
        )
        welding_info.setStyleSheet("color: #757575; font-size: 11px; font-style: italic;")
        welding_info.setWordWrap(True)
        welding_layout.addWidget(welding_info)

        self.weld_move_tabs = QtWidgets.QTabWidget()
        self.weld_move_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: #fafafa;
            }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 5px 14px;
                font-weight: bold;
                font-size: 12px;
                color: #757575;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #fafafa;
                color: #e65100;
                border-bottom: 2px solid #e65100;
            }
        """)

        live_tab = QtWidgets.QWidget()
        live_layout = QtWidgets.QVBoxLayout(live_tab)
        live_layout.setContentsMargins(10, 10, 10, 10)
        live_layout.setSpacing(10)

        live_group = QtWidgets.QGroupBox("Select Live Point")
        live_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #5d4037;
            }
        """)
        live_grid = QtWidgets.QGridLayout(live_group)
        live_grid.setSpacing(6)

        self.weld_live_point_btn = QtWidgets.QPushButton("📍 Pick Weld Live Point")
        self.weld_live_point_btn.setFixedHeight(36)
        self.weld_live_point_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.weld_live_point_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        self.weld_live_point_btn.clicked.connect(self._start_weld_live_point_pick)
        live_grid.addWidget(self.weld_live_point_btn, 0, 0, 1, 2)

        self.weld_live_point_label = QtWidgets.QLabel("Weld live point: not selected")
        self.weld_live_point_label.setWordWrap(True)
        self.weld_live_point_label.setStyleSheet("color: #424242; font-size: 11px;")
        live_grid.addWidget(self.weld_live_point_label, 1, 0, 1, 2)

        live_hint = QtWidgets.QLabel(
            "Click a point on the weld edge to define where welding starts. Start Welding will follow the edge from that point."
        )
        live_hint.setWordWrap(True)
        live_hint.setStyleSheet("color: #757575; font-size: 11px; font-style: italic;")
        live_grid.addWidget(live_hint, 2, 0, 1, 2)

        live_layout.addWidget(live_group)
        live_layout.addStretch()
        self.weld_move_tabs.addTab(live_tab, "Select Live Point")

        move_tab = QtWidgets.QWidget()
        move_layout = QtWidgets.QVBoxLayout(move_tab)
        move_layout.setContentsMargins(10, 10, 10, 10)
        move_layout.setSpacing(10)

        move_group = QtWidgets.QGroupBox("Move Object to Position")
        move_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #5d4037;
            }
        """)
        move_grid = QtWidgets.QGridLayout(move_group)
        move_grid.setSpacing(6)

        move_grid.addWidget(QtWidgets.QLabel("Target X (cm):"), 0, 0)
        self.weld_move_x_sb = QtWidgets.QDoubleSpinBox()
        self.weld_move_x_sb.setRange(-9999.0, 9999.0)
        self.weld_move_x_sb.setValue(0.0)
        self.weld_move_x_sb.setSuffix(" cm")
        self.weld_move_x_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        move_grid.addWidget(self.weld_move_x_sb, 0, 1)

        move_grid.addWidget(QtWidgets.QLabel("Target Y (cm):"), 1, 0)
        self.weld_move_y_sb = QtWidgets.QDoubleSpinBox()
        self.weld_move_y_sb.setRange(-9999.0, 9999.0)
        self.weld_move_y_sb.setValue(0.0)
        self.weld_move_y_sb.setSuffix(" cm")
        self.weld_move_y_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        move_grid.addWidget(self.weld_move_y_sb, 1, 1)

        move_grid.addWidget(QtWidgets.QLabel("Target Z (cm):"), 2, 0)
        self.weld_move_z_sb = QtWidgets.QDoubleSpinBox()
        self.weld_move_z_sb.setRange(-9999.0, 9999.0)
        self.weld_move_z_sb.setValue(0.0)
        self.weld_move_z_sb.setSuffix(" cm")
        self.weld_move_z_sb.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px; padding: 2px 4px;")
        move_grid.addWidget(self.weld_move_z_sb, 2, 1)

        self.weld_move_apply_btn = QtWidgets.QPushButton("↔ Apply Object Move")
        self.weld_move_apply_btn.setFixedHeight(36)
        self.weld_move_apply_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.weld_move_apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #e65100;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #ef6c00; }
        """)
        self.weld_move_apply_btn.clicked.connect(self._apply_weld_path_move)
        move_grid.addWidget(self.weld_move_apply_btn, 3, 0, 1, 2)

        move_hint = QtWidgets.QLabel(
            "Sets the selected object so its bottom-face center lands at the entered world coordinates."
        )
        move_hint.setWordWrap(True)
        move_hint.setStyleSheet("color: #757575; font-size: 11px; font-style: italic;")
        move_grid.addWidget(move_hint, 4, 0, 1, 2)

        move_layout.addWidget(move_group)
        move_layout.addStretch()
        self.weld_move_tabs.addTab(move_tab, "Move Path")

        welding_layout.addWidget(self.weld_move_tabs)

        welding_layout.addStretch()
        self.stack.addWidget(self.welding_view)
        
        self.weld_edge_records = []  # Selected weld edges: each item stores link + endpoints + derived metadata
        self.welding_paths = []  # Generated weld path payloads
        self.is_welding_active = False
        self.weld_motion_state = "IDLE"
        self.weld_target_joint_values = {}
        self.weld_joint_chain = []
        self.weld_tcp_link = None
        self.weld_tool_offset = np.zeros(3, dtype=float)
        self.weld_live_trail_points = []
        self.weld_live_trail_actor_name = "weld_live_trail"
        self.weld_live_point_world = None
        self.weld_live_point_link = None
        self.weld_live_point_active = False
        self.weld_timer = QtCore.QTimer(self)
        self.weld_timer.timeout.connect(self._weld_tick)
        self.current_weld_path_idx = 0
        self.current_weld_point_idx = 0
        self.paint_nozzle_pick_data = None
        self.painting_active = False
        self.paint_timer = QtCore.QTimer(self)
        self.paint_timer.timeout.connect(self._safe_on_paint_tick)
        self.paint_motion_state = "IDLE"
        self.paint_path_points = []
        self.paint_current_point_idx = 0
        self.paint_target_joint_values = {}
        self.paint_joint_chain = []
        self.paint_tcp_link = None
        self.paint_nozzle_tcp_offset = None
        self.paint_area_points_world = []
        self.paint_area_point_inputs = []
        self.paint_area_joint_targets = []
        
        # 5. Painting View â€” with sub-tabs
        self.painting_view = QtWidgets.QWidget()
        painting_layout = QtWidgets.QVBoxLayout(self.painting_view)
        painting_layout.setContentsMargins(10, 10, 10, 10)
        painting_layout.setSpacing(10)

        painting_title = QtWidgets.QLabel("ðŸŽ¨ PAINTING MODE")
        painting_title.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #7b1fa2; margin-bottom: 5px;"
        )
        painting_title.setAlignment(QtCore.Qt.AlignCenter)
        painting_layout.addWidget(painting_title)

        self.painting_tabs = QtWidgets.QTabWidget()
        self.painting_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: #fafafa;
            }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 12px;
                color: #757575;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #fafafa;
                color: #7b1fa2;
                border-bottom: 2px solid #7b1fa2;
            }
            QTabBar::tab:hover {
                background: #ede7f6;
            }
        """)
        painting_layout.addWidget(self.painting_tabs)

        nozzle_tab = QtWidgets.QWidget()
        nozzle_layout = QtWidgets.QVBoxLayout(nozzle_tab)
        nozzle_layout.setContentsMargins(10, 10, 10, 10)
        nozzle_layout.setSpacing(12)

        nozzle_group = QtWidgets.QGroupBox("Nozzle Face Selection")
        nozzle_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ce93d8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #7b1fa2;
            }
        """)
        nozzle_group_layout = QtWidgets.QVBoxLayout(nozzle_group)
        nozzle_group_layout.setSpacing(8)

        nozzle_intro = QtWidgets.QLabel(
            "Pick the face of the paint nozzle in the 3D scene. This uses the same face-picking flow as alignment."
        )
        nozzle_intro.setWordWrap(True)
        nozzle_intro.setStyleSheet("font-size: 12px; color: #424242;")
        nozzle_group_layout.addWidget(nozzle_intro)

        self.paint_square_summary = QtWidgets.QLabel("Square size: —")
        self.paint_square_summary.setStyleSheet("font-size: 12px; color: #424242; font-weight: bold;")
        nozzle_group_layout.addWidget(self.paint_square_summary)

        self.paint_square_detail = QtWidgets.QLabel("Center: —")
        self.paint_square_detail.setWordWrap(True)
        self.paint_square_detail.setStyleSheet("font-size: 11px; color: #757575;")
        nozzle_group_layout.addWidget(self.paint_square_detail)

        self.paint_nozzle_summary = QtWidgets.QLabel("Nozzle face: —")
        self.paint_nozzle_summary.setStyleSheet("font-size: 12px; color: #424242; font-weight: bold;")
        nozzle_group_layout.addWidget(self.paint_nozzle_summary)

        self.paint_nozzle_detail = QtWidgets.QLabel("Center: —")
        self.paint_nozzle_detail.setWordWrap(True)
        self.paint_nozzle_detail.setStyleSheet("font-size: 11px; color: #757575;")
        nozzle_group_layout.addWidget(self.paint_nozzle_detail)

        self.paint_pick_nozzle_btn = QtWidgets.QPushButton("🎯 Select Nozzle Face")
        self.paint_pick_nozzle_btn.setFixedHeight(46)
        self.paint_pick_nozzle_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.paint_pick_nozzle_btn.setStyleSheet("""
            QPushButton {
                background-color: #7b1fa2;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #6a1b9a; }
            QPushButton:pressed { background-color: #4a148c; }
        """)
        self.paint_pick_nozzle_btn.clicked.connect(self.pick_paint_nozzle_face)
        nozzle_group_layout.addWidget(self.paint_pick_nozzle_btn)

        self.paint_clear_nozzle_btn = QtWidgets.QPushButton("Clear Nozzle Face")
        self.paint_clear_nozzle_btn.setFixedHeight(38)
        self.paint_clear_nozzle_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.paint_clear_nozzle_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #7b1fa2;
                border: 1px solid #ce93d8;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #f3e5f5; }
        """)
        self.paint_clear_nozzle_btn.clicked.connect(self.clear_paint_nozzle_face)
        nozzle_group_layout.addWidget(self.paint_clear_nozzle_btn)

        nozzle_hint = QtWidgets.QLabel(
            "Use the selected nozzle face as the painting reference point and orientation."
        )
        nozzle_hint.setWordWrap(True)
        nozzle_hint.setStyleSheet("font-size: 11px; color: #757575; font-style: italic;")
        nozzle_group_layout.addWidget(nozzle_hint)

        self.paint_make_path_btn = QtWidgets.QPushButton("🧩 Make Path")
        self.paint_make_path_btn.setFixedHeight(44)
        self.paint_make_path_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.paint_make_path_btn.setStyleSheet("""
            QPushButton {
                background-color: #5e35b1;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #4527a0; }
            QPushButton:pressed { background-color: #311b92; }
        """)
        self.paint_make_path_btn.clicked.connect(self.make_paint_path)
        nozzle_group_layout.addWidget(self.paint_make_path_btn)

        paint_control_row = QtWidgets.QHBoxLayout()
        paint_control_row.setSpacing(8)

        self.paint_start_btn = QtWidgets.QPushButton("Start")
        self.paint_start_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.paint_start_btn.setFixedHeight(40)
        self.paint_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #1b5e20; }
            QPushButton:pressed { background-color: #0f3d14; }
        """)
        self.paint_start_btn.clicked.connect(self.start_painting)
        paint_control_row.addWidget(self.paint_start_btn)

        self.paint_stop_btn = QtWidgets.QPushButton("Stop")
        self.paint_stop_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.paint_stop_btn.setFixedHeight(40)
        self.paint_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #8e0000; }
            QPushButton:pressed { background-color: #5f0000; }
        """)
        self.paint_stop_btn.clicked.connect(self.stop_painting)
        paint_control_row.addWidget(self.paint_stop_btn)

        nozzle_group_layout.addLayout(paint_control_row)

        nozzle_layout.addWidget(nozzle_group)
        nozzle_layout.addStretch()
        self.painting_tabs.addTab(nozzle_tab, "🎯 Select Nozzle")

        area_tab = QtWidgets.QWidget()
        area_layout = QtWidgets.QVBoxLayout(area_tab)
        area_layout.setContentsMargins(10, 10, 10, 10)
        area_layout.setSpacing(12)

        area_group = QtWidgets.QGroupBox("Manual Area")
        area_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ce93d8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #7b1fa2;
            }
        """)
        area_group_layout = QtWidgets.QVBoxLayout(area_group)
        area_group_layout.setSpacing(8)

        area_intro = QtWidgets.QLabel(
            "Enter 4 corner points in centimeters. The points should be ordered around the area boundary."
        )
        area_intro.setWordWrap(True)
        area_intro.setStyleSheet("font-size: 12px; color: #424242;")
        area_group_layout.addWidget(area_intro)

        self.paint_area_summary = QtWidgets.QLabel("Area: —")
        self.paint_area_summary.setStyleSheet("font-size: 12px; color: #424242; font-weight: bold;")
        area_group_layout.addWidget(self.paint_area_summary)

        self.paint_area_detail = QtWidgets.QLabel("Points: —")
        self.paint_area_detail.setWordWrap(True)
        self.paint_area_detail.setStyleSheet("font-size: 11px; color: #757575;")
        area_group_layout.addWidget(self.paint_area_detail)

        area_grid = QtWidgets.QGridLayout()
        area_grid.setHorizontalSpacing(6)
        area_grid.setVerticalSpacing(6)
        area_grid.addWidget(QtWidgets.QLabel("Point"), 0, 0)
        area_grid.addWidget(QtWidgets.QLabel("X"), 0, 1)
        area_grid.addWidget(QtWidgets.QLabel("Y"), 0, 2)
        area_grid.addWidget(QtWidgets.QLabel("Z"), 0, 3)

        self.paint_area_point_inputs = []
        for idx in range(4):
            row = idx + 1
            label = QtWidgets.QLabel(f"P{idx + 1}")
            label.setStyleSheet("font-weight: bold;")
            area_grid.addWidget(label, row, 0)

            x_sb = self.create_coord_sb("#7b1fa2", save_on_change=False)
            y_sb = self.create_coord_sb("#7b1fa2", save_on_change=False)
            z_sb = self.create_coord_sb("#7b1fa2", save_on_change=False)
            x_sb.setValue(0.0)
            y_sb.setValue(0.0)
            z_sb.setValue(0.0)
            area_grid.addWidget(x_sb, row, 1)
            area_grid.addWidget(y_sb, row, 2)
            area_grid.addWidget(z_sb, row, 3)
            self.paint_area_point_inputs.append((x_sb, y_sb, z_sb))

        area_group_layout.addLayout(area_grid)

        self.paint_make_area_btn = QtWidgets.QPushButton("🧩 Make Area")
        self.paint_make_area_btn.setFixedHeight(44)
        self.paint_make_area_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.paint_make_area_btn.setStyleSheet("""
            QPushButton {
                background-color: #7b1fa2;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #6a1b9a; }
            QPushButton:pressed { background-color: #4a148c; }
        """)
        self.paint_make_area_btn.clicked.connect(self.make_paint_area)
        area_group_layout.addWidget(self.paint_make_area_btn)

        area_hint = QtWidgets.QLabel(
            "This draws the area in the 3D view and creates the zigzag path used by Start."
        )
        area_hint.setWordWrap(True)
        area_hint.setStyleSheet("font-size: 11px; color: #757575; font-style: italic;")
        area_group_layout.addWidget(area_hint)

        area_layout.addWidget(area_group)
        area_layout.addStretch()
        self.painting_tabs.addTab(area_tab, "🧩 Make Area")

        painting_layout.addStretch()

        self.stack.addWidget(self.painting_view)
        
        # Initial State
        self.switch_view(0)


    def create_coord_sb(self, color, save_on_change=True):
        sb = TypeOnlyDoubleSpinBox()
        sb.setRange(-9999, 9999)
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
        if save_on_change:
            sb.valueChanged.connect(self.main_window.save_sim_object_coords)
        return sb

    def update_object_position(self):
        """Moves the selected simulation object to P1 coordinates and compiles the path for Pick and Place."""
        # Auto-switch to objects tab so user can see coordinates
        self.switch_view(2)
        
        current_item = self.objects_list.currentItem()
        if not current_item:
            self.main_window.log("âš ï¸ Select an object from the list first.")
            self.main_window.show_toast("No object selected", "warning")
            return
            
        name = current_item.text()
        if name in self.main_window.robot.links:
            link = self.main_window.robot.links[name]
            
            # --- COMPLIANCE CHECK: Base, Aligned, or Jointed cannot be moved ---
            is_aligned = False
            if hasattr(self.main_window, 'alignment_cache'):
                for (p, c), pt in self.main_window.alignment_cache.items():
                    if c == name:
                        is_aligned = True; break
            
            if link.is_base:
                reason = "Base"
            elif link.parent_joint:
                reason = "Jointed"
            elif is_aligned:
                reason = "Aligned"
            else:
                reason = None
                
            if reason:
                self.main_window.log(f"âš ï¸ Locked: '{name}' is {reason} and cannot be moved.")
                self.main_window.show_toast(f"{reason} is fixed", "warning")
                return

            ratio = self.main_window.canvas.grid_units_per_cm
            
            # Target P1 Position (scaled to graph units)
            px = self.pick_x.value() * ratio
            py = self.pick_y.value() * ratio
            pz = self.pick_z.value() * ratio
            
            # --- COMPILE PROCESS FOR P1 AND P2 ---
            tcp_link = self._get_tcp_link()
            if tcp_link:
                if not self._check_target_feasibility("P1", tcp_link, z_offset_cm=0.0):
                    msg = "These coordinates are not feasible to achieve. Try other coordinates."
                    self.main_window.log(f"âš ï¸ P1: {msg}")
                    self._handle_unreachable_target("P1", msg)
                    return

                self._auto_prepare_gripper_for_pick_place(tcp_link=tcp_link, quiet=True)
                self.main_window.log("-----------------------------------------")
                self.main_window.log("ðŸ› ï¸ COMPILING PROCESS: P1 -> P2 Path Planning")
                self.main_window.log("-----------------------------------------")
                
                start_vals = {n: j.current_value for n, j in self.main_window.robot.joints.items()}
                _, tool_local, gap = self.main_window.get_link_tool_point(tcp_link)
                tol = 0.5 * ratio  # 0.5 cm in canvas units
                
                # Fetch object height offset for realistic targets
                _, z_offset, _ = self._get_object_grip_width()
                
                # 1. Compile P1
                p1_target = np.array([px, py, pz + z_offset])
                reached_p1 = self.main_window.robot.inverse_kinematics(
                    p1_target, tcp_link, max_iters=300, tolerance=tol, tool_offset=tool_local)
                if reached_p1:
                    self.main_window.log("ðŸ§  Path to reach P1 (Pick Position):")
                    chain_p1 = self.main_window.robot.get_kinematic_chain(tcp_link)
                    for i, j in enumerate(chain_p1):
                        self.main_window.log(f"   Step [{i+1}] {j.name} â†’ {j.current_value:.2f}Â°")
                else:
                    msg = "These coordinates are not feasible to achieve. Try other coordinates."
                    self.main_window.log(f"âš ï¸ P1: {msg}")
                    self._handle_unreachable_target("P1", msg)
                    for n, val in start_vals.items():
                        self.main_window.robot.joints[n].current_value = val
                    self.main_window.robot.update_kinematics()
                    return
                
                # Restore to calculate P2 independently
                for n, val in start_vals.items():
                    self.main_window.robot.joints[n].current_value = val
                self.main_window.robot.update_kinematics()
                
                # 2. Compile P2
                p2_target = np.array([
                    self.place_x.value() * ratio, 
                    self.place_y.value() * ratio, 
                    self.place_z.value() * ratio + z_offset
                ])
                reached_p2 = self.main_window.robot.inverse_kinematics(
                    p2_target, tcp_link, max_iters=300, tolerance=tol, tool_offset=tool_local)
                if reached_p2:
                    self.main_window.log("ðŸ§  Path to reach P2 (Place Position):")
                    chain_p2 = self.main_window.robot.get_kinematic_chain(tcp_link)
                    for i, j in enumerate(chain_p2):
                        self.main_window.log(f"   Step [{i+1}] {j.name} â†’ {j.current_value:.2f}Â°")
                else:
                    msg = "These coordinates are not feasible to achieve. Try other coordinates."
                    self.main_window.log(f"âš ï¸ P2: {msg}")
                    self._handle_unreachable_target("P2", msg)
                    for n, val in start_vals.items():
                        self.main_window.robot.joints[n].current_value = val
                    self.main_window.robot.update_kinematics()
                    return
                
                self.main_window.log("-----------------------------------------")
                
                # Restore state again before moving object
                for n, val in start_vals.items():
                    self.main_window.robot.joints[n].current_value = val
                self.main_window.robot.update_kinematics()
            
            # Apply transformation
            # We want the BOTTOM of the mesh to sit at (px, py, pz).
            # If the mesh's local min-Z is 'min_z', then the origin must be at 'pz - min_z'.
            t_new = np.identity(4)
            t_new[:3, :3] = link.t_offset[:3, :3] # keep rotation
            
            origin_z = pz
            if link.mesh:
                local_min_z = link.mesh.bounds[0][2]
                origin_z = pz - local_min_z
            
            t_new[:3, 3] = [px, py, origin_z]
            link.t_offset = t_new
            
            # Update visuals
            self.main_window.robot.update_kinematics()
            self.main_window.canvas.update_transforms(self.main_window.robot)
            self.main_window.log(f"âœ… Object '{name}' moved to P1: ({self.pick_x.value()}, {self.pick_y.value()}, {self.pick_z.value()}) cm")
            self.main_window.show_toast(f"Moved {name} to P1 & Compiled", "success")
            # Refresh info
            self.refresh_object_info(name)

    def capture_object_to_p1(self):
        """Captures the selected object's BOTTOM-CENTER world position into P1 spinboxes.
        
        P1 represents the bottom-center of the object (the coordinate the robot moves to
        before gripping). This accounts for the mesh's local min-Z offset so the pick
        coordinate always refers to the true base of the object in world space.
        """
        current_item = self.objects_list.currentItem()
        if not current_item:
            return
            
        name = current_item.text()
        if name not in self.main_window.robot.links:
            return

        link = self.main_window.robot.links[name]
        ratio = self.main_window.canvas.grid_units_per_cm

        # Compute world-space bottom-center
        # The mesh origin may be offset from the actual bottom, so we convert the
        # local bottom-center of the mesh bounding box to world space.
        if link.mesh:
            b = link.mesh.bounds
            local_bottom_center = np.array([
                (b[0][0] + b[1][0]) / 2.0,  # center X
                (b[0][1] + b[1][1]) / 2.0,  # center Y
                b[0][2]                       # bottom Z (local min)
            ])
            world_bottom = (link.t_world @ np.append(local_bottom_center, 1.0))[:3]
        else:
            # Fall back to transform origin if no mesh
            world_bottom = link.t_world[:3, 3]

        pos_cm = world_bottom / ratio

        self.pick_x.setValue(pos_cm[0])
        self.pick_y.setValue(pos_cm[1])
        self.pick_z.setValue(pos_cm[2])

        self.main_window.log(
            f"ðŸŽ¯ P1 set to bottom-center of '{name}': "
            f"({pos_cm[0]:.1f}, {pos_cm[1]:.1f}, {pos_cm[2]:.1f}) cm"
        )
        self.main_window.save_sim_object_coords()

    def refresh_object_info(self, name):
        """Updates the info labels and automated DIM fields for the given object."""
        if name not in self.main_window.robot.links:
            return
            
        link = self.main_window.robot.links[name]
        ratio = self.main_window.canvas.grid_units_per_cm
        
        # Dimensions
        if link.mesh:
            b = link.mesh.bounds
            size = (b[1] - b[0]) / ratio
            self.dim_label.setText(f"Dimensions: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} cm")
            
            # --- AUTO-POPULATE INDUSTRIAL DIM FIELDS ---
            self.obj_width.setValue(size[0])
            self.obj_depth.setValue(size[1])
            self.obj_height.setValue(size[2])
        else:
            self.dim_label.setText("Dimensions: N/A")
            
        # Position
        pos = link.t_world[:3, 3] / ratio
        self.pos_label.setText(f"Current Pos: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) cm")

    def _auto_prepare_gripper_for_pick_place(self, tcp_link=None, quiet=False):
        gripper_tab = getattr(self.main_window, 'gripper_tab', None)
        if gripper_tab is None or not hasattr(gripper_tab, 'ensure_auto_gripping_ready'):
            return {"configured": False, "reason": "gripper_tab_unavailable"}

        preferred_joint_name = None
        if tcp_link is not None:
            for joint in tcp_link.child_joints:
                if getattr(joint, 'is_gripper', False):
                    preferred_joint_name = joint.name
                    break

        plan = gripper_tab.ensure_auto_gripping_ready(
            preferred_joint_name=preferred_joint_name,
            quiet=quiet,
            force=False
        )
        if isinstance(plan, dict):
            return plan
        return {"configured": False, "reason": "invalid_plan"}

    def _build_motion_target(self, target_name, tcp_link, z_offset_cm=0.0):
        """Builds the IK target for P1, P2, or HOME without changing robot state."""
        ratio = self.main_window.canvas.grid_units_per_cm

        if target_name == "P1":
            target_cm = np.array([self.pick_x.value(), self.pick_y.value(), self.pick_z.value()], dtype=float)
        elif target_name == "HOME":
            target_cm = np.array([self.home_x.value(), self.home_y.value(), self.home_z.value()], dtype=float)
        else:
            target_cm = np.array([self.place_x.value(), self.place_y.value(), self.place_z.value()], dtype=float)

        target_cm[2] += z_offset_cm
        target_world = target_cm * ratio

        world_tcp, tool_local, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        is_home_target = target_name == "HOME"
        final_z_offset = 0.0

        if not is_home_target:
            _, base_z_offset, _ = self._get_object_grip_width()
            final_z_offset = base_z_offset
            # NOTE:
            # P1/P2 are object bottom-center coordinates. We aim the TCP at a stable grasp point
            # on the object body (usually near the object's center height), so the gripper can
            # clamp on any side face. Do not treat finger_depth as a world-Z offset; finger_depth
            # is measured along the gripper's approach axis, not world Z.

        target_world[2] += final_z_offset

        return {
            "ratio": ratio,
            "target_cm": target_cm,
            "target_world": target_world,
            "tool_local": tool_local,
            "geo_data": geo_data,
            "is_home_target": is_home_target,
            "final_z_offset": final_z_offset,
        }

    def _check_target_feasibility(self, target_name, tcp_link, z_offset_cm=0.0):
        """Checks whether the robot can reach a target before motion starts."""
        probe = self._build_motion_target(target_name, tcp_link, z_offset_cm=z_offset_cm)
        ratio = probe["ratio"]
        target_world = probe["target_world"]
        tool_local = probe["tool_local"]

        start_vals = {n: j.current_value for n, j in self.main_window.robot.joints.items()}
        try:
            reached = self.main_window.robot.inverse_kinematics(
                target_world,
                tcp_link,
                max_iters=300,
                tolerance=0.5 * ratio,
                tool_offset=tool_local
            )
            return bool(reached)
        finally:
            for n, val in start_vals.items():
                if n in self.main_window.robot.joints:
                    self.main_window.robot.joints[n].current_value = val
            self.main_window.robot.update_kinematics()

    def _handle_unreachable_target(self, target_name, msg):
        """Show a non-blocking warning when a planning target cannot be solved."""
        self.main_window.log(f"âš ï¸ {target_name}: {msg}")
        self.main_window.show_toast(f"{target_name} not reachable", "warning")

    def _measure_gripper_gap_range(self):
        """Measure the gripper's usable gap range in world units and cm."""
        if not hasattr(self.main_window, "_control_gripper_fingers"):
            return None

        try:
            self.main_window._control_gripper_fingers(
                close=False,
                target_gap_world=0.0,
                apply=False,
            )
        except Exception:
            return None

        gap_limits = getattr(self.main_window, "_last_gripper_gap_limits", {}) or {}
        global_limits = gap_limits.get("_global")
        if not global_limits and gap_limits:
            all_limits = [
                value for value in gap_limits.values()
                if isinstance(value, tuple) and len(value) == 2
            ]
            if all_limits:
                global_limits = (
                    float(min(limit[0] for limit in all_limits)),
                    float(max(limit[1] for limit in all_limits)),
                )

        if not global_limits:
            return None

        ratio = self.main_window.canvas.grid_units_per_cm
        min_gap_world, max_gap_world = float(global_limits[0]), float(global_limits[1])
        return {
            "min_world": min_gap_world,
            "max_world": max_gap_world,
            "min_cm": min_gap_world / ratio,
            "max_cm": max_gap_world / ratio,
        }

    def _make_world_parallel_rotation(self, rotation):
        """Flatten a rotation so the object stays parallel to the world floor."""
        rot = np.array(rotation, dtype=float)
        if rot.shape != (3, 3):
            return np.eye(3)

        # Keep yaw if possible, but remove roll/pitch so the bottom face stays level.
        x_axis = np.array(rot[:, 0], dtype=float)
        x_axis[2] = 0.0
        if np.linalg.norm(x_axis) < 1e-9:
            x_axis = np.array(rot[:, 1], dtype=float)
            x_axis[2] = 0.0
        if np.linalg.norm(x_axis) < 1e-9:
            return np.eye(3)

        x_axis /= np.linalg.norm(x_axis)
        z_axis = np.array([0.0, 0.0, 1.0], dtype=float)
        y_axis = np.cross(z_axis, x_axis)
        if np.linalg.norm(y_axis) < 1e-9:
            return np.eye(3)
        y_axis /= np.linalg.norm(y_axis)
        x_axis = np.cross(y_axis, z_axis)
        x_axis /= np.linalg.norm(x_axis)

        flat = np.eye(3)
        flat[:3, 0] = x_axis
        flat[:3, 1] = y_axis
        flat[:3, 2] = z_axis
        return flat

    def _build_pick_place_plan(self, tcp_link):
        """Builds a realistic pick-and-place grasp plan from the gripper and object geometry."""
        ratio = self.main_window.canvas.grid_units_per_cm
        current_item = self.objects_list.currentItem()
        if not current_item:
            return {"feasible": False, "reason": "No object selected"}

        obj_name = current_item.text()
        if obj_name not in self.main_window.robot.links:
            return {"feasible": False, "reason": "Selected object missing"}

        grip_width_world, z_offset_world, obj_link = self._get_object_grip_width()
        _, _, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)

        if obj_link is None:
            return {"feasible": False, "reason": "Object profile unavailable"}

        mesh_size = np.abs(obj_link.mesh.bounds[1] - obj_link.mesh.bounds[0]) if obj_link.mesh else np.zeros(3)
        object_height_cm = self.obj_height.value() if self.obj_height.value() > 0 else (mesh_size[2] / ratio)
        object_thickness_cm = grip_width_world / ratio if grip_width_world > 0 else max(
            self.obj_width.value(),
            self.obj_depth.value(),
            mesh_size[0] / ratio if mesh_size.size else 0.0,
            mesh_size[1] / ratio if mesh_size.size else 0.0,
        )

        finger_gap_world = None
        finger_depth_world = None
        using_selected_faces = False
        if isinstance(geo_data, dict):
            finger_gap_world = geo_data.get("real_gap")
            finger_depth_world = geo_data.get("finger_depth")
            using_selected_faces = bool(geo_data.get("using_selected_gripping_surfaces"))

        finger_gap_cm = finger_gap_world / ratio if finger_gap_world is not None else None
        finger_depth_cm = finger_depth_world / ratio if finger_depth_world is not None else None
        gap_range = self._measure_gripper_gap_range()
        min_open_gap_cm = gap_range["min_cm"] if gap_range else None
        max_open_gap_cm = gap_range["max_cm"] if gap_range else None

        # Industrial-style safety clearances:
        # - extra opening before approach
        # - slightly larger lift to clear the table and keep the part centered
        clearance_cm = max(0.5, min(2.0, max(0.5, object_height_cm * 0.12)))
        squeeze_cm = 0.0 if using_selected_faces else max(0.05, min(0.25, object_thickness_cm * 0.03))
        required_open_cm = object_thickness_cm + clearance_cm
        close_gap_cm = max(0.0, object_thickness_cm - squeeze_cm)
        if using_selected_faces:
            close_gap_cm = object_thickness_cm

        approach_z_cm = max(5.0, object_height_cm * 0.35)
        if finger_depth_cm is not None:
            approach_z_cm = max(approach_z_cm, finger_depth_cm * 0.25)
        lift_z_cm = max(5.0, object_height_cm * 0.35, clearance_cm)

        # Prefer the longest safe overhead route so the motion stays clear of the object.
        longest_safe_z_cm = max(
            approach_z_cm,
            lift_z_cm,
            object_height_cm * 0.5 + 8.0,
            (finger_depth_cm * 0.5) if finger_depth_cm is not None else 0.0,
        )
        approach_z_cm = longest_safe_z_cm
        lift_z_cm = longest_safe_z_cm
        transit_z_cm = longest_safe_z_cm
        open_gap_world = required_open_cm * ratio
        close_gap_world = close_gap_cm * ratio
        release_open_gap_world = (
            max_open_gap_cm * ratio if max_open_gap_cm is not None else open_gap_world
        )

        warnings = []
        fit_status = "OK"
        if max_open_gap_cm is not None and required_open_cm > max_open_gap_cm + 0.01:
            fit_status = "Best effort"
            warnings.append(
                f"Object needs about {required_open_cm:.2f} cm opening, but the gripper only opens to "
                f"{max_open_gap_cm:.2f} cm. Continuing with the largest safe opening."
            )
        if min_open_gap_cm is not None and close_gap_cm < min_open_gap_cm - 0.01:
            fit_status = "Best effort"
            warnings.append(
                f"Object is thinner than the measured minimum closing gap of {min_open_gap_cm:.2f} cm."
            )

        return {
            "feasible": True,
            "reason": None,
            "object_name": obj_name,
            "object_thickness_cm": object_thickness_cm,
            "object_height_cm": object_height_cm,
            "finger_gap_cm": finger_gap_cm,
            "finger_depth_cm": finger_depth_cm,
            "clearance_cm": clearance_cm,
            "squeeze_cm": squeeze_cm,
            "required_open_cm": required_open_cm,
            "close_gap_cm": close_gap_cm,
            "approach_z_cm": approach_z_cm,
            "lift_z_cm": lift_z_cm,
            "transit_z_cm": transit_z_cm,
            "route_mode": "longest_safe_overhead",
            "parallel_to_plane": True,
            "open_gap_world": open_gap_world,
            "close_gap_world": close_gap_world,
            "release_open_gap_world": release_open_gap_world,
            "min_open_gap_cm": min_open_gap_cm,
            "max_open_gap_cm": max_open_gap_cm,
            "using_selected_faces": using_selected_faces,
            "grip_width_world": grip_width_world,
            "z_offset_world": z_offset_world,
            "fit_status": fit_status,
            "warnings": warnings,
        }

    def toggle_welding_edge_picking(self, checked):
        """Toggle interactive edge picking for weld joint capture."""
        if checked:
            if not self.main_window.robot.links:
                self.main_window.log("⚠️ Load or import a component before selecting welding edges.")
                self.main_window.show_toast("Import a model first", "warning")
                self.weld_pick_btn.blockSignals(True)
                self.weld_pick_btn.setChecked(False)
                self.weld_pick_btn.blockSignals(False)
                return

            self.main_window.log("🎯 Edge Picking Active: click a weld edge on the 3D model.")
            self.main_window.show_toast("Pick weld edges in 3D", "info")
            self.main_window.canvas.start_edge_picking(self._on_weld_edge_picked, color="#e65100")
        else:
            self.main_window.canvas.deselect_all()

    def _on_weld_edge_picked(self, link_name, p1_w, p2_w):
        """Callback from the canvas when the user picks one edge."""
        record = {
            "link": link_name,
            "edge_points": [np.array(p1_w, dtype=float), np.array(p2_w, dtype=float)],
        }
        if self._add_weld_edge_record(record):
            self.main_window.log(f"✅ Weld edge added from '{link_name}'.")
        else:
            self.main_window.log("⚠️ Duplicate or invalid weld edge ignored.")

        self._refresh_weld_edge_ui()

        # Re-arm edge picking if the toggle remains active.
        if self.weld_pick_btn.isChecked():
            QtCore.QTimer.singleShot(0, lambda: self.main_window.canvas.start_edge_picking(self._on_weld_edge_picked, color="#e65100"))

    def _start_weld_live_point_pick(self):
        """Activate point picking so the user can define the weld start reference."""
        self.main_window.log("📍 Click a point on the weld edge to set the live weld point.")
        self.main_window.show_toast("Pick weld live point", "info")
        self.weld_live_point_active = True
        self.main_window.canvas.start_point_picking(self._on_weld_live_point_picked)

    def _on_weld_live_point_picked(self, world_pt):
        """Store the picked point as the weld start reference."""
        picked = np.array(world_pt, dtype=float)
        edge_idx, projected = self._find_nearest_selected_weld_edge(picked)
        self.weld_live_point_world = projected if projected is not None else picked
        self.weld_live_point_link = None
        self.weld_live_point_edge_index = edge_idx
        self.weld_live_point_active = False

        if hasattr(self, "weld_live_point_label"):
            ratio = self.main_window.canvas.grid_units_per_cm
            pt_cm = self.weld_live_point_world / ratio
            self.weld_live_point_label.setText(
                f"Weld live point: ({pt_cm[0]:.2f}, {pt_cm[1]:.2f}, {pt_cm[2]:.2f}) cm"
            )

        if hasattr(self.main_window.canvas, "set_live_point_marker"):
            self.main_window.canvas.set_live_point_marker(
                self.weld_live_point_world,
                color="#ff9800",
                name="weld_selected_live_point",
            )

        self.main_window.log(
            f"📍 Weld live point set at ({self.weld_live_point_world[0]:.2f}, "
            f"{self.weld_live_point_world[1]:.2f}, {self.weld_live_point_world[2]:.2f})"
        )
        self.main_window.show_toast("Weld live point saved", "success")

    def _add_weld_edge_record(self, record):
        """Store a new weld edge unless it already exists."""
        p1, p2 = record["edge_points"]
        for existing in self.weld_edge_records:
            e1, e2 = existing["edge_points"]
            if (
                np.linalg.norm(p1 - e1) < 1e-3 and np.linalg.norm(p2 - e2) < 1e-3
            ) or (
                np.linalg.norm(p1 - e2) < 1e-3 and np.linalg.norm(p2 - e1) < 1e-3
            ):
                return False
        self.weld_edge_records.append(record)
        return True

    def _refresh_weld_edge_ui(self):
        """Update the edge list and summary labels."""
        self.weld_edges_list.clear()
        for idx, edge in enumerate(self.weld_edge_records, start=1):
            p1, p2 = edge["edge_points"]
            self.weld_edges_list.addItem(
                f"{idx}. {edge['link']} | ({p1[0]:.1f}, {p1[1]:.1f}, {p1[2]:.1f}) -> ({p2[0]:.1f}, {p2[1]:.1f}, {p2[2]:.1f})"
            )
        if hasattr(self, "weld_summary_label"):
            self.weld_summary_label.setText(f"Selected edges: {len(self.weld_edge_records)}")

    def clear_welding_edges(self):
        """Clear welding edge selections and generated path data."""
        self.weld_edge_records = []
        self.welding_paths = []
        self.weld_json_view.clear()
        self.current_weld_path_idx = 0
        self.current_weld_point_idx = 0
        self.is_welding_active = False
        self.weld_state = "IDLE"
        self.weld_timer.stop()
        self._refresh_weld_edge_ui()
        if hasattr(self, "weld_pick_btn"):
            self.weld_pick_btn.blockSignals(True)
            self.weld_pick_btn.setChecked(False)
            self.weld_pick_btn.blockSignals(False)
        if hasattr(self, "start_weld_btn"):
            self.start_weld_btn.blockSignals(True)
            self.start_weld_btn.setChecked(False)
            self.start_weld_btn.setText("▶ Start Welding")
            self.start_weld_btn.blockSignals(False)
        self.main_window.canvas.deselect_all()
        self.main_window.log("🗑️ Welding edges cleared.")

    def start_welding_sequence(self):
        """Generate a structured weld path JSON and start welding playback."""
        if self.is_welding_active:
            self.stop_welding()
            return

        if not self.weld_edge_records:
            self.main_window.log("⚠️ No welding edges selected.")
            self.main_window.show_toast("Select welding edges first", "warning")
            return

        payload = self._build_welding_payload()
        self.welding_paths = payload.get("weld_paths", [])
        pretty = json.dumps(payload, indent=2)
        self.weld_json_view.setPlainText(pretty)
        self.main_window.log(
            f"🧾 Generated welding JSON for {len(self.weld_edge_records)} edge(s), "
            f"{len(self.welding_paths)} path block(s)."
        )
        if self.weld_live_point_world is not None:
            self.main_window.log("📍 Welding will start from the selected live point reference.")
        self.main_window.show_toast("Weld JSON generated", "success")

        self.is_welding_active = True
        self.weld_state = "RUNNING"
        self.weld_motion_state = "SOLVE_WAYPOINT"
        self.current_weld_path_idx = 0
        self.current_weld_point_idx = 0
        self.weld_target_joint_values = {}
        self.weld_joint_chain = []
        self.weld_tcp_link = self._get_tcp_link()
        self.weld_tool_offset = np.zeros(3, dtype=float)
        self.weld_live_trail_points = []
        self.weld_live_point_edge_index = None
        self._clear_weld_live_trail()
        self.start_weld_btn.setText("⏹ Stop Welding")
        self.start_weld_btn.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #b71c1c; }
            QPushButton:pressed { background-color: #8e0000; }
        """)
        if not self.weld_timer.isActive():
            self.weld_timer.start(60)
        self.main_window.log("🔥 Welding started.")
        self.main_window.show_toast("Welding started", "success")

    def stop_welding(self):
        """Stop the welding timer and reset the state."""
        self.is_welding_active = False
        self.weld_state = "IDLE"
        self.weld_motion_state = "IDLE"
        self.weld_target_joint_values = {}
        self.weld_joint_chain = []
        self.weld_tcp_link = None
        self.weld_live_trail_points = []
        self.weld_live_point_edge_index = None
        self._clear_weld_live_trail()
        if self.weld_timer.isActive():
            self.weld_timer.stop()
        if hasattr(self, "start_weld_btn"):
            self.start_weld_btn.setText("▶ Start Welding")
            self.start_weld_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e65100;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover { background-color: #ef6c00; }
                QPushButton:pressed { background-color: #d84315; }
            """)

    def _weld_tick(self):
        """Advance through the generated weld paths one waypoint at a time."""
        if not self.is_welding_active:
            return

        if not self.welding_paths:
            self.main_window.log("⚠️ Welding stopped: no generated paths available.")
            self.stop_welding()
            return

        if self.current_weld_path_idx >= len(self.welding_paths):
            self.main_window.log("✅ Welding complete.")
            self.main_window.show_toast("Welding complete", "success")
            self.stop_welding()
            return

        tcp_link = self.weld_tcp_link or self._get_tcp_link()
        if tcp_link is None:
            self.main_window.log("⚠️ Welding stopped: no TCP link available.")
            self.stop_welding()
            return

        path = self.welding_paths[self.current_weld_path_idx]
        waypoints = path.get("waypoints", [])
        if self.current_weld_point_idx >= len(waypoints):
            self.current_weld_path_idx += 1
            self.current_weld_point_idx = 0
            self.weld_motion_state = "SOLVE_WAYPOINT"
            self.weld_target_joint_values = {}
            return

        waypoint = waypoints[self.current_weld_point_idx]
        phase = waypoint.get("phase", "weld")
        target_mm = np.array(waypoint.get("position_world_mm", [0.0, 0.0, 0.0]), dtype=float)
        height_mm = float(waypoint.get("height_from_start_mm", 0.0))
        ratio = self.main_window.canvas.grid_units_per_cm
        target_world = target_mm * (ratio / 10.0)

        if self.weld_motion_state == "SOLVE_WAYPOINT" or not self.weld_target_joint_values:
            tool_world, tool_local, _ = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
            self.weld_tool_offset = np.array(tool_local, dtype=float)

            start_vals = {n: j.current_value for n, j in self.main_window.robot.joints.items()}
            tolerance_world = 0.5 * ratio
            reached = self.main_window.robot.inverse_kinematics(
                target_world,
                tcp_link,
                max_iters=300,
                tolerance=tolerance_world,
                tool_offset=self.weld_tool_offset,
            )
            self.weld_target_joint_values = {
                n: j.current_value for n, j in self.main_window.robot.joints.items()
            }
            self.weld_joint_chain = self.main_window.robot.get_kinematic_chain(tcp_link)

            for n, val in start_vals.items():
                self.main_window.robot.joints[n].current_value = val
            self.main_window.robot.update_kinematics()

            self.weld_motion_state = "MOVE_WAYPOINT"
            self.main_window.log(
                f"🔥 {path.get('joint_classification', 'weld').upper()} | "
                f"path {self.current_weld_path_idx + 1}/{len(self.welding_paths)} "
                f"waypoint {self.current_weld_point_idx + 1}/{len(waypoints)} "
                f"phase={phase} target=({target_mm[0]:.1f}, {target_mm[1]:.1f}, {target_mm[2]:.1f}) mm "
                f"height={height_mm:+.1f} mm "
                f"reached={reached}"
            )
            if not reached:
                self.main_window.log("⚠️ Welding waypoint is only partially reachable; continuing best effort.")
            self._set_weld_live_point(target_world)
            return

        if self.weld_motion_state == "MOVE_WAYPOINT":
            if self._move_weld_smoothly():
                self._record_weld_live_trail(tcp_link)
                self.current_weld_point_idx += 1
                self.weld_motion_state = "SOLVE_WAYPOINT"
                self.weld_target_joint_values = {}
                self.main_window.robot.update_kinematics()
                self.main_window.canvas.update_transforms(self.main_window.robot)
                self.main_window.update_live_ui()
                self._set_weld_live_point(target_world)

                self.main_window.log(
                    f"🔥 Weld waypoint reached: path {self.current_weld_path_idx + 1}/{len(self.welding_paths)} "
                    f"step {self.current_weld_point_idx}/{len(waypoints)}"
                )
            else:
                self._record_weld_live_trail(tcp_link)
                self._set_weld_live_point(target_world)
            try:
                self.main_window.canvas.plotter.render()
            except Exception:
                pass

    def _build_welding_payload(self):
        """Build JSON-ready welding paths from the selected edge records."""
        weld_type_choice = self.weld_type_combo.currentText().lower()
        step_mm = float(self.weld_step_sb.value())
        offset_mm = float(self.weld_offset_sb.value())
        torch_angle_deg = float(self.weld_torch_angle_sb.value())
        approach_mm = float(self.weld_approach_sb.value())
        retract_mm = float(self.weld_retract_sb.value())
        feed_mm_s = float(self.weld_feed_sb.value())

        paths = []
        warnings = []
        for idx, edge in enumerate(self.weld_edge_records, start=1):
            path = self._build_edge_weld_path(
                edge,
                weld_type_choice=weld_type_choice,
                step_mm=step_mm,
                offset_mm=offset_mm,
                torch_angle_deg=torch_angle_deg,
                approach_mm=approach_mm,
                retract_mm=retract_mm,
                feed_mm_s=feed_mm_s,
            )
            path["edge_index"] = idx
            paths.append(path)
            warnings.extend(path.get("warnings", []))

        return {
            "mode": "welding",
            "file_import": {
                "supported_formats": ["stl", "step", "stp"],
            },
            "settings": {
                "weld_type": weld_type_choice,
                "step_size_mm": step_mm,
                "offset_mm": offset_mm,
                "torch_angle_deg": torch_angle_deg,
                "approach_mm": approach_mm,
                "retract_mm": retract_mm,
                "feed_mm_s": feed_mm_s,
            },
            "weld_paths": paths,
            "warnings": warnings,
        }

    def _build_edge_weld_path(self, edge, weld_type_choice, step_mm, offset_mm, torch_angle_deg, approach_mm, retract_mm, feed_mm_s):
        """Build a structured path for one selected weld edge."""
        p1_world = np.array(edge["edge_points"][0], dtype=float)
        p2_world = np.array(edge["edge_points"][1], dtype=float)
        link = self.main_window.robot.links.get(edge["link"])
        ratio = self.main_window.canvas.grid_units_per_cm
        mm_to_world = ratio / 10.0
        world_to_mm = 10.0 / ratio
        warnings = []
        live_point_world = getattr(self, "weld_live_point_world", None)
        live_point_edge_index = getattr(self, "weld_live_point_edge_index", None)

        if link is None or link.mesh is None:
            return {
                "link": edge["link"],
                "joint_classification": "unknown",
                "warnings": ["Selected link or mesh is missing."],
                "waypoints": [],
            }

        normals, joint_type = self._infer_weld_geometry(link, p1_world, p2_world, weld_type_choice)
        if not normals:
            warnings.append("Could not infer adjacent face normals; using fallback orientation.")

        weld_points = self._sample_edge_polyline([p1_world, p2_world], step_mm)
        if len(weld_points) < 2:
            warnings.append("Edge segment is very short; path sampling collapsed to endpoints.")
            weld_points = [p1_world, p2_world]

        if live_point_world is not None and live_point_edge_index == edge.get("edge_index"):
            weld_points, live_warning = self._start_edge_from_live_point(weld_points, live_point_world)
            if live_warning:
                warnings.append(live_warning)

        travel = p2_world - p1_world
        travel_norm = np.linalg.norm(travel)
        if travel_norm < 1e-9:
            travel = np.array([1.0, 0.0, 0.0], dtype=float)
            travel_norm = 1.0
            warnings.append("Degenerate edge travel direction; using world X as fallback.")
        travel_dir = travel / travel_norm

        surface_normal = normals.get("average_normal", np.array([0.0, 0.0, 1.0], dtype=float))
        torch_dir = self._compute_torch_direction(surface_normal, travel_dir, torch_angle_deg)

        offset_vec = self._safe_perp_offset(travel_dir, surface_normal, offset_mm, mm_to_world)
        approach_vec = -torch_dir
        retract_vec = torch_dir

        waypoints = []
        start_point = weld_points[0]
        end_point = weld_points[-1]
        start_z_mm = float(start_point[2] * world_to_mm)
        end_z_mm = float(end_point[2] * world_to_mm)

        approach_pt = start_point + approach_vec * (approach_mm * mm_to_world)
        waypoints.append(
            self._make_waypoint(
                "approach",
                approach_pt,
                torch_dir,
                travel_dir,
                "approach",
                feed_mm_s,
                world_to_mm,
                height_mm=float(approach_pt[2] * world_to_mm - start_z_mm),
            )
        )

        for i, pt in enumerate(weld_points):
            phase = "weld"
            if i == 0:
                phase = "start_weld"
            elif i == len(weld_points) - 1:
                phase = "end_weld"
            waypoints.append(
                self._make_waypoint(
                    phase,
                    pt + offset_vec,
                    torch_dir,
                    travel_dir,
                    "weld",
                    feed_mm_s,
                    world_to_mm,
                    height_mm=float(pt[2] * world_to_mm - start_z_mm),
                )
            )

        retract_pt = end_point + retract_vec * (retract_mm * mm_to_world)
        waypoints.append(
            self._make_waypoint(
                "retract",
                retract_pt,
                torch_dir,
                travel_dir,
                "retract",
                feed_mm_s,
                world_to_mm,
                height_mm=float(retract_pt[2] * world_to_mm - end_z_mm),
            )
        )

        if len(weld_points) > 2:
            corner_angles = self._segment_corner_angles(weld_points)
            if any(angle < 135.0 for angle in corner_angles):
                warnings.append("Sharp corner detected in the selected edge path; consider smoothing or splitting the joint.")

        return {
            "link": edge["link"],
            "joint_classification": joint_type,
            "weld_type": joint_type,
            "torch_angle_deg": torch_angle_deg,
            "step_size_mm": step_mm,
            "offset_mm": offset_mm,
            "approach_mm": approach_mm,
            "retract_mm": retract_mm,
            "feed_mm_s": feed_mm_s,
            "edge_points_world_mm": [self._to_mm(p1_world, world_to_mm), self._to_mm(p2_world, world_to_mm)],
            "face_normals_world": [self._unit_list(normals.get("face_a", surface_normal)), self._unit_list(normals.get("face_b", surface_normal))],
            "travel_direction": self._unit_list(travel_dir),
            "tool_axis": self._unit_list(torch_dir),
            "height_profile_mm": self._edge_height_profile_mm(weld_points, world_to_mm),
            "waypoints": waypoints,
            "warnings": warnings,
        }

    def _start_edge_from_live_point(self, weld_points, live_point_world):
        """Start a sampled edge at the chosen live point and continue toward the far end."""
        pts = [np.array(p, dtype=float) for p in weld_points]
        if len(pts) < 2:
            return pts, None

        live_pt = np.array(live_point_world, dtype=float)
        projected = self._project_point_to_segment(live_pt, pts[0], pts[-1])
        if projected is None:
            return pts, "Live weld point could not be projected onto the edge."

        d_first = float(np.linalg.norm(pts[0] - projected))
        d_last = float(np.linalg.norm(pts[-1] - projected))
        if d_last < d_first:
            pts = list(reversed(pts))

        pts = [np.array(projected, dtype=float)] + pts[1:]
        return pts, None

    def _project_point_to_segment(self, point, a, b):
        """Project a world point onto a line segment."""
        p = np.array(point, dtype=float)
        a = np.array(a, dtype=float)
        b = np.array(b, dtype=float)
        ab = b - a
        denom = float(np.dot(ab, ab))
        if denom < 1e-9:
            return a.copy()
        t = float(np.dot(p - a, ab) / denom)
        t = max(0.0, min(1.0, t))
        return a + ab * t

    def _find_nearest_selected_weld_edge(self, point_world):
        """Return the index and projected point for the closest selected weld edge."""
        if not self.weld_edge_records:
            return None, None

        best_idx = None
        best_proj = None
        best_dist = float("inf")
        for idx, edge in enumerate(self.weld_edge_records, start=1):
            p1, p2 = edge["edge_points"]
            proj = self._project_point_to_segment(point_world, p1, p2)
            dist = float(np.linalg.norm(np.array(point_world, dtype=float) - np.array(proj, dtype=float)))
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
                best_proj = proj
        return best_idx, best_proj

    def _set_weld_live_point(self, point_world):
        """Store the weld live point but don't render a sphere marker."""
        pt = np.array(point_world, dtype=float)
        self.weld_live_point_world = pt
        # Sphere marker removed - only the visual trail is shown

    def _infer_weld_geometry(self, link, p1_world, p2_world, weld_type_choice):
        """Infer adjacent face normals and classify the weld joint."""
        try:
            import trimesh
        except Exception:
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        mesh = link.mesh
        if not isinstance(mesh, trimesh.Trimesh):
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        inv = np.linalg.inv(link.t_world)
        p1_local = (inv @ np.append(p1_world, 1.0))[:3]
        p2_local = (inv @ np.append(p2_world, 1.0))[:3]

        verts = np.asarray(mesh.vertices)
        if len(verts) == 0:
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        vid1 = int(np.argmin(np.linalg.norm(verts - p1_local, axis=1)))
        vid2 = int(np.argmin(np.linalg.norm(verts - p2_local, axis=1)))
        if vid1 == vid2:
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        face_adj = getattr(mesh, "face_adjacency", None)
        face_adj_edges = getattr(mesh, "face_adjacency_edges", None)
        if face_adj is None or face_adj_edges is None or len(face_adj) == 0:
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        target_edge = tuple(sorted((vid1, vid2)))
        chosen_faces = None
        for edge_pair, faces in zip(face_adj_edges, face_adj):
            if tuple(sorted((int(edge_pair[0]), int(edge_pair[1])))) == target_edge:
                chosen_faces = faces
                break

        if chosen_faces is None:
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        face_a = int(chosen_faces[0])
        face_b = int(chosen_faces[1])
        normal_a = np.array(mesh.face_normals[face_a], dtype=float)
        normal_b = np.array(mesh.face_normals[face_b], dtype=float)
        if np.linalg.norm(normal_a) < 1e-9 or np.linalg.norm(normal_b) < 1e-9:
            return {}, weld_type_choice if weld_type_choice != "auto" else "fillet"

        normal_a /= np.linalg.norm(normal_a)
        normal_b /= np.linalg.norm(normal_b)
        avg = normal_a + normal_b
        if np.linalg.norm(avg) < 1e-9:
            avg = normal_a
        avg /= np.linalg.norm(avg)

        dihedral_deg = float(np.degrees(np.arccos(np.clip(np.dot(normal_a, normal_b), -1.0, 1.0))))
        if weld_type_choice != "auto":
            joint_type = weld_type_choice
        elif dihedral_deg < 25.0:
            joint_type = "butt"
        elif dihedral_deg < 120.0:
            joint_type = "fillet"
        else:
            joint_type = "lap"

        return {
            "face_a": normal_a,
            "face_b": normal_b,
            "average_normal": avg,
            "dihedral_deg": dihedral_deg,
        }, joint_type

    def _sample_edge_polyline(self, points_world, step_mm):
        """Sample a polyline with a fixed waypoint spacing."""
        if len(points_world) < 2:
            return [np.array(points_world[0], dtype=float)] if points_world else []

        step_world = step_mm * (self.main_window.canvas.grid_units_per_cm / 10.0)
        sampled = [np.array(points_world[0], dtype=float)]
        for idx in range(len(points_world) - 1):
            a = np.array(points_world[idx], dtype=float)
            b = np.array(points_world[idx + 1], dtype=float)
            seg = b - a
            seg_len = float(np.linalg.norm(seg))
            if seg_len < 1e-9:
                continue
            n = max(1, int(np.floor(seg_len / max(step_world, 1e-9))))
            for i in range(1, n + 1):
                t = min(1.0, (i * step_world) / seg_len)
                pt = a + seg * t
                if np.linalg.norm(pt - sampled[-1]) > 1e-6:
                    sampled.append(pt)
        if np.linalg.norm(sampled[-1] - np.array(points_world[-1], dtype=float)) > 1e-6:
            sampled.append(np.array(points_world[-1], dtype=float))
        return sampled

    def _edge_height_profile_mm(self, points_world, world_to_mm):
        """Return height offsets along the edge relative to its start point."""
        if not points_world:
            return []
        base_z = float(np.array(points_world[0], dtype=float)[2])
        profile = []
        for pt in points_world:
            z_mm = (float(np.array(pt, dtype=float)[2]) - base_z) * world_to_mm
            profile.append(float(z_mm))
        return profile

    def _segment_corner_angles(self, points_world):
        """Return internal corner angles for a polyline."""
        angles = []
        for i in range(1, len(points_world) - 1):
            a = np.array(points_world[i - 1], dtype=float)
            b = np.array(points_world[i], dtype=float)
            c = np.array(points_world[i + 1], dtype=float)
            v1 = a - b
            v2 = c - b
            n1 = np.linalg.norm(v1)
            n2 = np.linalg.norm(v2)
            if n1 < 1e-9 or n2 < 1e-9:
                continue
            ang = np.degrees(np.arccos(np.clip(np.dot(v1 / n1, v2 / n2), -1.0, 1.0)))
            angles.append(float(ang))
        return angles

    def _compute_torch_direction(self, surface_normal, travel_dir, torch_angle_deg):
        """Compute a torch axis that is tilted toward the weld travel direction."""
        n = np.array(surface_normal, dtype=float)
        if np.linalg.norm(n) < 1e-9:
            n = np.array([0.0, 0.0, 1.0], dtype=float)
        n /= np.linalg.norm(n)

        t = np.array(travel_dir, dtype=float)
        if np.linalg.norm(t) < 1e-9:
            t = np.array([1.0, 0.0, 0.0], dtype=float)
        t /= np.linalg.norm(t)

        side = np.cross(t, n)
        if np.linalg.norm(side) < 1e-9:
            side = np.cross(t, np.array([0.0, 0.0, 1.0], dtype=float))
        if np.linalg.norm(side) < 1e-9:
            side = np.array([0.0, 1.0, 0.0], dtype=float)
        side /= np.linalg.norm(side)

        # Interpret the input angle as inclination from the surface normal.
        incl = np.deg2rad(np.clip(90.0 - torch_angle_deg, 0.0, 90.0))
        torch_dir = (-n * np.cos(incl)) + (side * np.sin(incl))
        if np.linalg.norm(torch_dir) < 1e-9:
            torch_dir = -n
        return torch_dir / np.linalg.norm(torch_dir)

    def _safe_perp_offset(self, travel_dir, surface_normal, offset_mm, mm_to_world):
        """Create a stable offset vector for bead placement."""
        if abs(offset_mm) < 1e-9:
            return np.zeros(3)
        t = np.array(travel_dir, dtype=float)
        n = np.array(surface_normal, dtype=float)
        side = np.cross(t, n)
        if np.linalg.norm(side) < 1e-9:
            side = np.array([0.0, 1.0, 0.0], dtype=float)
        side /= np.linalg.norm(side)
        return side * (offset_mm * mm_to_world)

    def _make_waypoint(self, phase, position_world, torch_dir, travel_dir, motion_mode, feed_mm_s, world_to_mm, height_mm=0.0):
        return {
            "phase": phase,
            "position_world_mm": self._to_mm(position_world, world_to_mm),
            "height_from_start_mm": float(height_mm),
            "tool_axis": self._unit_list(torch_dir),
            "travel_direction": self._unit_list(travel_dir),
            "motion_mode": motion_mode,
            "feed_mm_s": feed_mm_s,
        }

    def _to_mm(self, point_world, world_to_mm):
        return [float(v * world_to_mm) for v in np.array(point_world, dtype=float)]

    def _unit_list(self, vec):
        arr = np.array(vec, dtype=float)
        n = np.linalg.norm(arr)
        if n < 1e-9:
            return [0.0, 0.0, 1.0]
        return [float(v) for v in (arr / n)]

    def _move_weld_smoothly(self):
        """Move robot joints toward the current weld waypoint targets."""
        if not self.weld_target_joint_values or not self.weld_joint_chain:
            return True

        all_done = True
        step_deg = max(0.5, float(getattr(self, "motion_speed", 5.0)))

        for joint in self.weld_joint_chain:
            target = self.weld_target_joint_values.get(joint.name, joint.current_value)
            diff = target - joint.current_value
            if abs(diff) < 0.08:
                if joint.current_value != target:
                    self._update_joint_and_slaves(joint, target)
                continue

            all_done = False
            new_val = target if abs(step_deg) > abs(diff) else joint.current_value + (step_deg if diff > 0 else -step_deg)
            new_val = np.clip(new_val, joint.min_limit, joint.max_limit)
            self._update_joint_and_slaves(joint, new_val)

        self.main_window.canvas.update_transforms(self.main_window.robot)
        self.main_window.update_live_ui()
        return all_done

    def _record_weld_live_trail(self, tcp_link_or_world):
        """Store a running weld trail so the live point path is visible in 3D."""
        if tcp_link_or_world is None:
            return

        world_pt = None
        # Backwards-compatible: allow either a TCP link object or a direct world point.
        if hasattr(tcp_link_or_world, "t_world"):
            world_pt, _, _ = self.main_window.get_link_tool_point(tcp_link_or_world, return_vec=True)
        else:
            world_pt = tcp_link_or_world

        if world_pt is None:
            return

        pt = np.array(world_pt, dtype=float).reshape(-1)
        if pt.size < 3:
            return
        pt = pt[:3]
        if not hasattr(self, "weld_live_trail_points"):
            self.weld_live_trail_points = []

        if self.weld_live_trail_points:
            if np.linalg.norm(pt - self.weld_live_trail_points[-1]) < 1e-6:
                return

        self.weld_live_trail_points.append(pt)
        # Sphere marker removed - only the trail line is visualized
        self._update_weld_live_trail_visual(render=False)

    def _update_weld_live_trail_visual(self, render=True):
        """Draw the weld live-point trail in the 3D graph."""
        try:
            import pyvista as pv
        except Exception:
            return

        canvas = self.main_window.canvas
        actor_name = getattr(self, "weld_live_trail_actor_name", "weld_live_trail")

        try:
            canvas.plotter.remove_actor(actor_name)
        except Exception:
            pass

        if len(self.weld_live_trail_points) < 2:
            if render:
                canvas.plotter.render()
            return

        trail = pv.lines_from_points(np.array(self.weld_live_trail_points, dtype=float))
        canvas.plotter.add_mesh(
            trail,
            color="#00acc1",
            line_width=4,
            name=actor_name,
            pickable=False,
        )
        if render:
            canvas.plotter.render()

    def _clear_weld_live_trail(self):
        """Remove the weld live-point trail from the scene."""
        if not hasattr(self, "main_window") or not hasattr(self.main_window, "canvas"):
            return
        try:
            self.main_window.canvas.plotter.remove_actor(getattr(self, "weld_live_trail_actor_name", "weld_live_trail"))
        except Exception:
            pass
        try:
            if hasattr(self.main_window.canvas, "clear_live_point_marker"):
                self.main_window.canvas.clear_live_point_marker(name="weld_live_point")
                self.main_window.canvas.clear_live_point_marker(name="weld_target_point")
        except Exception:
            pass
        try:
            self.main_window.canvas.plotter.render()
        except Exception:
            pass

    def toggle_pick_place_sim(self, checked):
        """Enable automated pick-and-place monitoring with sequential motion."""
        if checked:
            # === PRE-FLIGHT VALIDATION ===
            # 1. Verify an object is selected
            current_item = self.objects_list.currentItem()
            if not current_item:
                self.main_window.log("âš ï¸ No simulation object selected. Please select an object from the list first.")
                self.main_window.show_toast("Select an object first!", "warning")
                self.start_btn.blockSignals(True)
                self.start_btn.setChecked(False)
                self.start_btn.blockSignals(False)
                return

            obj_name = current_item.text()
            if obj_name not in self.main_window.robot.links:
                self.main_window.log("âš ï¸ Selected object not found in robot model.")
                self.start_btn.blockSignals(True)
                self.start_btn.setChecked(False)
                self.start_btn.blockSignals(False)
                return

            # 2. Refresh dimensions from mesh if DIM fields are still zero
            if self.obj_height.value() == 0.0 and self.obj_width.value() == 0.0:
                self.refresh_object_info(obj_name)
                self.main_window.log(f"ðŸ“ Auto-populated dimensions for '{obj_name}' before simulation.")

            # 3. Verify TCP link is available
            tcp_link = self._get_tcp_link()
            if tcp_link is None:
                self.main_window.log("âš ï¸ No TCP (Live Point) link found on robot. Cannot start simulation.")
                self.main_window.show_toast("No TCP found!", "warning")
                self.start_btn.blockSignals(True)
                self.start_btn.setChecked(False)
                self.start_btn.blockSignals(False)
                return

            target_checks = [
                ("P1", 0.0),
                ("P2", 0.0),
            ]
            for target_name, z_offset_cm in target_checks:
                if not self._check_target_feasibility(target_name, tcp_link, z_offset_cm=z_offset_cm):
                    msg = "These coordinates are not feasible to achieve. Try other coordinates."
                    self.main_window.log(f"âš ï¸ {target_name}: {msg} Continuing with best-effort planning.")

            auto_plan = self._auto_prepare_gripper_for_pick_place(tcp_link=tcp_link, quiet=False)
            if isinstance(auto_plan, dict) and not auto_plan.get("configured", False):
                self.main_window.log(
                    "âš ï¸ Auto-gripper preparation is incomplete. "
                    "Pick-and-place will run with generic fallback geometry."
                )

            self.pick_place_plan = self._build_pick_place_plan(tcp_link)
            plan_reason = self.pick_place_plan.get("reason")
            plan_warnings = self.pick_place_plan.get("warnings", []) or []
            for warning in plan_warnings:
                self.main_window.log(f"âš ï¸ {warning}")

            if not self.pick_place_plan.get("feasible", True):
                fatal_reasons = {
                    "No object selected",
                    "Selected object missing",
                }
                if plan_reason in fatal_reasons:
                    msg = self.pick_place_plan.get(
                        "reason",
                        "These coordinates are not feasible to achieve. Try other coordinates."
                    )
                    self.main_window.log(f"âš ï¸ Grasp plan rejected: {msg}")
                    self.main_window.show_toast("Grasp plan rejected", "warning")
                    self.start_btn.blockSignals(True)
                    self.start_btn.setChecked(False)
                    self.start_btn.blockSignals(False)
                    return

                self.main_window.log(
                    "âš ï¸ Grasp plan marked as best effort. "
                    "Continuing with pick-and-place instead of rejecting the run."
                )
                self.main_window.show_toast("Grasp plan warning", "warning")

            gap_value = self.pick_place_plan.get("finger_gap_cm")
            gap_text = f"{gap_value:.2f} cm" if gap_value is not None else "n/a"
            ratio = self.main_window.canvas.grid_units_per_cm
            open_text = self.pick_place_plan.get("open_gap_world")
            close_text = self.pick_place_plan.get("close_gap_world")
            release_text = self.pick_place_plan.get("release_open_gap_world")
            open_cm = open_text / ratio if open_text is not None else None
            close_cm = close_text / ratio if close_text is not None else None
            release_cm = release_text / ratio if release_text is not None else None
            max_open_cm = self.pick_place_plan.get("max_open_gap_cm")
            max_open_text = f"{max_open_cm:.2f} cm" if max_open_cm is not None else "n/a"
            self.main_window.log(
                "ðŸ§  Industrial grasp plan: "
                f"gap={gap_text}, "
                f"part={self.pick_place_plan['object_thickness_cm']:.2f} cm, "
                f"clearance={self.pick_place_plan['clearance_cm']:.2f} cm, "
                f"open={open_cm:.2f} cm, "
                f"close={close_cm:.2f} cm, "
                f"release={release_cm:.2f} cm, "
                f"max_open={max_open_text}, "
                f"approach={self.pick_place_plan['approach_z_cm']:.2f} cm, "
                f"lift={self.pick_place_plan['lift_z_cm']:.2f} cm, "
                f"transit={self.pick_place_plan['transit_z_cm']:.2f} cm, "
                f"route={self.pick_place_plan.get('route_mode', 'default')}."
            )
            self.main_window.log("   Parallel Workflow: pick -> transit -> place stays on one flat overhead plane.")

            # === START SEQUENCE ===
            self.is_sim_active = True
            self.main_window.log("â”€" * 50)
            self.main_window.log("ðŸš€ STARTING PICK-AND-PLACE SEQUENCE")
            self.main_window.log(f"   Object : {obj_name}")
            self.main_window.log(f"   DIM    : {self.obj_width.value():.1f} x {self.obj_depth.value():.1f} x {self.obj_height.value():.1f} cm")
            self.main_window.log(f"   P1 (Bottom Face Center) : ({self.pick_x.value():.1f}, {self.pick_y.value():.1f}, {self.pick_z.value():.1f}) cm")
            self.main_window.log(f"   P2 (Bottom Face Center) : ({self.place_x.value():.1f}, {self.place_y.value():.1f}, {self.place_z.value():.1f}) cm")
            self.main_window.log(f"   HOME (End) : ({self.home_x.value():.1f}, {self.home_y.value():.1f}, {self.home_z.value():.1f}) cm")
            self.main_window.log(f"   TCP Link   : {tcp_link.name}")
            _, _, preflight_geo = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
            if isinstance(preflight_geo, dict) and preflight_geo.get("using_selected_gripping_surfaces"):
                self.main_window.log("   Grip Mode  : Selected gripping faces (industrial face-to-face clamp)")
            else:
                self.main_window.log("   Grip Mode  : Generic finger geometry fallback")
            self.main_window.log("â”€" * 50)

            self.start_btn.setText("ðŸ›‘ Stop Simulation")
            self.start_btn.setStyleSheet("background-color: #f44336; color: white; border-radius: 8px; font-weight: bold; font-size: 14px;")

            # === Snapshot initial joint state so we can return later ===
            self._initial_joint_state = {
                n: j.current_value
                for n, j in self.main_window.robot.joints.items()
            }

            # Reset Sequence
            self.sim_state = "OPEN_GRIPPER"   # first: open gripper to object width
            self.main_window.log("ðŸ“ Initializing motion sequence from Robot Base...")
            self.gripped_object = None
            self.grip_offset = None
            self.grip_original_rotation = None
            self.grip_fixed_rotation = None
            self.grip_local_center = None
            self.grip_anchor_world = None
            self.target_joint_values = {}
            self._target_gripper_angles = {}  # for smooth animation
            self.active_joint_index = 0

            self.sim_timer.start(50)  # Ticking every 50 ms
        else:
            self.main_window.log("ðŸ›‘ Simulation Stopped.")
            self.start_btn.setText("ðŸš€ Start Simulation")
            self.start_btn.setStyleSheet("background-color: #fdd835; color: #212121; border-radius: 8px; font-weight: bold; font-size: 14px;")
            self.sim_timer.stop()
            self.is_sim_active = False
            self.sim_state = "IDLE"

            # Reset state
            self.gripped_object = None
            self.grip_offset = None
            self.grip_original_rotation = None
            self.grip_fixed_rotation = None
            self.grip_local_center = None
            self.grip_anchor_world = None
            self.main_window.canvas.clear_highlights()
            self.main_window.canvas.plotter.render()
            self.pick_place_plan = {}

    def _safe_on_sim_tick(self):
        """Runs the simulation tick and turns runtime errors into a clean stop."""
        try:
            self._on_sim_tick()
        except Exception:
            err_msg = traceback.format_exc()
            self.main_window.log("Simulation error encountered. Stopping safely.")
            self.main_window.log(err_msg)
            self.main_window.show_toast("Simulation stopped due to an error", "error")
            self.sim_timer.stop()
            self.is_sim_active = False
            self.sim_state = "IDLE"
            if hasattr(self, "start_btn"):
                self.start_btn.blockSignals(True)
                self.start_btn.setChecked(False)
                self.start_btn.blockSignals(False)
                self.start_btn.setText("ðŸš€ Start Simulation")
                self.start_btn.setStyleSheet(
                    "background-color: #fdd835; color: #212121; border-radius: 8px; font-weight: bold; font-size: 14px;"
                )
            
    def _on_sim_tick(self):
        if not self.is_sim_active:
            return

        # 1. Identify TCP link
        tcp_link = self._get_tcp_link()
        if tcp_link is None:
            return

        # 2. STATE MACHINE (Industrial Sequence)
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        #  OPEN_GRIPPER      â†’ size gripper to fit around object (with clearance)
        #  SOLVE_APPROACH_P1 â†’ plan path to Safe Point (5cm above P1)
        #  MOVE_APPROACH_P1  â†’ travel to safe approach point
        #  SOLVE_PICK_P1     â†’ plan descent to exact P1
        #  MOVE_PICK_P1      â†’ descend vertically to grip object
        #  GRIP              â†’ close fingers to snugly grip the object
        #  SOLVE_LIFT_P1     â†’ plan path back to Safe Point (5cm above P1)
        #  MOVE_LIFT_P1      â†’ lift object vertically from surface
        #  SOLVE_APPROACH_P2 â†’ plan path to Safe Point (5cm above P2)
        #  MOVE_APPROACH_P2  â†’ transit to safe place point
        #  SOLVE_PLACE_P2    â†’ plan descent to exact P2
        #  MOVE_PLACE_P2     â†’ descend to place object at destination
        #  RELEASE           â†’ open fingers, drop object at P2
        #  SOLVE_RETRACT_P2  â†’ plan path back to Safe Point (5cm above P2)
        #  MOVE_RETRACT_P2   â†’ retract vertically from destination
        #  SOLVE_HOME        â†’ plan path to home point
        #  MOVE_HOME         â†’ move robot to home point
        #  DONE              â†’ sequence complete
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        if self.sim_state == "OPEN_GRIPPER":
            if not self._target_gripper_angles:
                grip_width, _, _ = self._get_object_grip_width()
                ratio = self.main_window.canvas.grid_units_per_cm
                if grip_width > 0:
                    approach_gap = self.pick_place_plan.get(
                        "open_gap_world",
                        grip_width + (0.5 * ratio)
                    )
                    self._presise_gripper_for_approach(target_gap_world=approach_gap)
                    self.main_window.log(
                        f"Opening gripper to {approach_gap/ratio:.2f} cm before approach."
                    )
                else:
                    # No width info â€” open fully
                    self._target_gripper_angles = self.main_window._control_gripper_fingers(
                        close=False, apply=False
                    )
                    # If still empty (no gripper joints), skip immediately
                    if not self._target_gripper_angles:
                        self.main_window.log("â„¹ï¸ No gripper joints found â€” skipping OPEN_GRIPPER.")
                        self.sim_state = "SOLVE_APPROACH_P1"
                        return
                    self.main_window.log("ðŸ‘ Opening gripper fully before approach...")

            done = self._move_gripper_smoothly()
            if done:
                self.main_window.log("âœ… Gripper open. Commencing movement from Base reference to P1...")
                self._target_gripper_angles = {}
                self.sim_state = "SOLVE_APPROACH_P1"

        elif self.sim_state == "SOLVE_APPROACH_P1":
            self._handle_state_solve(
                "P1",
                tcp_link,
                next_state="MOVE_APPROACH_P1",
                z_offset_cm=self.pick_place_plan.get("transit_z_cm", self.pick_place_plan.get("approach_z_cm", 5.0))
            )

        elif self.sim_state == "MOVE_APPROACH_P1":
            if self._handle_sequential_motion():
                self.main_window.log("ðŸ“ Reached safe approach point. Descending to P1...")
                self.sim_state = "SOLVE_PICK_P1"

        elif self.sim_state == "SOLVE_PICK_P1":
            self._handle_state_solve("P1", tcp_link, next_state="MOVE_PICK_P1", z_offset_cm=0.0)

        elif self.sim_state == "MOVE_PICK_P1":
            if self._handle_sequential_motion():
                self.main_window.log("ðŸ“ Reached P1. Closing gripper to grip object...")
                self.sim_state = "GRIP"

        elif self.sim_state == "GRIP":
            if not self._target_gripper_angles:
                self._prepare_grip_targets(tcp_link)
            
            if self._move_gripper_smoothly():
                self._finalize_grip(tcp_link)
                self.main_window.log("ðŸ§² Object gripped. Lifting object from P1...")
                self._target_gripper_angles = {}
                self.sim_state = "SOLVE_LIFT_P1"

        elif self.sim_state == "SOLVE_LIFT_P1":
            self._handle_state_solve(
                "P1",
                tcp_link,
                next_state="MOVE_LIFT_P1",
                z_offset_cm=self.pick_place_plan.get("transit_z_cm", self.pick_place_plan.get("lift_z_cm", 5.0))
            )

        elif self.sim_state == "MOVE_LIFT_P1":
            self._carry_gripped_object(tcp_link)
            if self._handle_sequential_motion():
                self.main_window.log("ðŸ“ Lift complete. Moving to P2 approach...")
                self.sim_state = "SOLVE_APPROACH_P2"

        elif self.sim_state == "SOLVE_APPROACH_P2":
            self._handle_state_solve(
                "P2",
                tcp_link,
                next_state="MOVE_APPROACH_P2",
                z_offset_cm=self.pick_place_plan.get("transit_z_cm", self.pick_place_plan.get("approach_z_cm", 5.0))
            )

        elif self.sim_state == "MOVE_APPROACH_P2":
            self._carry_gripped_object(tcp_link)
            if self._handle_sequential_motion():
                self.main_window.log("ðŸ“ Reached P2 approach point. Descending to place...")
                self.sim_state = "SOLVE_PLACE_P2"

        elif self.sim_state == "SOLVE_PLACE_P2":
            self._handle_state_solve("P2", tcp_link, next_state="MOVE_PLACE_P2", z_offset_cm=0.0)

        elif self.sim_state == "MOVE_PLACE_P2":
            self._carry_gripped_object(tcp_link)
            if self._handle_sequential_motion():
                self.main_window.log("ðŸ“ Reached P2. Opening gripper to release object...")
                self.sim_state = "RELEASE"

        elif self.sim_state == "RELEASE":
            if not self._target_gripper_angles:
                self._prepare_release_targets()
            
            if self._move_gripper_smoothly():
                self._finalize_release()
                self.main_window.log("ðŸ“¦ Object released. Retracting from P2...")
                self._target_gripper_angles = {}
                self.sim_state = "SOLVE_RETRACT_P2"

        elif self.sim_state == "SOLVE_RETRACT_P2":
            self._handle_state_solve(
                "P2",
                tcp_link,
                next_state="MOVE_RETRACT_P2",
                z_offset_cm=self.pick_place_plan.get("transit_z_cm", self.pick_place_plan.get("lift_z_cm", 5.0))
            )

        elif self.sim_state == "MOVE_RETRACT_P2":
            if self._handle_sequential_motion():
                self.main_window.log("ðŸ“ Retract complete. Moving to home position...")
                self.sim_state = "SOLVE_HOME"

        elif self.sim_state == "SOLVE_HOME":
            if False and not self._check_target_feasibility("HOME", tcp_link, z_offset_cm=0.0):
                msg = "These coordinates are not feasible to achieve. Try other coordinates."
                self.main_window.log(f"âš ï¸ HOME: {msg}")
                self._handle_unreachable_target("HOME", msg)
                self.sim_timer.stop()
                self.is_sim_active = False
                self.sim_state = "IDLE"
                self.start_btn.setChecked(False)
                self.start_btn.setText("ðŸš€ Start Simulation")
                self.start_btn.setStyleSheet(
                    "background-color: #fdd835; color: #212121; border-radius: 8px; font-weight: bold; font-size: 14px;"
                )
                return
            self._handle_state_solve("HOME", tcp_link, next_state="MOVE_HOME", z_offset_cm=0.0)

        elif self.sim_state == "MOVE_HOME":
            if self._handle_sequential_motion():
                self.main_window.log("âœ¨ Home position reached. Pick-and-place sequence complete.")
                self.sim_state = "DONE"

        elif self.sim_state == "DONE":
            self.sim_timer.stop()
            self._on_task_completed()
            self.sim_state = "IDLE"
            return 

        # Sync UI after every tick
        self._sync_all_sliders()
        self.main_window.canvas.update_transforms(self.main_window.robot)
        self.main_window.update_live_ui()

    def _get_object_grip_width(self):
        """
        Measures the object's thickness along the gripper's opening axis
        and the world-space height of the selected sim object.
        Returns (grip_size_world, z_offset_world, obj_link)
        """
        item = self.objects_list.currentItem()
        if not item:
            return 0.0, 0.0, None
        obj_name = item.text()
        if obj_name not in self.main_window.robot.links:
            return 0.0, 0.0, None

        obj_link = self.main_window.robot.links[obj_name]
        if not obj_link.mesh:
            return 0.0, 0.0, obj_link

        ratio = self.main_window.canvas.grid_units_per_cm
        raw_size = obj_link.mesh.bounds[1] - obj_link.mesh.bounds[0]
        tcp_link = self._get_tcp_link()
        geo_data = None
        using_selected_faces = False
        if tcp_link:
            _, _, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
            using_selected_faces = bool(
                isinstance(geo_data, dict) and geo_data.get("using_selected_gripping_surfaces")
            )

        # --- NEW: Prioritize Manual User Inputs (Industrial Standard) ---
        m_w = self.obj_width.value() * ratio
        m_d = self.obj_depth.value() * ratio
        m_h = self.obj_height.value() * ratio

        has_manual_values = (m_h > 0 or m_w > 0 or m_d > 0)
        manual_override = has_manual_values
        if has_manual_values:
            # DIM fields are auto-filled from mesh on object selection.
            # Treat them as a true manual override only when they differ from mesh size.
            auto_w = raw_size[0] / ratio
            auto_d = raw_size[1] / ratio
            auto_h = raw_size[2] / ratio
            eps_cm = 0.05
            manual_override = (
                abs(self.obj_width.value() - auto_w) > eps_cm
                or abs(self.obj_depth.value() - auto_d) > eps_cm
                or abs(self.obj_height.value() - auto_h) > eps_cm
            )

        # In selected-face mode, prefer geometric axis measurement unless user explicitly overrode DIM values.
        if has_manual_values and (not using_selected_faces or manual_override):
            # Use manual height for z_offset (centrally gripped)
            z_offset = m_h / 2.0 if m_h > 0 else 0.0
            if using_selected_faces:
                # In face mode, width is interpreted as face-to-face clamp thickness.
                manual_grip_width = m_w if m_w > 0 else max(m_d, 0.0)
            else:
                # Use max of width/depth for grip width safety if mesh detection fails
                manual_grip_width = max(m_w, m_d)
            if using_selected_faces:
                self.main_window.log(
                    f"Face Mode: Using manual face-to-face width {manual_grip_width/ratio:.2f} cm."
                )
            else:
                self.main_window.log(
                    f"Balancing: Using manual dimensions ({m_w/ratio:.1f}x{m_d/ratio:.1f}x{m_h/ratio:.1f} cm)."
                )
            return manual_grip_width, z_offset, obj_link

        # --- FALLBACK: Geometric detection from mesh ---
        # 1. Height calculation (consistent)
        R_obj = obj_link.t_world[:3, :3]
        world_extents = np.abs(R_obj @ raw_size)
        z_offset = world_extents[2] / 2.0

        # 2. Geometric Grip Width Calculation
        # To "hold perfectly", measure thickness along the active gripping strategy.
        grip_width = 0.0
        
        if tcp_link:
            # --- Project all object mesh vertices for geometric measurement ---
            # Vertices in world space
            verts_world = (obj_link.t_world[:3, :3] @ obj_link.mesh.vertices.T).T + obj_link.t_world[:3, 3]
            
            if using_selected_faces and isinstance(geo_data, dict):
                # Clamp strictly along the selected gripping-face axis.
                grip_axis = np.array(
                    geo_data.get("primary_axis", np.array([1.0, 0.0, 0.0])),
                    dtype=float
                )
                axis_norm = np.linalg.norm(grip_axis)
                if axis_norm < 1e-9:
                    grip_axis = tcp_link.t_world[:3, 0]
                    axis_norm = np.linalg.norm(grip_axis)
                if axis_norm > 1e-9:
                    grip_axis = grip_axis / axis_norm
                projections = verts_world @ grip_axis
                grip_width = float(np.ptp(projections))
                self.main_window.log(
                    f"Face Mode: Measured object thickness {grip_width/ratio:.2f} cm along selected face axis."
                )
            elif isinstance(geo_data, dict) and "fingers_world" in geo_data:
                # N-FINGER LOGIC: 
                # For each finger, measure thickness along the radial axis (Centroid -> Finger)
                # and tangential axes (Finger -> Finger).
                max_observed = 0.0
                centers = geo_data["fingers_world"]
                centroid = np.mean(centers, axis=0)
                
                # Axes to check:
                check_axes = []
                # Radial axes
                for c in centers:
                    v = c - centroid
                    if np.linalg.norm(v) > 1e-3:
                        check_axes.append(v / np.linalg.norm(v))
                
                # Tangential axes (Finger to Finger)
                for i in range(len(centers)):
                    for j in range(i + 1, len(centers)):
                        v = centers[i] - centers[j]
                        if np.linalg.norm(v) > 1e-3:
                            check_axes.append(v / np.linalg.norm(v))
                
                # Use the primary axis from the data if available
                if "primary_axis" in geo_data:
                    v = geo_data["primary_axis"]
                    check_axes.append(v / np.linalg.norm(v))
                
                # Hold the object "between" them: 
                # The effective grip width is the maximum chord of the object among all these axes.
                for axis in check_axes:
                    projections = verts_world @ axis
                    max_observed = max(max_observed, np.ptp(projections))
                
                grip_width = max_observed
            else:
                # FALLBACK: Use simple primary axis if data is just a vector
                grip_axis = geo_data if geo_data is not None else tcp_link.t_world[:3, 0]
                if np.linalg.norm(grip_axis) < 1e-3: grip_axis = np.array([1,0,0])
                grip_axis /= np.linalg.norm(grip_axis)
                
                projections = verts_world @ grip_axis
                grip_width = np.ptp(projections)
        else:
            # Fallback to world-space bounding box
            grip_width = max(world_extents[0], world_extents[1])


        return grip_width, z_offset, obj_link


    def _presise_gripper_for_approach(self, target_gap_world=None):
        """Open gripper before approach, preferably to object width + clearance."""
        if target_gap_world is not None:
            self._target_gripper_angles = self.main_window._control_gripper_fingers(
                close=False,
                target_gap_world=target_gap_world,
                apply=False
            )
        else:
            self._target_gripper_angles = self.main_window._control_gripper_fingers(
                close=False,
                apply=False
            )

        if self._target_gripper_angles:
            ratio = self.main_window.canvas.grid_units_per_cm
            gap_limits = getattr(self.main_window, '_last_gripper_gap_limits', {}) or {}
            if gap_limits:
                min_gap = min(limit[0] for limit in gap_limits.values())
                max_gap = max(limit[1] for limit in gap_limits.values())
                self.main_window.log(
                    f"Gripper face range: {min_gap/ratio:.2f} to {max_gap/ratio:.2f} cm."
                )
            for j_name, angle in self._target_gripper_angles.items():
                self.main_window.log(f"   Main '{j_name}' target: {angle:.2f} deg")


    def _prepare_grip_targets(self, tcp_link):
        """Calculates targets to fully close the gripper at the object position."""
        ratio = self.main_window.canvas.grid_units_per_cm
        _, _, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        using_selected_faces = bool(
            isinstance(geo_data, dict) and geo_data.get("using_selected_gripping_surfaces")
        )

        if using_selected_faces:
            self.main_window.log(
                "Face Mode: Closing fully at the object position; contact limits will stop the jaws."
            )
        else:
            self.main_window.log(
                "ðŸ§² Closing fully at the object position; collision/contact will stop the jaws on the object."
            )

        self._target_gripper_angles = self.main_window._control_gripper_fingers(
            close=True,
            apply=False
        )
        gap_limits = getattr(self.main_window, "_last_gripper_gap_limits", {}) or {}
        if gap_limits:
            min_gap = min(limit[0] for limit in gap_limits.values())
            max_gap = max(limit[1] for limit in gap_limits.values())
            self.main_window.log(
                f"Clamp range: {min_gap/ratio:.2f} to {max_gap/ratio:.2f} cm."
            )

        if self._target_gripper_angles:
            for j_name, angle in self._target_gripper_angles.items():
                self.main_window.log(f"   âˆŸ Main '{j_name}' calculated target: {angle:.2f}Â°")
                for s_id, ratio in self.main_window.robot.joint_relations.get(j_name, []):
                    self.main_window.log(f"      âˆŸ Slave Folding Joint '{s_id}' target: {angle * ratio:.2f}Â°")


    def _finalize_grip(self, tcp_link):
        """Actually attaches the object to the robot after gripper finished closing."""
        _, _, obj_link = self._get_object_grip_width()
        if not obj_link or not obj_link.mesh: return

        # 1. Compute the exact TCP (centroid of fingers) at this moment
        world_tcp, local_tcp, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        
        # 2. Perfect Centering: Use mesh centroid instead of axis-aligned bounds midpoint
        local_center = obj_link.mesh.centroid
        
        # 3. Create a 'Perfect Hold' pose for the object
        # Keep the object parallel to the world floor and only move it with the TCP.
        t_obj_perfect = np.eye(4)
        R_obj = self._make_world_parallel_rotation(obj_link.t_world[:3, :3])
        self.grip_fixed_rotation = R_obj.copy()
        self.grip_local_center = local_center.copy()
        self.grip_anchor_world = world_tcp.copy()
        
        # Set world translation so centroid aligns exactly with TCP
        t_obj_perfect[:3, 3] = world_tcp - R_obj @ local_center
        
        # Store the world pose so we can reuse the same orientation while carrying
        self.grip_offset = t_obj_perfect.copy()
        self.gripped_object = obj_link.name
        self.grip_original_rotation = R_obj.copy()
        
        # Apply immediately to the link offset
        obj_link.t_offset = t_obj_perfect
        self.main_window.robot.update_kinematics()
        
        # --- PERFECT GRIP FEEDBACK ---
        self.main_window.log(f"âœ… PERFECT GRIP: '{obj_link.name}' is now physically held by {len(tcp_link.child_joints)} finger components.")
        if isinstance(geo_data, dict):
            self.main_window.log(f"   Shape Data  : Reach={geo_data.get('finger_depth', 0)/10.0:.1f} cm | Gap={geo_data.get('real_gap', 0)/10.0:.1f} cm")
        self.main_window.log("   Parallel Workflow: Object rotation flattened so the bottom face stays parallel to the floor.")
        
        # Visual Signal: Flash green to confirm surface contact
        orig_color = obj_link.color if hasattr(obj_link, 'color') else "silver"
        self.main_window.canvas.set_actor_color(self.gripped_object, "#4caf50")
        QtCore.QTimer.singleShot(500, lambda: self.main_window.canvas.set_actor_color(self.gripped_object, orig_color))
        
        self.main_window.show_toast(f"Held '{obj_link.name}' between fingers", "success")


    def _prepare_release_targets(self):
        """Calculates targets to open gripper fully."""
        planned_release_gap = getattr(self, "pick_place_plan", {}).get("release_open_gap_world")
        if planned_release_gap is not None:
            self._target_gripper_angles = self.main_window._control_gripper_fingers(
                close=False,
                target_gap_world=float(planned_release_gap),
                apply=False
            )
        else:
            self._target_gripper_angles = self.main_window._control_gripper_fingers(
                close=False, apply=False
            )

    def _finalize_release(self):
        """Drops the object at P2."""
        self._do_release()

    def _move_gripper_smoothly(self):
        """Moves gripper joints toward targets incrementally. Returns True if all reached."""
        if not self._target_gripper_angles:
            return True
            
        all_done = True
        STEP = 2.0 # Degrees per tick
        
        # Only enforce surface contact/rigid blocking during the GRIP state
        enforce_collision = (self.sim_state == "GRIP")
        
        # We use list() because we might delete items from the dict during iteration
        for j_name, target in list(self._target_gripper_angles.items()):
            joint = self.main_window.robot.joints.get(j_name)
            if not joint: continue
            
            # --- Store previous state for reversion if collision occurs ---
            old_val = joint.current_value
            # Store slave states too
            old_slaves = {}
            for s_id, ratio in self.main_window.robot.joint_relations.get(j_name, []):
                if s_id in self.main_window.robot.joints:
                    old_slaves[s_id] = self.main_window.robot.joints[s_id].current_value

            diff = target - joint.current_value
            if abs(diff) < STEP:
                joint.current_value = target
            else:
                joint.current_value += np.sign(diff) * STEP
                all_done = False
                
            # Propagate to slaves
            for s_id, ratio in self.main_window.robot.joint_relations.get(j_name, []):
                if s_id in self.main_window.robot.joints:
                    self.main_window.robot.joints[s_id].current_value = joint.current_value * ratio
            
            # Update kinematics to test the proposed position
            self.main_window.robot.update_kinematics()

            # --- MULTI-PART RIGID COLLISION CHECK ---
            if enforce_collision and self._check_gripper_collision():
                # Revert to the last safe position just before contact
                joint.current_value = old_val
                for s_id, s_val in old_slaves.items():
                    if s_id in self.main_window.robot.joints:
                        self.main_window.robot.joints[s_id].current_value = s_val
                
                # Cleanup: we've reached the surface, so this target is "solved"
                del self._target_gripper_angles[j_name]
                self.main_window.log(f"ðŸ“ Contact: '{joint.name}' stopped at the rigid object surface.")
                self.main_window.robot.update_kinematics()
                continue # Joint is effectively 'reached' at the surface
                    
        self.main_window.robot.update_kinematics()
        # Return True only if no targets are left to solve
        return all_done or not self._target_gripper_angles

    def _check_gripper_collision(self):
        """Monitors contacts between ANY gripper-related link and the simulation object using Trimesh."""
        item = self.objects_list.currentItem()
        if not item: return False
        obj_name = item.text()
        obj_link = self.main_window.robot.links.get(obj_name)
        if not obj_link or not obj_link.mesh: return False
        
        tcp_link = self._get_tcp_link() # The 'Hand'
        if tcp_link is None:
            return False
        
        # Identify 'Fingers' and ALL their recursive children
        # (A gripper isn't just the direct child link; it's the whole sub-assembly)
        finger_assembly = []
        rel_joints = set()
        for j_name, joint in self.main_window.robot.joints.items():
            if getattr(joint, 'is_gripper', False):
                rel_joints.add(j_name)
            
        for j_name in rel_joints:
            joint = self.main_window.robot.joints.get(j_name)
            if joint and joint.child_link:
                # Add the finger and all its downstream geometry
                stack = [joint.child_link]
                while stack:
                    curr = stack.pop()
                    finger_assembly.append(curr)
                    for cj in curr.child_joints:
                        if cj.child_link: stack.append(cj.child_link)
        
        if not finger_assembly: 
            finger_assembly = [tcp_link]
            
        # Create Collision Manager for this tick
        try:
            import trimesh
            cm = trimesh.collision.CollisionManager()
        except ValueError:
            # Fallback if FCL backend is not properly linked or missing
            # In this case, we'll return False (no collision detected) to allow 
            # simulation to proceed without rigid contact, but log a warning.
            if not getattr(self, '_collision_warn_done', False):
                self.main_window.log("âš  Collision Engine: FCL backend not found. Rigid contact will be disabled.")
                self._collision_warn_done = True
            return False

        cm.add_object("SIM_OBJ", obj_link.mesh, obj_link.t_world)
        
        for i, f_link in enumerate(finger_assembly):
            if f_link.mesh:
                try:
                    cm.add_object(f"PART_{i}", f_link.mesh, f_link.t_world)
                except Exception:
                    continue
                
        return cm.in_collision_internal()

    def _gripper_contact_link_names(self):
        """Returns links that belong to the gripper assembly and should be allowed to touch the target object."""
        allowed = set()
        tcp_link = self._get_tcp_link()
        if tcp_link is not None:
            allowed.add(tcp_link.name)

        for joint in self.main_window.robot.joints.values():
            if not getattr(joint, 'is_gripper', False):
                continue

            if joint.parent_link is not None:
                allowed.add(joint.parent_link.name)

            if joint.child_link is None:
                continue

            stack = [joint.child_link]
            while stack:
                link = stack.pop()
                if link is None or link.name in allowed:
                    continue
                allowed.add(link.name)
                for child_joint in link.child_joints:
                    if child_joint.child_link is not None:
                        stack.append(child_joint.child_link)

        return allowed



    def _do_grip(self, tcp_link):
        # Redundant: replaced by _prepare_grip_targets and _finalize_grip
        pass

    def _carry_gripped_object(self, tcp_link):
        """Updates the gripped object's position every tick so it follows the TCP."""
        if not self.gripped_object:
            return
        if self.gripped_object not in self.main_window.robot.links:
            return

        obj_link = self.main_window.robot.links[self.gripped_object]
        world_tcp, _, _ = self.main_window.get_link_tool_point(tcp_link, return_vec=True)

        fixed_rotation = self.grip_fixed_rotation
        local_center = self.grip_local_center
        if fixed_rotation is None or local_center is None:
            fixed_rotation = self._make_world_parallel_rotation(obj_link.t_world[:3, :3])
            local_center = obj_link.mesh.centroid if obj_link.mesh else np.zeros(3)

        # Keep the imported orientation fixed; only translate the object with the TCP.
        t_obj = np.eye(4)
        t_obj[:3, :3] = fixed_rotation
        t_obj[:3, 3] = world_tcp - fixed_rotation @ local_center
        obj_link.t_offset = t_obj
        self.main_window.robot.update_kinematics()
        self.main_window.canvas.update_transforms(self.main_window.robot)
        self.main_window.simulation_tab.refresh_object_info(self.gripped_object)

    def _do_release(self):
        """Opens gripper and drops the gripped object at P2 with its ORIGINAL orientation."""
        # Open fingers
        self.main_window._control_gripper_fingers(close=False)
        self.main_window.robot.update_kinematics()

        if not self.gripped_object:
            return
        if self.gripped_object not in self.main_window.robot.links:
            return

        obj_link = self.main_window.robot.links[self.gripped_object]
        ratio = self.main_window.canvas.grid_units_per_cm

        # Build final transform:
        #   - Translation: P2 coordinates from the spinboxes (canvas units)
        #   - Rotation: the object's ORIGINAL rotation before it was picked up
        t_release = np.eye(4)
        if self.grip_fixed_rotation is not None:
            t_release[:3, :3] = self.grip_fixed_rotation
        elif hasattr(self, 'grip_original_rotation') and self.grip_original_rotation is not None:
            t_release[:3, :3] = self._make_world_parallel_rotation(self.grip_original_rotation)
        else:
            t_release[:3, :3] = self._make_world_parallel_rotation(obj_link.t_world[:3, :3])

        # Place at P2 world position
        # Align mesh BASE with P2 coordinates
        p2_cm = np.array([self.place_x.value(), self.place_y.value(), self.place_z.value()])
        p2_world = p2_cm * ratio
        
        origin_z = p2_world[2]
        if obj_link.mesh:
            # Shift origin so bottom center is at P2
            local_min_z = obj_link.mesh.bounds[0][2]
            origin_z = p2_world[2] - local_min_z

        t_release[:3, 3] = [p2_world[0], p2_world[1], origin_z]
        obj_link.t_offset = t_release
        self.main_window.robot.update_kinematics()
        self.main_window.canvas.update_transforms(self.main_window.robot)

        self.main_window.log(f"ðŸ“¦ RELEASED: '{self.gripped_object}' placed at P2 with original orientation.")
        self.main_window.show_toast(f"Placed {self.gripped_object} at P2", "success")

        self.gripped_object = None
        self.grip_offset = None
        self.grip_original_rotation = None
        self.grip_fixed_rotation = None
        self.grip_local_center = None
        self.grip_anchor_world = None

    def _on_task_completed(self):
        """Show a completion dialog after the robot reaches the configured home position."""
        self.main_window.log("ðŸŽ‰ Task Completed! Robot reached the home position successfully.")
        self.main_window.show_toast("Task Completed!", "success", duration=5000)
        if hasattr(self.main_window, "snap_live_point_to_home"):
            self.main_window.snap_live_point_to_home()

        # --- Build & Show dialog ---
        dlg = QtWidgets.QDialog(self.main_window)
        dlg.setWindowTitle("Task Completed")
        dlg.setFixedSize(360, 180)
        dlg.setStyleSheet("""
            QDialog  { background: #ffffff; }
            QLabel   { font-size: 15px; color: #212121; }
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 30px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)

        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        # Icon + message row
        icon_row = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("ðŸŽ‰")
        icon_lbl.setStyleSheet("font-size: 36px; color: #388e3c;")
        icon_row.addWidget(icon_lbl)

        msg_lbl = QtWidgets.QLabel(
            "<b>Task Completed!</b><br>"
            "<span style='font-size:13px; color:#555;'>"
            "The robot reached the configured <b>HOME</b> position successfully."
            "</span>"
        )
        msg_lbl.setWordWrap(True)
        icon_row.addWidget(msg_lbl, 1)
        layout.addLayout(icon_row)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setCursor(QtCore.Qt.PointingHandCursor)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        dlg.exec_()   # Blocks until user presses OK

        # === Final cleanup ===
        self._finish_return()

    def _return_to_initial_position(self):
        """Smoothly animates joints back to the snapshot taken before simulation started."""
        if not hasattr(self, '_initial_joint_state') or not self._initial_joint_state:
            self.main_window.log("âš ï¸ No initial state snapshot found.")
            self._finish_return()
            return

        self.main_window.log("â†© Returning to initial position...")

        # Reuse the existing motion machinery
        self.target_joint_values = dict(self._initial_joint_state)
        self.joint_chain = self._get_tcp_chain_ordered()

        self._return_timer = QtCore.QTimer(self)
        self._return_timer.timeout.connect(self._on_return_tick)
        self._return_timer.start(50)

    def _get_tcp_chain_ordered(self):
        """Returns joint chain base->TCP (same order used for motion)."""
        tcp_link = self._get_tcp_link()
        if tcp_link is None:
            return list(self.main_window.robot.joints.values())
        chain = self.main_window.robot.get_kinematic_chain(tcp_link)
        return chain  # already base->TCP

    def _on_return_tick(self):
        """Single tick of the return-to-home animation."""
        all_done = True
        for joint in self.joint_chain:
            target  = self.target_joint_values.get(joint.name, joint.current_value)
            diff    = target - joint.current_value
            if abs(diff) < 0.08:
                joint.current_value = target
                self._update_joint_and_slaves(joint, target)
                continue
            all_done = False
            RAMP, MIN_S = 15.0, 0.5
            step_mag = max(MIN_S, self.motion_speed * min(1.0, abs(diff) / RAMP))
            step = step_mag if diff > 0 else -step_mag
            new_val = target if abs(step) > abs(diff) else joint.current_value + step
            joint.current_value = new_val
            self._update_joint_and_slaves(joint, new_val)

        self._sync_all_sliders()
        self.main_window.canvas.update_transforms(self.main_window.robot)
        self.main_window.update_live_ui()

        if all_done:
            self._return_timer.stop()
            self._finish_return()

    def _finish_return(self):
        """Called after the simulation completes and the robot is left at HOME."""
        self.is_sim_active = False
        self.start_btn.setChecked(False)
        self.start_btn.setText("ðŸš€ Start Simulation")
        self.start_btn.setStyleSheet(
            "background-color: #fdd835; color: #212121; "
            "border-radius: 8px; font-weight: bold; font-size: 14px;"
        )
        self.main_window.log("âœ… Task completed. Robot is at the home position.")
        self.main_window.show_toast("Task completed", "success")

    def set_custom_lp(self):
        """Activates object picking mode to set the Live Point (TCP)."""
        self.main_window.log("ðŸŽ¯ Please click an object in the 3D canvas to set as Live Point (TCP).")
        self.main_window.show_toast("Click an object in 3D view", "info")
        self.main_window.canvas.start_object_picking(self._on_custom_lp_picked, label="Live Point")

    def _on_custom_lp_picked(self, name):
        """Callback for when an object is clicked to become the Live Point."""
        if name in self.main_window.robot.links:
            self.main_window.custom_tcp_name = name
            self.main_window.log(f"ðŸŽ¯ Live Point (TCP) manually set to: '{name}' via 3D click.")
            self.main_window.show_toast(f"Live Point set to {name}", "success")
            self.main_window.update_live_ui()
            
            # Select it in the UI list too
            items = self.objects_list.findItems(name, QtCore.Qt.MatchExactly)
            if items:
                self.objects_list.setCurrentItem(items[0])

    def _get_tcp_link(self):
        """
        Identifies the Tool Center Point (TCP) link for the robot.
        Prioritizes user-selected/custom TCP, then gripper hand link, then leaf link.
        """
        robot = self.main_window.robot

        # 1. Explicit user-selected TCP link
        custom_name = getattr(self.main_window, 'custom_tcp_name', None)
        if custom_name and custom_name in robot.links:
            return robot.links[custom_name]

        # 2. Link-local custom TCP markers
        for link in robot.links.values():
            if hasattr(link, 'custom_tcp_offset') and link.custom_tcp_offset is not None:
                return link

        # 3. Prefer the parent link that owns most marked gripper joints (the hand/root).
        hand_counts = {}
        for joint in robot.joints.values():
            if getattr(joint, 'is_gripper', False) and joint.parent_link is not None:
                hand_name = joint.parent_link.name
                hand_counts[hand_name] = hand_counts.get(hand_name, 0) + 1

        if hand_counts:
            best_hand_name = max(
                hand_counts.keys(),
                key=lambda name: (
                    hand_counts[name],
                    len(robot.get_kinematic_chain(robot.links[name])) if name in robot.links else 0,
                ),
            )
            if best_hand_name in robot.links:
                return robot.links[best_hand_name]

        # 4. Relation-based fallback (legacy rigs)
        rel_joints = set()
        for master, slaves in robot.joint_relations.items():
            rel_joints.add(master)
            for s_id, _ in slaves:
                rel_joints.add(s_id)
        
        if rel_joints:
            parent_counts = {}
            for j_name in rel_joints:
                joint = robot.joints.get(j_name)
                if joint:
                    p_name = joint.parent_link.name
                    parent_counts[p_name] = parent_counts.get(p_name, 0) + 1
            
            if parent_counts:
                best_hand_name = max(parent_counts, key=parent_counts.get)
                return robot.links[best_hand_name]

        # 5. Leaf link fallback
        for link in robot.links.values():
            if link.parent_joint and not link.child_joints:
                return link
                
        return next((l for l in robot.links.values() if not l.is_base), None)

    def pick_paint_nozzle_face(self):
        """Start face picking for the nozzle reference used in painting mode."""
        self.main_window.log("🎯 Painting Nozzle Selection: Click the nozzle face in the 3D scene.")
        self.main_window.canvas.start_face_picking(self.on_paint_nozzle_face_picked, color="#ff9800")

    def on_paint_nozzle_face_picked(self, name, center, normal):
        """Store the selected nozzle face for painting reference."""
        self.paint_nozzle_tcp_offset = None
        self.paint_nozzle_pick_data = {
            "name": name,
            "center": np.array(center, dtype=float),
            "normal": np.array(normal, dtype=float),
        }

        if name in self.main_window.robot.links:
            link = self.main_window.robot.links[name]
            try:
                inv = np.linalg.inv(link.t_world)
                self.paint_nozzle_tcp_offset = (inv @ np.append(np.array(center, dtype=float), 1.0))[:3]
            except Exception:
                self.paint_nozzle_tcp_offset = None

        ratio = self.main_window.canvas.grid_units_per_cm
        center_cm = self.paint_nozzle_pick_data["center"] / ratio
        normal = self.paint_nozzle_pick_data["normal"]
        self.paint_nozzle_summary.setText(f"Nozzle face: {name}")
        self.paint_nozzle_detail.setText(
            f"Center: ({center_cm[0]:.2f}, {center_cm[1]:.2f}, {center_cm[2]:.2f}) cm\n"
            f"Normal: ({normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f})"
        )
        self.main_window.log(f"🎯 Painting nozzle face picked on {name}")
        self.main_window.show_toast("Nozzle face selected", "success")

    def clear_paint_nozzle_face(self):
        """Clear the selected nozzle face from painting mode."""
        self.paint_nozzle_pick_data = None
        self.paint_nozzle_tcp_offset = None
        self.paint_nozzle_summary.setText("Nozzle face: —")
        self.paint_nozzle_detail.setText("Center: —")
        self.main_window.log("Painting nozzle face selection cleared.")
        self.main_window.show_toast("Nozzle face cleared", "info")

    def make_paint_area(self):
        """Create a manual paint area from four user-entered 3D points."""
        if len(self.paint_area_point_inputs) != 4:
            self.main_window.show_toast("Area inputs are not ready", "warning")
            return

        ratio = self.main_window.canvas.grid_units_per_cm
        points_world = []
        points_cm = []
        for x_sb, y_sb, z_sb in self.paint_area_point_inputs:
            pt_cm = np.array([x_sb.value(), y_sb.value(), z_sb.value()], dtype=float)
            points_cm.append(pt_cm)
            points_world.append(pt_cm * ratio)

        pts_world = np.array(points_world, dtype=float)
        if len(pts_world) != 4:
            self.main_window.show_toast("Enter exactly 4 points", "warning")
            return

        diag_len = max(
            float(np.linalg.norm(pts_world[2] - pts_world[0])),
            float(np.linalg.norm(pts_world[3] - pts_world[1])),
        )
        area_cm2 = self._quad_area_cm2(points_cm)
        self.paint_area_points_world = [p.copy() for p in pts_world]
        self.paint_path_points = self._build_paint_area_path(pts_world)

        self.paint_area_summary.setText(f"Area: {area_cm2:.2f} cm²")
        self.paint_area_detail.setText(
            "P1: ({:.2f}, {:.2f}, {:.2f}) cm\n"
            "P2: ({:.2f}, {:.2f}, {:.2f}) cm\n"
            "P3: ({:.2f}, {:.2f}, {:.2f}) cm\n"
            "P4: ({:.2f}, {:.2f}, {:.2f}) cm".format(
                *points_cm[0], *points_cm[1], *points_cm[2], *points_cm[3]
            )
        )

        self._render_paint_area_preview(pts_world)
        self._prepare_paint_motion_plan()
        self.main_window.log(
            f"🧩 Paint area created from 4 points; diagonal span is {diag_len / ratio:.2f} cm."
        )
        self.main_window.show_toast("Paint area created", "success")

    def make_paint_path(self):
        """Create the painting path from the current area inputs."""
        self.make_paint_area()

    def _quad_area_cm2(self, points_cm):
        """Approximate the area of a 4-point quad in cm^2."""
        pts = [np.array(p, dtype=float) for p in points_cm]
        if len(pts) != 4:
            return 0.0
        tri1 = 0.5 * np.linalg.norm(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
        tri2 = 0.5 * np.linalg.norm(np.cross(pts[3] - pts[0], pts[2] - pts[0]))
        return float(tri1 + tri2)

    def _build_paint_area_path(self, pts_world):
        """Build a zigzag path across a quadrilateral area."""
        pts = [np.array(p, dtype=float) for p in pts_world]
        if len(pts) != 4:
            return []

        p1, p2, p3, p4 = pts
        edge_a = max(float(np.linalg.norm(p2 - p1)), float(np.linalg.norm(p3 - p4)))
        edge_b = max(float(np.linalg.norm(p4 - p1)), float(np.linalg.norm(p3 - p2)))
        ratio = self.main_window.canvas.grid_units_per_cm
        row_count = max(2, int(np.ceil(edge_b / max(6.0 * ratio, 1e-6))))
        col_count = max(2, int(np.ceil(edge_a / max(6.0 * ratio, 1e-6))))

        path_points = []
        for row_idx, v in enumerate(np.linspace(0.0, 1.0, row_count)):
            left = (1.0 - v) * p1 + v * p4
            right = (1.0 - v) * p2 + v * p3
            cols = np.linspace(0.0, 1.0, col_count)
            if row_idx % 2 == 1:
                cols = cols[::-1]
            for u in cols:
                pt = (1.0 - u) * left + u * right
                if not path_points or np.linalg.norm(pt - path_points[-1]) > 1e-6:
                    path_points.append(pt)
        return path_points

    def _prepare_paint_motion_plan(self):
        """Precompute joint targets for each paint waypoint."""
        if not self.paint_path_points:
            self.paint_area_joint_targets = []
            return

        tcp_link = self.paint_tcp_link
        if tcp_link is None and self.paint_nozzle_pick_data:
            nozzle_name = self.paint_nozzle_pick_data.get("name")
            if nozzle_name and nozzle_name in self.main_window.robot.links:
                tcp_link = self.main_window.robot.links[nozzle_name]
        if tcp_link is None:
            tcp_link = self._get_tcp_link()
        if tcp_link is None:
            self.paint_area_joint_targets = []
            self.main_window.show_toast("No TCP found for paint plan", "warning")
            return

        ratio = self.main_window.canvas.grid_units_per_cm
        if self.paint_nozzle_tcp_offset is not None:
            tool_local = np.array(self.paint_nozzle_tcp_offset, dtype=float)
            tcp_world = (tcp_link.t_world @ np.append(tool_local, 1.0))[:3]
        else:
            tcp_world, tool_local, _ = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        start_vals = {n: j.current_value for n, j in self.main_window.robot.joints.items()}
        planned_targets = []
        warnings = 0

        try:
            for idx, pt in enumerate(self.paint_path_points):
                reached = self.main_window.robot.inverse_kinematics(
                    np.array(pt, dtype=float),
                    tcp_link,
                    max_iters=220,
                    tolerance=0.5 * ratio,
                    tool_offset=tool_local,
                )
                planned_targets.append({
                    n: j.current_value for n, j in self.main_window.robot.joints.items()
                })
                if not reached:
                    warnings += 1

            self.paint_area_joint_targets = planned_targets
            self.paint_joint_chain = self.main_window.robot.get_kinematic_chain(tcp_link)
            self.paint_tcp_link = tcp_link
            self.main_window.log(
                f"🧠 Precomputed paint joint plan for {len(planned_targets)} waypoints "
                f"({warnings} best-effort solves)."
            )
            if planned_targets:
                self.main_window.log("🎨 Paint preview is now linked to robot joint motion.")
        finally:
            for n, val in start_vals.items():
                self.main_window.robot.joints[n].current_value = val
            self.main_window.robot.update_kinematics()
            self.main_window.canvas.plotter.render()

    def _render_paint_area_preview(self, pts_world):
        """Render the manual paint area and its zigzag traversal in the 3D view."""
        import pyvista as pv

        canvas = self.main_window.canvas
        self._clear_paint_area_preview()

        quad = pv.PolyData(np.array(pts_world, dtype=float))
        quad.faces = np.array([4, 0, 1, 2, 3], dtype=np.int64)
        canvas.plotter.add_mesh(
            quad,
            color="#ce93d8",
            opacity=0.28,
            show_edges=True,
            edge_color="#7b1fa2",
            line_width=3,
            name="robot_paint_area",
            pickable=False,
        )

        outline_pts = np.vstack([np.array(pts_world, dtype=float), np.array(pts_world[0], dtype=float)])
        outline = pv.lines_from_points(outline_pts)
        canvas.plotter.add_mesh(
            outline,
            color="#ffb300",
            line_width=4,
            name="robot_paint_area_outline",
            pickable=False,
        )

        if len(self.paint_path_points) > 1:
            path = pv.lines_from_points(np.array(self.paint_path_points, dtype=float))
            canvas.plotter.add_mesh(
                path,
                color="#fbc02d",
                line_width=4,
                name="robot_paint_area_path",
                pickable=False,
            )
        canvas.plotter.render()

    def _clear_paint_area_preview(self):
        """Remove the manual area preview from the scene."""
        canvas = self.main_window.canvas
        for actor_name in [
            "robot_paint_square",
            "robot_paint_square_raster",
            "robot_paint_area",
            "robot_paint_area_outline",
            "robot_paint_area_path",
        ]:
            try:
                canvas.plotter.remove_actor(actor_name)
            except Exception:
                pass
        try:
            canvas.plotter.render()
        except Exception:
            pass

    def start_painting(self):
        """Start painting preview mode by computing and showing the square."""
        if not self.paint_path_points:
            self._paint_compute_square()
            if not self.paint_path_points:
                return

        if self.paint_tcp_link is None and getattr(self, "paint_square_state", None):
            nozzle_name = self.paint_square_state.get("nozzle_name")
            if nozzle_name and nozzle_name in self.main_window.robot.links:
                self.paint_tcp_link = self.main_window.robot.links[nozzle_name]

        self.painting_active = True
        self.paint_motion_state = "SOLVE_POINT"
        self.paint_current_point_idx = 0
        self.paint_target_joint_values = {}
        self.paint_joint_chain = []
        self.paint_live_trail_points = []
        self._clear_paint_live_trail()
        self.main_window.log("Painting preview started.")
        self.main_window.show_toast("Painting started", "success")
        self.paint_timer.start(50)

    def stop_painting(self):
        """Stop painting preview mode and clear the preview from the 3D scene."""
        self.painting_active = False
        self.paint_timer.stop()
        self.paint_motion_state = "IDLE"
        self.paint_current_point_idx = 0
        self.paint_target_joint_values = {}
        self.paint_joint_chain = []
        self._clear_paint_area_preview()
        self._clear_paint_live_trail()
        self.main_window.log("Painting preview stopped.")
        self.main_window.show_toast("Painting stopped", "info")

    def _record_paint_live_trail(self, tcp_link):
        """Store a running paint trail so the nozzle path is visible in 3D."""
        if tcp_link is None:
            return

        world_pt, _, _ = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        if world_pt is None:
            return

        pt = np.array(world_pt, dtype=float).reshape(-1)
        if pt.size < 3:
            return
        pt = pt[:3]

        if not hasattr(self, "paint_live_trail_points") or self.paint_live_trail_points is None:
            self.paint_live_trail_points = []

        if self.paint_live_trail_points:
            if np.linalg.norm(pt - self.paint_live_trail_points[-1]) < 1e-6:
                return

        self.paint_live_trail_points.append(pt)
        # Sphere marker removed - only the trail line is visualized
        self._update_paint_live_trail_visual(render=False)

    def _update_paint_live_trail_visual(self, render=True):
        """Draw the paint live-point trail in the 3D graph."""
        try:
            import pyvista as pv
        except Exception:
            return

        canvas = self.main_window.canvas
        actor_name = getattr(self, "paint_live_trail_actor_name", "paint_live_trail")

        try:
            canvas.plotter.remove_actor(actor_name)
        except Exception:
            pass

        if not hasattr(self, "paint_live_trail_points") or len(self.paint_live_trail_points) < 2:
            if render:
                canvas.plotter.render()
            return

        trail = pv.lines_from_points(np.array(self.paint_live_trail_points, dtype=float))
        canvas.plotter.add_mesh(
            trail,
            color="#fbc02d",
            line_width=4,
            name=actor_name,
            pickable=False,
        )
        if render:
            canvas.plotter.render()

    def _clear_paint_live_trail(self):
        """Remove paint live-point visuals from the scene."""
        if not hasattr(self, "main_window") or not hasattr(self.main_window, "canvas"):
            return
        try:
            self.main_window.canvas.plotter.remove_actor(getattr(self, "paint_live_trail_actor_name", "paint_live_trail"))
        except Exception:
            pass
        try:
            if hasattr(self.main_window.canvas, "clear_live_point_marker"):
                self.main_window.canvas.clear_live_point_marker(name="paint_live_point")
        except Exception:
            pass
        try:
            self.main_window.canvas.plotter.render()
        except Exception:
            pass

    def _clear_paint_square_preview(self):
        """Remove the paint square preview from the scene."""
        canvas = self.main_window.canvas
        try:
            canvas.plotter.remove_actor("robot_paint_square")
            canvas.plotter.remove_actor("robot_paint_square_raster")
        except Exception:
            pass
        canvas.plotter.render()

    def _safe_on_paint_tick(self):
        """Advance the painting motion while keeping runtime errors contained."""
        try:
            self._on_paint_tick()
        except Exception:
            self.paint_timer.stop()
            self.painting_active = False
            self.paint_motion_state = "IDLE"
            self.main_window.log(traceback.format_exc())
            self.main_window.show_toast("Painting stopped due to an error", "error")

    def _on_paint_tick(self):
        """Drive the robot through the computed zigzag paint path."""
        if not self.painting_active or not self.paint_path_points:
            return

        if self.paint_current_point_idx >= len(self.paint_path_points):
            self.paint_timer.stop()
            self.painting_active = False
            self.paint_motion_state = "IDLE"
            self.main_window.log("Painting path complete.")
            self.main_window.show_toast("Painting complete", "success")
            return

        tcp_link = self.paint_tcp_link or self._get_tcp_link()
        if tcp_link is None:
            self.paint_timer.stop()
            self.painting_active = False
            self.paint_motion_state = "IDLE"
            self.main_window.show_toast("No TCP found", "warning")
            return

        target_world = np.array(self.paint_path_points[self.paint_current_point_idx], dtype=float)
        ratio = self.main_window.canvas.grid_units_per_cm

        if self.paint_motion_state == "SOLVE_POINT" or not self.paint_target_joint_values:
            if self.paint_area_joint_targets and self.paint_current_point_idx < len(self.paint_area_joint_targets):
                self.paint_target_joint_values = self.paint_area_joint_targets[self.paint_current_point_idx]
                self.paint_joint_chain = self.main_window.robot.get_kinematic_chain(tcp_link)
                self.paint_tcp_link = tcp_link
                self.paint_motion_state = "MOVE_POINT"
                self.main_window.log(
                    f"🎨 Painting waypoint {self.paint_current_point_idx + 1}/{len(self.paint_path_points)} "
                    f"using precomputed joint targets at ({target_world[0]/ratio:.2f}, {target_world[1]/ratio:.2f}, {target_world[2]/ratio:.2f}) cm"
                )
                return

            if self.paint_nozzle_tcp_offset is not None:
                tool_local = np.array(self.paint_nozzle_tcp_offset, dtype=float)
            else:
                _, tool_local, _ = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
            start_vals = {n: j.current_value for n, j in self.main_window.robot.joints.items()}
            reached = self.main_window.robot.inverse_kinematics(
                target_world,
                tcp_link,
                max_iters=300,
                tolerance=0.5 * ratio,
                tool_offset=tool_local,
            )
            self.paint_target_joint_values = {
                n: j.current_value for n, j in self.main_window.robot.joints.items()
            }
            self.paint_joint_chain = self.main_window.robot.get_kinematic_chain(tcp_link)
            self.paint_tcp_link = tcp_link

            for n, val in start_vals.items():
                self.main_window.robot.joints[n].current_value = val
            self.main_window.robot.update_kinematics()

            if not reached:
                self.main_window.log(
                    f"⚠️ Paint waypoint {self.paint_current_point_idx + 1}/{len(self.paint_path_points)} "
                    "is only partially reachable; continuing best effort."
                )
            self.paint_motion_state = "MOVE_POINT"
            self.main_window.log(
                f"🎨 Painting waypoint {self.paint_current_point_idx + 1}/{len(self.paint_path_points)} "
                f"targeted at ({target_world[0]/ratio:.2f}, {target_world[1]/ratio:.2f}, {target_world[2]/ratio:.2f}) cm"
            )
            return

        if self.paint_motion_state == "MOVE_POINT":
            self.joint_chain = self.paint_joint_chain
            self.target_joint_values = self.paint_target_joint_values
            done = self._handle_sequential_motion()
            self.main_window.robot.update_kinematics()
            self.main_window.canvas.update_transforms(self.main_window.robot)
            self.main_window.update_live_ui()
            self._record_paint_live_trail(tcp_link)
            try:
                self.main_window.canvas.plotter.render()
            except Exception:
                pass

            if done:
                self.main_window.log(
                    f"✅ Paint waypoint reached: {self.paint_current_point_idx + 1}/{len(self.paint_path_points)}"
                )
                self.paint_current_point_idx += 1
                self.paint_target_joint_values = {}
                self.paint_joint_chain = []
                self.paint_motion_state = "SOLVE_POINT"
                if self.paint_current_point_idx >= len(self.paint_path_points):
                    self.paint_timer.stop()
                    self.painting_active = False
                    self.paint_motion_state = "IDLE"
                    self.main_window.log("Painting path complete.")
                    self.main_window.show_toast("Painting complete", "success")

    def _paint_compute_square(self):
        """Compute and preview a square based on the current joint chain and Live Point."""
        nozzle_data = self.paint_nozzle_pick_data
        if not nozzle_data:
            self.paint_square_summary.setText("Square size: unavailable")
            self.paint_square_detail.setText("Select the nozzle face first.")
            self.main_window.show_toast("Select the nozzle face first", "warning")
            return

        ratio = self.main_window.canvas.grid_units_per_cm
        robot = self.main_window.robot
        nozzle_center = np.array(nozzle_data["center"], dtype=float)

        tcp_link = self._get_tcp_link()
        if tcp_link is None:
            self.paint_square_summary.setText("Square size: unavailable")
            self.paint_square_detail.setText("No TCP link found.")
            self.main_window.show_toast("No TCP found", "warning")
            return

        tcp_world, _, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        work_frame = self._compute_paint_work_frame(nozzle_center, tcp_link)
        if work_frame is None:
            self.main_window.show_toast("Unable to derive paint plane from robot joints", "warning")
            return
        plane_center, plane_x, plane_y, plane_normal = work_frame

        chain = robot.get_kinematic_chain(tcp_link) if hasattr(robot, "get_kinematic_chain") else []
        sample_points = [np.array(tcp_world, dtype=float)]
        for joint in chain:
            parent_link = getattr(joint, "parent_link", None)
            child_link = getattr(joint, "child_link", None)
            if parent_link is not None:
                sample_points.append(np.array(parent_link.t_world[:3, 3], dtype=float))
            if child_link is not None:
                sample_points.append(np.array(child_link.t_world[:3, 3], dtype=float))

        sample_xy = np.array([p[:2] for p in sample_points], dtype=float)
        span_x = float(np.ptp(sample_xy[:, 0])) if len(sample_xy) else 0.0
        span_y = float(np.ptp(sample_xy[:, 1])) if len(sample_xy) else 0.0
        chain_span_world = max(span_x, span_y)

        tcp_to_samples = max((float(np.linalg.norm(p - tcp_world)) for p in sample_points), default=0.0)
        joint_count_factor = max(1, len(chain)) * 2.0 * ratio
        square_side_world = max(
            8.0 * ratio,
            chain_span_world * 1.35,
            tcp_to_samples * 1.1,
            joint_count_factor,
        )

        side_cm = square_side_world / ratio
        tcp_cm = nozzle_center / ratio
        joint_names = ", ".join(j.name for j in chain) if chain else "no joints"

        self.paint_square_summary.setText(f"Square size: {side_cm:.2f} cm x {side_cm:.2f} cm")
        detail_text = (
            f"Center: ({tcp_cm[0]:.2f}, {tcp_cm[1]:.2f}, {tcp_cm[2]:.2f}) cm\n"
            f"Joint chain: {joint_names}"
        )
        if self.paint_nozzle_pick_data:
            nozzle_name = self.paint_nozzle_pick_data.get("name", "unknown")
            detail_text += f"\nNozzle: {nozzle_name}"
        self.paint_square_detail.setText(detail_text)

        try:
            offset_cm = np.array([0.0, 0.0, 0.0], dtype=float)
            nozzle_link = robot.links.get(self.paint_nozzle_pick_data.get("name"))
            self.paint_tcp_link = nozzle_link if nozzle_link is not None else self._get_tcp_link()
            self.paint_square_state = {
                "nozzle_name": self.paint_nozzle_pick_data.get("name"),
                "nozzle_center_world": nozzle_center.tolist(),
                "work_plane_center_world": plane_center.tolist(),
                "work_plane_x_world": plane_x.tolist(),
                "work_plane_y_world": plane_y.tolist(),
                "work_plane_normal_world": plane_normal.tolist(),
                "square_side_world": float(square_side_world),
                "offset_cm": offset_cm.tolist(),
            }
            self.paint_path_points = self._render_paint_square_preview(
                plane_center,
                plane_x,
                plane_y,
                plane_normal,
                square_side_world,
                offset_world=offset_cm * ratio,
            )
        except Exception as exc:
            self.main_window.log(f"⚠️ Square preview could not be drawn: {exc}")

        if isinstance(geo_data, dict) and geo_data.get("using_selected_gripping_surfaces"):
            mode_text = "selected gripping surfaces"
        elif getattr(tcp_link, "custom_tcp_offset", None) is not None:
            mode_text = "custom TCP offset"
        else:
            mode_text = "TCP fallback"

        self.main_window.log(
            f"🟪 Painting square computed from {len(chain)} joints and {mode_text}: "
            f"{side_cm:.2f} cm square, derived from robot joint geometry."
        )
        self.main_window.show_toast("Painting square computed", "success")

    def _compute_paint_work_frame(self, nozzle_center, tcp_link):
        """Derive a paint plane from the robot's joint and link geometry."""
        robot = self.main_window.robot
        points = [np.array(nozzle_center, dtype=float)]

        if tcp_link is not None:
            chain = robot.get_kinematic_chain(tcp_link) if hasattr(robot, "get_kinematic_chain") else []
            for joint in chain:
                parent_link = getattr(joint, "parent_link", None)
                child_link = getattr(joint, "child_link", None)
                if parent_link is not None:
                    points.append(np.array(parent_link.t_world[:3, 3], dtype=float))
                if child_link is not None:
                    points.append(np.array(child_link.t_world[:3, 3], dtype=float))

        for link in robot.links.values():
            if hasattr(link, "t_world"):
                points.append(np.array(link.t_world[:3, 3], dtype=float))

        pts = np.array(points, dtype=float)
        if len(pts) < 3:
            return None

        centered = pts - np.mean(pts, axis=0)
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
        except Exception:
            return None

        if vh.shape[0] < 3:
            return None

        plane_x = vh[0]
        plane_y = vh[1]
        plane_normal = vh[2]

        def _norm(v):
            n = np.linalg.norm(v)
            return v / n if n > 1e-9 else None

        plane_x = _norm(plane_x)
        plane_y = _norm(plane_y)
        plane_normal = _norm(plane_normal)
        if plane_x is None or plane_y is None or plane_normal is None:
            return None

        if np.dot(plane_normal, nozzle_center - np.mean(pts, axis=0)) < 0:
            plane_normal = -plane_normal
            plane_y = -plane_y

        plane_center = np.array(nozzle_center, dtype=float) + plane_normal * (0.25 * np.linalg.norm(np.ptp(pts, axis=0)))
        return plane_center, plane_x, plane_y, plane_normal

    def _render_paint_square_preview(self, center_world, axis_x, axis_y, normal_world, square_side_world, offset_world=None):
        """Render the zigzag paint path in the 3D view."""
        import pyvista as pv

        canvas = self.main_window.canvas
        try:
            canvas.plotter.remove_actor("robot_paint_square")
            canvas.plotter.remove_actor("robot_paint_square_raster")
        except Exception:
            pass

        tangent_x = np.array(axis_x, dtype=float)
        tangent_y = np.array(axis_y, dtype=float)
        normal = np.array(normal_world, dtype=float)
        tangent_x /= np.linalg.norm(tangent_x) + 1e-9
        tangent_y /= np.linalg.norm(tangent_y) + 1e-9
        normal /= np.linalg.norm(normal) + 1e-9

        if offset_world is not None:
            center_world = center_world + np.array(offset_world, dtype=float)

        half = square_side_world / 2.0
        square_plane = pv.Plane(
            center=center_world,
            direction=tuple(normal.tolist()),
            i_size=square_side_world,
            j_size=square_side_world,
            i_resolution=1,
            j_resolution=1,
        )
        canvas.plotter.add_mesh(
            square_plane,
            color="#ce93d8",
            opacity=0.28,
            show_edges=True,
            edge_color="#7b1fa2",
            line_width=3,
            name="robot_paint_square",
            pickable=False,
        )

        raster_spacing_world = max(square_side_world / 8.0, 6.0 * self.main_window.canvas.grid_units_per_cm)
        raster_rows = max(2, int(np.ceil(square_side_world / raster_spacing_world)))
        row_step = square_side_world / raster_rows
        path_points = []
        direction = 1
        y = -half
        while y <= half + 1e-9:
            x0, x1 = (-half, half) if direction > 0 else (half, -half)
            row_pts = [
                np.array([x0, y, 0.0], dtype=float),
                np.array([x1, y, 0.0], dtype=float),
            ]
            for pt in row_pts:
                world_pt = center_world + tangent_x * pt[0] + tangent_y * pt[1]
                if not path_points or np.linalg.norm(world_pt - path_points[-1]) > 1e-6:
                    path_points.append(world_pt)
            y += row_step
            direction *= -1

        if len(path_points) > 1:
            raster = pv.lines_from_points(np.array(path_points))
            canvas.plotter.add_mesh(
                raster,
                color="#fbc02d",
                line_width=4,
                name="robot_paint_square_raster",
                pickable=False,
            )
        canvas.plotter.render()
        return path_points

    def _apply_weld_path_move(self):
        """Place the selected simulation object so its bottom face matches the entered world coordinates."""
        link_name = self._get_selected_move_object_name()
        if not link_name:
            self.main_window.show_toast("Select an object first", "warning")
            return

        link = self.main_window.robot.links.get(link_name)
        if not link or link.mesh is None:
            self.main_window.show_toast("Selected object is unavailable", "warning")
            return

        if link.is_base or link.parent_joint:
            self.main_window.show_toast("Selected object is locked", "warning")
            return

        target_cm = np.array([
            self.weld_move_x_sb.value(),
            self.weld_move_y_sb.value(),
            self.weld_move_z_sb.value(),
        ], dtype=float)
        target_world = target_cm * self.main_window.canvas.grid_units_per_cm

        self.main_window.robot.update_kinematics()
        bottom_local = self._get_mesh_bottom_center_local(link)
        rotation = np.array(link.t_world[:3, :3], dtype=float)

        t_new = np.eye(4, dtype=float)
        t_new[:3, :3] = rotation
        t_new[:3, 3] = target_world - rotation @ bottom_local
        link.t_offset = t_new

        self.main_window.robot.update_kinematics()
        self.main_window.canvas.update_transforms(self.main_window.robot)
        self.main_window.canvas.plotter.render()

        self.main_window.log(
            f"↔ Moved '{link_name}' so its bottom face is at ({target_cm[0]:.2f}, {target_cm[1]:.2f}, {target_cm[2]:.2f}) cm."
        )
        self.main_window.show_toast("Object moved", "success")

    def _get_selected_move_object_name(self):
        """Return the selected simulation object name for move operations."""
        current_item = self.main_window.sim_objects_list.currentItem() if hasattr(self.main_window, "sim_objects_list") else None
        if current_item:
            return current_item.text()

        current_item = self.weld_edges_list.currentItem()
        if current_item:
            text = current_item.text()
            if ". " in text:
                text = text.split(". ", 1)[1]
            if " | " in text:
                return text.split(" | ", 1)[0].strip()

        if self.weld_edge_records:
            return self.weld_edge_records[0].get("link")
        return None

    def _get_mesh_bottom_center_local(self, link):
        """Return the bottom-center of a mesh in the link's local coordinates."""
        if link.mesh is None:
            return np.zeros(3, dtype=float)
        bounds = link.mesh.bounds
        return np.array([
            float((bounds[0][0] + bounds[1][0]) / 2.0),
            float((bounds[0][1] + bounds[1][1]) / 2.0),
            float(bounds[0][2]),
        ], dtype=float)

    def _handle_state_solve(self, target_name, tcp_link, next_state, z_offset_cm=0.0):
        ratio = self.main_window.canvas.grid_units_per_cm  # canvas units per cm

        # Target in canvas units (raw world space)
        if target_name == "P1":
            target_cm = np.array([self.pick_x.value(), self.pick_y.value(), self.pick_z.value()])
        elif target_name == "HOME":
            target_cm = np.array([self.home_x.value(), self.home_y.value(), self.home_z.value()])
        else:
            target_cm = np.array([self.place_x.value(), self.place_y.value(), self.place_z.value()])

        # Apply industry Z offset (approach/lift/retract)
        target_cm[2] += z_offset_cm
        
        target_world = target_cm * ratio  # Convert cm â†’ canvas units

        world_tcp, tool_local, geo_data = self.main_window.get_link_tool_point(tcp_link, return_vec=True)

        is_home_target = target_name == "HOME"
        final_z_offset = 0.0

        if not is_home_target:
            # ADJUST TARGET FOR OBJECT BOTTOM-CENTER:
            # P1/P2 are locations for the object's BASE.
            # The robot's TCP targets the object's CENTER by default.
            grip_width, base_z_offset, _ = self._get_object_grip_width()

            final_z_offset = base_z_offset

            target_world[2] += final_z_offset

            if final_z_offset > 0:
                self.main_window.log(
                    f"ðŸ§  Grasp Target: Using object center-height at Z={target_world[2]/ratio:.1f} cm (P1/P2 are bottom-center refs)."
                )
            else:
                self.main_window.log(f"ðŸ§  Balancing Analysis: Targeting object base for direct surface placement.")

        # Current TCP position for reference logging
        _, tool_local, gap = self.main_window.get_link_tool_point(tcp_link)
        self.main_window.robot.update_kinematics()
        tcp_now_world = (tcp_link.t_world @ np.append(tool_local, 1.0))[:3]
        tcp_now_cm = tcp_now_world / ratio

        self.main_window.log(
            f"ðŸ“ [{target_name}] Target: ({target_cm[0]:.1f}, {target_cm[1]:.1f}, {target_cm[2]:.1f}) cm  |  "
            f"TCP Position: ({tcp_now_cm[0]:.1f}, {tcp_now_cm[1]:.1f}, {tcp_now_cm[2]:.1f}) cm"
        )

        # Snapshot current joint state so we can revert after planning
        start_vals = {n: j.current_value for n, j in self.main_window.robot.joints.items()}

        # Tolerance: 0.5 cm expressed in canvas units
        tolerance_world = 0.5 * ratio

        # Solve IK â€” target and TCP both in canvas world units
        reached = self.main_window.robot.inverse_kinematics(
            target_world, tcp_link,
            max_iters=300,
            tolerance=tolerance_world,
            tool_offset=tool_local
        )

        if gap:
            self.main_window.log(
                f"ðŸ¤ Gripper gap: {gap/ratio:.1f} cm â€” IK aligns to midpoint of fingers."
            )

        if not reached:
            self.main_window.log(f"âš  Warning: {target_name} might be outside workspace! (best effort)")
            self.main_window.show_toast(f"{target_name} partially reachable", "warning")
        else:
            self.main_window.log(f"âœ… IK Solved for {target_name} successfully.")

        # Capture solved joint angles as targets
        self.target_joint_values = {
            n: j.current_value for n, j in self.main_window.robot.joints.items()
        }
        self.joint_chain = self.main_window.robot.get_kinematic_chain(tcp_link)  # base â†’ TCP

        # Revert robot to start state â€” actual movement happens in MOVE state
        for n, val in start_vals.items():
            self.main_window.robot.joints[n].current_value = val
        self.main_window.robot.update_kinematics()

        # --- NEW: ORIENTATION-AWARE GRIP INTELLIGENCE ---
        # Analyze the object's narrowest vs widest dimensions to align the gripper span.
        # We look for the object's 'principal orientations' in world space.
        target_world_rot = None
        _, _, obj_link = self._get_object_grip_width()
        if obj_link and obj_link.mesh:
            verts_w = (obj_link.t_world[:3, :3] @ obj_link.mesh.vertices.T).T + obj_link.t_world[:3, 3]
            # Use PCA (via SVD) on vertices to find major axes
            centroid = np.mean(verts_w, axis=0)
            centered = verts_w - centroid
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            # vh[0] is major, vh[1] is secondary, vh[2] is minor (narrowest)
            major_axis = vh[0]
            minor_axis = vh[2] 
            
            # We want to align the gripper span (best_vec) with the object's narrowest axis
            # to achieve the most centered/stable grip.
            self.main_window.log(f"ðŸ§  Orientation Analysis: Found narrowest axis for '{obj_link.name}'. Aligning gripper span...")
            
            # Propose a rotation that aligns span axis [1,0,0] with minor_axis
            # and approach axis [0,0,1] with -Z (downward).
            # This requires a more complex IK solver, but for now we'll log the recommendation.
            # In a future update, we can solve for target orientation matrix.

        self.sim_state = next_state
        self.main_window.log(f"ðŸ§  Motion Plan for {target_name} (reached={reached}):")
        for i, joint in enumerate(self.joint_chain):
            deg = self.target_joint_values.get(joint.name, 0)
            self.main_window.log(f"   [{i+1}] {joint.name} â†’ {deg:.2f}Â°")
        
        # --- NEW: PERFECT GRIP FEEDBACK ---
        # Get actual finger count and shape data from the tool analysis
        _, _, geo_report = self.main_window.get_link_tool_point(tcp_link, return_vec=True)
        
        finger_count = 0
        if not is_home_target and isinstance(geo_report, dict):
            finger_count = len(geo_report.get('fingers_world', []))
            self.main_window.log(f"ðŸ¤ Gripper Configuration: {finger_count} relationed components detected.")
            self.main_window.log(f"   Shape Data  : Reach={geo_report.get('finger_depth', 0)/ratio:.1f} cm | Gap={geo_report.get('real_gap', 0)/ratio:.1f} cm")
            self.main_window.log(f"   Grip Strategy: Centroid-averaging midpoint TCP.")
        elif not is_home_target:
            self.main_window.log(f"ðŸ¤ Gripper Configuration: Standard leaf gripper detected.")

    def _handle_sequential_motion(self):
        """
        Moves joints simultaneously toward their target angles.
        Uses a smooth trapezoidal speed profile:
          - Accelerates when far from target (large diff)
          - Decelerates within the last few degrees (smooth arrival, no snap)
          - Snaps to exact target angle when within a tiny dead-zone
        Returns True when ALL joints have reached their targets.
        """
        all_done = True

        for joint in self.joint_chain:
            target  = self.target_joint_values.get(joint.name, joint.current_value)
            current = joint.current_value
            diff    = target - current

            # 1. Dead-zone snap
            if abs(diff) < 0.08:
                if joint.current_value != target:
                    old_snap_val = joint.current_value
                    joint.current_value = target
                    self._update_joint_and_slaves(joint, target)
                    
                    # RIGID BLOCKING: revert if snap causes collision
                    if self._check_global_collision():
                        joint.current_value = old_snap_val
                        self._update_joint_and_slaves(joint, old_snap_val)
                        all_done = False
                    continue
                continue

            all_done = False

            # --- Trapezoidal speed profile ---
            RAMP_DIST  = 15.0   
            MIN_SPEED  = 0.5    
            if abs(diff) >= RAMP_DIST:
                step_mag = self.motion_speed
            else:
                step_mag = max(MIN_SPEED, self.motion_speed * (abs(diff) / RAMP_DIST))

            step = step_mag if diff > 0 else -step_mag

            if abs(step) > abs(diff):
                new_val = target
            else:
                new_val = np.clip(current + step, joint.min_limit, joint.max_limit)

            # 2. PROPOSE MOVEMENT
            old_move_val = joint.current_value
            joint.current_value = new_val
            self._update_joint_and_slaves(joint, new_val)
            
            # RIGID BLOCKING: If we hit a simulation object, REVERT.
            if self._check_global_collision():
                joint.current_value = old_move_val
                self._update_joint_and_slaves(joint, old_move_val)
                # Note: we don't return True here; other joints might still be able to move
                # unless they are downstream in the chain.


        return all_done

    def _check_global_collision(self):
        """Checks if any robot part intersections with any independent simulation object mesh."""
        # 1. Gather independent simulation objects (exclude the one we are carrying)
        sim_objs = [l for l in self.main_window.robot.links.values() 
                    if getattr(l, 'is_sim_obj', False) and l.name != self.gripped_object]
        if not sim_objs: return False
        
        # 2. Gather robot links
        robot_links = [l for l in self.main_window.robot.links.values() 
                       if not getattr(l, 'is_sim_obj', False)]
        gripper_contact_links = self._gripper_contact_link_names()
        
        # 3. Setup collision manager for sim objects (Environment Cache)
        # We REBUILD only if the count or objects changed (simple heuristic)
        if self._env_collision_manager is None:
            import trimesh
            self._env_collision_manager = trimesh.collision.CollisionManager()
            for i, obj in enumerate(sim_objs):
                if obj.mesh:
                    self._env_collision_manager.add_object(f"EXTERNAL_{i}", obj.mesh, obj.t_world)
                
        # 4. Check each robot link against the environment
        for link in robot_links:
            if link.mesh and link.name not in gripper_contact_links:
                # We only care about robot <-> environment collisions here
                if self._env_collision_manager.in_collision_single(link.mesh, link.t_world):
                    self.main_window.log(f"ðŸ’¥ Collision: Robot link '{link.name}' hit a rigid environment object.")
                    return True
                    
        # 5. Check the gripped object (if any) against the environment
        if self.gripped_object:
            gripped_link = self.main_window.robot.links.get(self.gripped_object)
            if gripped_link and gripped_link.mesh:
                if self._env_collision_manager.in_collision_single(gripped_link.mesh, gripped_link.t_world):
                    self.main_window.log(f"ðŸ’¥ Collision: Gripped object '{self.gripped_object}' hit another rigid object.")
                    return True

        return False


    def _update_joint_and_slaves(self, joint, val):
        """Propagates a joint value to all slave joints and refreshes kinematics."""
        if joint.name in self.main_window.robot.joint_relations:
            for slave_id, ratio in self.main_window.robot.joint_relations[joint.name]:
                slave_joint = self.main_window.robot.joints.get(slave_id)
                if slave_joint:
                    slave_joint.current_value = np.clip(
                        val * ratio,
                        slave_joint.min_limit,
                        slave_joint.max_limit
                    )
        self.main_window.robot.update_kinematics()

    def _sync_all_sliders(self):
        for name, data in self.sliders.items():
            joint = data['joint']
            val = joint.current_value
            data['slider'].blockSignals(True)
            data['slider'].setValue(int(val))
            data['slider'].blockSignals(False)
            data['spinbox'].blockSignals(True)
            data['spinbox'].setValue(float(val))
            data['spinbox'].blockSignals(False)

    def _on_sim_tick_old(self):
        # [Legacy method content replaced by state machine]
        pass

    def create_tab_button(self, text, icon_path):
        btn = QtWidgets.QPushButton(text)
        btn.setIcon(QtGui.QIcon(icon_path))
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
        
        all_btns = [self.joints_btn, self.matrices_btn, self.objects_btn, self.welding_btn, self.painting_btn]
        for i, btn in enumerate(all_btns):
            btn.setStyleSheet(active_style if i == index else inactive_style)
        
        # Refresh data for the selected view
        if index == 1:
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
            val_spin.setSuffix("Â°")
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

    def update_motion_speed(self, val):
        self.motion_speed = val

