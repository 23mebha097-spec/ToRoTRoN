from PyQt5 import QtWidgets, QtCore, QtGui
from graphics.canvas import RobotCanvas
from core.robot import Robot
from ui.panels.align_panel import AlignPanel
from ui.panels.joint_panel import JointPanel
from ui.panels.matrices_panel import MatricesPanel
from ui.panels.program_panel import ProgramPanel
from ui.panels.simulation_panel import SimulationPanel
from core.serial_manager import SerialManager
import os
import numpy as np
import random
from ui.widgets.code_drawer import CodeDrawer
from core.firmware_gen import generate_esp32_firmware

# Mixin imports — each provides a subset of MainWindow methods
from ui.mixins.links_mixin import LinksMixin
from ui.mixins.hardware_mixin import HardwareMixin
from ui.mixins.project_mixin import ProjectMixin
from ui.mixins.navigation_mixin import NavigationMixin


class MainWindow(QtWidgets.QMainWindow, LinksMixin, HardwareMixin, ProjectMixin, NavigationMixin):
    log_signal = QtCore.pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ToRoTRoN - Programmable 3-D Robotic Assembly")
        self.resize(1200, 800)
        
        self.robot = Robot()
        self.serial_mgr = SerialManager(self)
        self.alignment_cache = {} # Cache for storing alignment points: {(parent, child): point}
        self.current_speed = 50   # Global speed setting (0-100%)
        self.init_ui()
        self.apply_styles()
        
        # Periodic Port Refresh (Auto-Scan)
        self.port_scan_timer = QtCore.QTimer(self)
        self.port_scan_timer.timeout.connect(self.refresh_ports_silently)
        self.port_scan_timer.start(5000) # Scan every 5s
        
        # Connect signals
        self.log_signal.connect(self.log)

    def init_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        self.main_layout = QtWidgets.QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # --- TOP BAR ---
        top_bar = QtWidgets.QWidget()
        top_bar.setStyleSheet("background-color: white; border-bottom: 1px solid #e0e0e0;")
        top_bar.setFixedHeight(55)
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 5, 10, 5)
        
        # --- Logo / Title ---
        logo_label = QtWidgets.QLabel("ToRoTRoN")
        logo_label.setStyleSheet("""
            color: #1976d2;
            font-size: 22px;
            font-weight: bold;
            font-family: 'Segoe UI', Roboto, sans-serif;
            padding: 5px;
        """)
        top_layout.addWidget(logo_label)
        
        top_layout.addStretch()
        
        # --- COM Port Section ---
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setFixedWidth(200)
        self.port_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 5px;
                color: #212121;
            }
        """)
        top_layout.addWidget(self.port_combo)
        
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; border-radius: 6px; padding: 8px 15px;")
        self.connect_btn.clicked.connect(self.toggle_connection)
        top_layout.addWidget(self.connect_btn)
        
        refresh_btn = QtWidgets.QPushButton("↻")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setStyleSheet("border-radius: 15px; font-size: 16px;")
        refresh_btn.clicked.connect(self.refresh_ports)
        top_layout.addWidget(refresh_btn)
        
        top_layout.addSpacing(15)
        
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.clicked.connect(self.save_project)
        top_layout.addWidget(self.save_btn)
        
        self.load_btn = QtWidgets.QPushButton("Open")
        self.load_btn.clicked.connect(self.load_project)
        top_layout.addWidget(self.load_btn)
        
        # Simulation toggle button
        self.sim_toggle_btn = QtWidgets.QPushButton("Simulation Mode")
        self.sim_toggle_btn.setCheckable(True)
        self.sim_toggle_btn.setChecked(False)
        self.sim_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #212121;
                border: 1px solid #bbb;
                border-radius: 8px;
                font-weight: bold;
                padding: 8px 15px;
            }
            QPushButton:checked {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #4CAF50;
            }
        """)
        self.sim_toggle_btn.clicked.connect(self.toggle_simulation)
        top_layout.addWidget(self.sim_toggle_btn)
        
        self.main_layout.addWidget(top_bar)
        
        # --- MAIN CONTENT AREA ---
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Left Side - Navigation + Panel Stack
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # --- ICON NAVIGATION BAR ---
        nav_bar = QtWidgets.QWidget()
        nav_bar.setObjectName("nav_bar_widget")
        nav_bar.setStyleSheet("background-color: white; border-bottom: 2px solid #e0e0e0;")
        nav_bar.setFixedHeight(50)
        nav_layout = QtWidgets.QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 5, 8, 5)
        nav_layout.setSpacing(6)
        
        # Create navigation buttons with text (no icons/emojis)
        self.nav_buttons = []
        nav_items = [
            ("Links", "Manage robot links and components"),
            ("Align", "Align components together"),
            ("Joint", "Create and control joints"),
            ("Matrices", "View transformation matrices"),
            ("Code", "Program robot movements")
        ]
        
        # Ensure panel_stack is initialized before buttons are connected
        self.panel_stack = QtWidgets.QStackedWidget()
        self.panel_stack.setMinimumWidth(280)
        
        # Create panels
        self.links_tab = QtWidgets.QWidget()
        self.setup_links_tab()
        
        self.align_tab = AlignPanel(self)
        self.joint_tab = JointPanel(self)
        self.matrices_tab = MatricesPanel(self)
        self.program_tab = ProgramPanel(self)
        self.simulation_tab = SimulationPanel(self)
        
        self.panel_stack.addWidget(self.links_tab)
        self.panel_stack.addWidget(self.align_tab)
        self.panel_stack.addWidget(self.joint_tab)
        self.panel_stack.addWidget(self.matrices_tab)
        self.panel_stack.addWidget(self.program_tab)
        self.panel_stack.addWidget(self.simulation_tab)
        
        for name, tooltip in nav_items:
            btn = QtWidgets.QPushButton(name)
            btn.setObjectName(name)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(40)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
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
                QPushButton:hover {
                    background-color: #e3f2fd;
                    color: #1976d2;
                }
                QPushButton:pressed {
                    background-color: #bbdefb;
                }
            """)
            btn.clicked.connect(lambda checked, idx=len(self.nav_buttons): self.switch_panel(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        nav_layout.addStretch()
        left_layout.addWidget(nav_bar)
        
        # --- STACKED WIDGET FOR PANELS ---
        # Wrap panel_stack in a Scroll Area for responsiveness on small screens
        panel_scroll = QtWidgets.QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setWidget(self.panel_stack)
        panel_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        left_layout.addWidget(panel_scroll, 1)
        
        # Refresh ports on launch
        self.refresh_ports()
        
        # Right Side - Vertical Splitter (Canvas on top, Console on bottom)
        self.right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        self.canvas = RobotCanvas()
        self.right_splitter.addWidget(self.canvas)
        
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("System Log...")
        self.console.setVisible(False)  # Hidden by default
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                border: none;
                padding: 10px;
                selection-background-color: #264f78;
            }
        """)
        self.right_splitter.addWidget(self.console)
        
        # Hide console initially — canvas takes full space
        self.right_splitter.setSizes([800, 0])
        
        # --- TERMINAL TOGGLE BUTTON (bottom-right) ---
        self.terminal_btn = QtWidgets.QPushButton("⌘ Terminal")
        self.terminal_btn.setCheckable(True)
        self.terminal_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.terminal_btn.setToolTip("Toggle system terminal")
        self.terminal_btn.setAccessibleName("Toggle Terminal")
        self.terminal_btn.setFixedHeight(30)
        self.terminal_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                border-radius: 0px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 16px;
            }
            QPushButton:checked {
                background-color: #1976d2;
                color: white;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.terminal_btn.clicked.connect(self.toggle_terminal)
        
        # Add components to main horizontal splitter
        self.gen_code_btn = QtWidgets.QPushButton("Generate ESP32 Code")
        self.gen_code_btn.setToolTip("Auto-generate Arduino code for all joints")
        self.gen_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                padding: 12px;
                font-size: 14px;
                border: none;
                border-radius: 8px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        self.gen_code_btn.clicked.connect(self.on_generate_code)
        left_layout.addWidget(self.gen_code_btn)

        # --- UNIVERSAL SPEED CONTROL ---
        speed_container = QtWidgets.QWidget()
        speed_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 2px solid #1976d2;
            }
        """)
        speed_layout = QtWidgets.QHBoxLayout(speed_container)
        speed_layout.setContentsMargins(12, 10, 12, 10)
        speed_layout.setSpacing(12)
        
        speed_header = QtWidgets.QLabel("Speed")
        speed_header.setStyleSheet("font-weight: bold; font-size: 15px; color: #1976d2; background: transparent; border: none;")
        speed_layout.addWidget(speed_header)
        
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setValue(self.current_speed)
        self.speed_slider.setCursor(QtCore.Qt.PointingHandCursor)
        self.speed_slider.setStyleSheet("""
            QSlider {
                background: transparent;
                border: none;
                min-height: 28px;
            }
            QSlider::groove:horizontal {
                height: 10px;
                background: #f0f0f0;
                border-radius: 5px;
                border: 1px solid #ddd;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #bbdefb, stop: 1 #1976d2);
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 2px solid #1976d2;
                width: 22px;
                height: 22px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover {
                background: #e3f2fd;
                border-color: #1565c0;
            }
        """)
        speed_layout.addWidget(self.speed_slider, 1)
        
        self.speed_spin = QtWidgets.QSpinBox()
        self.speed_spin.setRange(0, 100)
        self.speed_spin.setValue(self.current_speed)
        self.speed_spin.setSuffix("%")
        self.speed_spin.setFixedWidth(80)
        self.speed_spin.setStyleSheet("""
            QSpinBox {
                background: white;
                color: #1976d2;
                border: 2px solid #1976d2;
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: #e3f2fd;
                border: none;
                width: 18px;
            }
        """)
        speed_layout.addWidget(self.speed_spin)
        
        self.speed_slider.valueChanged.connect(self.on_speed_change)
        self.speed_spin.valueChanged.connect(self.on_speed_change)
        
        left_layout.addWidget(speed_container)

        self.main_splitter.addWidget(left_container)
        
        # Wrap right splitter + terminal button in a container
        right_container = QtWidgets.QWidget()
        right_vbox = QtWidgets.QVBoxLayout(right_container)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(0)
        right_vbox.addWidget(self.right_splitter, 1)
        right_vbox.addWidget(self.terminal_btn)
        
        self.main_splitter.addWidget(right_container)
        
        # --- CODE DRAWER (Right sidebar) ---
        self.code_drawer = CodeDrawer(self)
        self.main_splitter.addWidget(self.code_drawer)
        
        # Set initial side-to-side bias (Left=350, RightSplitter=850, Code=0)
        self.main_splitter.setSizes([350, 850, 0])
        
        self.main_layout.addWidget(self.main_splitter)
        
        # Connect Focus Button from Canvas
        self.canvas.focus_btn.clicked.connect(self.on_focus_base)
        self.canvas.on_drop_callback = self.sync_link_transform
        self.canvas.on_deselect_callback = self.on_deselect


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
