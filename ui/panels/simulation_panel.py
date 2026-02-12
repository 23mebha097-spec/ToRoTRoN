from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np

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
        
        self.joints_btn.clicked.connect(lambda: self.switch_view(0))
        self.matrices_btn.clicked.connect(lambda: self.switch_view(1))
        
        tab_layout.addWidget(self.joints_btn)
        tab_layout.addWidget(self.matrices_btn)
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
        
        # Initial State
        self.switch_view(0)

    def create_tab_button(self, text, icon_path):
        btn = QtWidgets.QPushButton(text)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setIconSize(QtCore.QSize(24, 24))
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                font-weight: bold;
                border: 1px solid #bbb;
                border-radius: 4px;
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
                color: white;
                font-weight: bold;
                border: 1px solid #0d47a1;
                border-radius: 4px;
                padding: 5px;
                text-align: left;
                padding-left: 15px;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #f5f5f5;
                color: #212121;
                font-weight: bold;
                border: 1px solid #bbb;
                border-radius: 4px;
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
            val_label = QtWidgets.QLabel(f"{joint.current_value:.1f}°")
            val_label.setFixedWidth(50)
            val_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setMinimum(int(joint.min_limit))
            slider.setMaximum(int(joint.max_limit))
            slider.setValue(int(joint.current_value))
            
            slider_layout.addWidget(slider)
            slider_layout.addWidget(val_label)
            
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
                'label': val_label,
                'joint': joint
            }
            
            slider.valueChanged.connect(lambda val, n=name: self.on_slider_change(n, val))

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
            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            
            header = QtWidgets.QLabel(f"Matrix: {name}")
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
        lines = []
        for row in matrix:
            line = "  ".join([f"{val:6.2f}" for val in row])
            lines.append(f"[ {line} ]")
        return "\n".join(lines)

    def on_slider_change(self, name, value):
        if name in self.sliders:
            data = self.sliders[name]
            joint = data['joint']
            
            # Update Joint Model
            joint.current_value = float(value)
            
            # Update Label
            data['label'].setText(f"{value:.1f}°")
            
            # Update Robot Kinematics
            self.main_window.robot.update_kinematics()
            
            # Update Graphics
            self.main_window.canvas.update_transforms(self.main_window.robot)
            self.main_window.canvas.plotter.render()
            
            # Update Matrices if visible
            if self.stack.currentIndex() == 1:
                self.refresh_matrices()
