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

class MainWindow(QtWidgets.QMainWindow):
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
        
        # Connect signals
        self.log_signal.connect(self.log)

    def init_ui(self):
        # Central widget
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.overall_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.overall_layout.setContentsMargins(5, 5, 5, 5)
        self.overall_layout.setSpacing(5)
        
        # --- HARDWARE TOOLBAR ---
        self.hardware_bar = QtWidgets.QHBoxLayout()
        self.hardware_bar.setContentsMargins(10, 0, 10, 0)
        
        hw_label = QtWidgets.QLabel("ESP32 HARDWARE:")
        hw_label.setStyleSheet("color: #1976d2; font-weight: bold; font-size: 11px;")
        self.hardware_bar.addWidget(hw_label)
        
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(120)
        self.port_combo.setStyleSheet("background-color: white; color: black; padding: 3px; border: 1px solid #bbb;")
        self.hardware_bar.addWidget(self.port_combo)
        
        self.refresh_ports_btn = QtWidgets.QPushButton("🔄")
        self.refresh_ports_btn.setToolTip("Refresh COM Ports")
        self.refresh_ports_btn.setFixedWidth(30)
        self.refresh_ports_btn.setStyleSheet("background-color: #e0e0e0; color: black; border: 1px solid #bbb;")
        self.refresh_ports_btn.clicked.connect(self.refresh_ports)
        self.hardware_bar.addWidget(self.refresh_ports_btn)
        
        self.connect_btn = QtWidgets.QPushButton("CONNECT")
        self.connect_btn.setFixedWidth(100)
        self.connect_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.hardware_bar.addWidget(self.connect_btn)
        
        self.hardware_bar.addStretch()
        
        # --- PROJECT TOOLBAR ---
        project_label = QtWidgets.QLabel("PROJECT:")
        project_label.setStyleSheet("color: #1976d2; font-weight: bold; font-size: 11px;")
        self.hardware_bar.addWidget(project_label)

        self.save_btn = QtWidgets.QPushButton("SAVE")
        self.save_btn.setFixedWidth(80)
        self.save_btn.setStyleSheet("background-color: #e0e0e0; color: black; border: 1px solid #bbb;")
        self.save_btn.clicked.connect(self.save_project)
        self.hardware_bar.addWidget(self.save_btn)

        self.load_btn = QtWidgets.QPushButton("OPEN")
        self.load_btn.setFixedWidth(80)
        self.load_btn.setStyleSheet("background-color: #e0e0e0; color: black; border: 1px solid #bbb;")
        self.load_btn.clicked.connect(self.load_project)
        self.hardware_bar.addWidget(self.load_btn)

        # --- SIMULATION TOOLBAR ---
        self.hardware_bar.addSpacing(20)
        self.sim_btn = QtWidgets.QPushButton()
        self.sim_btn.setIcon(QtGui.QIcon("assets/robotic-arm.png"))
        self.sim_btn.setIconSize(QtCore.QSize(24, 24))
        self.sim_btn.setToolTip("Toggle Simulation Mode")
        self.sim_btn.setCheckable(True)
        self.sim_btn.setFixedSize(40, 40)
        self.sim_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #bbb;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #4caf50;
                border: 1px solid #388e3c;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.sim_btn.setShortcut("Ctrl+Q")
        self.sim_btn.clicked.connect(self.toggle_simulation)
        self.hardware_bar.addWidget(self.sim_btn)
        
        self.overall_layout.addLayout(self.hardware_bar)
        
        # Main content layout
        self.main_layout = QtWidgets.QHBoxLayout()
        self.overall_layout.addLayout(self.main_layout)
        
        self.refresh_ports() # Initial load
        
        # MAIN SPLITTER (Allows resizing Controls vs 3D View)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Left Panel Container
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # --- ICON NAVIGATION BAR ---
        nav_bar = QtWidgets.QWidget()
        nav_bar.setObjectName("nav_bar_widget")
        nav_bar.setStyleSheet("background-color: #000000;")
        nav_bar.setFixedHeight(60)
        nav_layout = QtWidgets.QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        nav_layout.setSpacing(5)
        
        # Create navigation buttons with text (no icons/emojis)
        self.nav_buttons = []
        nav_items = [
            ("Links", "Manage robot links and components"),
            ("Align", "Align components together"),
            ("Joint", "Create and control joints"),
            ("Matrices", "View transformation matrices"),
            ("Code", "Program robot movements")
        ]
        
        for name, tooltip in nav_items:
            btn = QtWidgets.QPushButton(name)
            btn.setObjectName(name)
            btn.setToolTip(tooltip)
            # Remove fixed size to allow text to fit, or use fixed height
            btn.setFixedHeight(40)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #000000;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #333333;
                }
                QPushButton:pressed {
                    background-color: #1976d2;
                }
            """)
            btn.clicked.connect(lambda checked, idx=len(self.nav_buttons): self.switch_panel(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        nav_layout.addStretch()
        left_layout.addWidget(nav_bar)
        
        # --- STACKED WIDGET FOR PANELS ---
        self.panel_stack = QtWidgets.QStackedWidget()
        self.panel_stack.setMinimumWidth(250)
        
        # Create panels
        self.links_tab = QtWidgets.QWidget()
        self.setup_links_tab()
        
        self.align_tab = AlignPanel(self)
        self.joint_tab = JointPanel(self)
        self.matrices_tab = MatricesPanel(self)
        self.program_tab = ProgramPanel(self)
        
        self.panel_stack.addWidget(self.links_tab)
        self.panel_stack.addWidget(self.align_tab)
        self.panel_stack.addWidget(self.joint_tab)
        self.panel_stack.addWidget(self.matrices_tab)

        self.panel_stack.addWidget(self.program_tab)
        
        self.simulation_tab = SimulationPanel(self)
        self.panel_stack.addWidget(self.simulation_tab)
        
        left_layout.addWidget(self.panel_stack, 1)  # stretch=1 so panel takes all extra vertical space
        
        # Set initial selection
        self.switch_panel(0)
        
        # Connect panel change to refresh lists
        self.panel_stack.currentChanged.connect(self.on_tab_changed)
        
        # Right Side - Vertical Splitter (Canvas on top, Console on bottom)
        self.right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        self.canvas = RobotCanvas()
        self.right_splitter.addWidget(self.canvas)
        
        self.console = QtWidgets.QTextEdit()
        # Remove fixed height to allow resizing
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("System Log...")
        self.right_splitter.addWidget(self.console)
        
        # Set initial bias (Canvas 600px, Console 150px)
        self.right_splitter.setSizes([600, 150])
        
        # Add components to main horizontal splitter
        self.gen_code_btn = QtWidgets.QPushButton("⚡ GENERATE ESP32 CODE")
        self.gen_code_btn.setToolTip("Auto-generate Arduino code for all joints")
        self.gen_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12; 
                color: white; 
                font-weight: bold; 
                padding: 10px;
                font-size: 11px;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        self.gen_code_btn.clicked.connect(self.on_generate_code)
        left_layout.addWidget(self.gen_code_btn)

        # --- UNIVERSAL SPEED CONTROL ---
        speed_container = QtWidgets.QWidget()
        speed_container.setStyleSheet("background-color: #1a1b1e; border-top: 1px solid #333;")
        speed_container.setMaximumHeight(60)
        speed_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        speed_layout = QtWidgets.QVBoxLayout(speed_container)
        speed_layout.setContentsMargins(15, 10, 15, 10)
        
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setValue(self.current_speed)
        self.speed_slider.setFixedHeight(30)
        self.speed_slider.setCursor(QtCore.Qt.PointingHandCursor)
        self.speed_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 10px;
                background: #000;
                border-radius: 5px;
                border: 1px solid #222;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #3c4cdb, stop:1 #4a90e2);
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, 
                    stop:0 #5fa8ff, stop:0.2 #4a90e2, stop:0.3 #111, stop:1 #000);
                border: 2px solid #333;
                width: 24px;
                height: 24px;
                margin-top: -8px;
                margin-bottom: -8px;
                border-radius: 12px;
            }
            QSlider::handle:horizontal:hover {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, 
                    stop:0 #74b9ff, stop:0.2 #5fa8ff, stop:0.3 #222, stop:1 #000);
                border: 2px solid #4a90e2;
            }
        """)
        
        # Link to simple hidden spinbox to maintain existing speed logic connection
        self.speed_spin = QtWidgets.QSpinBox()
        self.speed_spin.setRange(0, 100)
        self.speed_spin.setValue(self.current_speed)
        self.speed_spin.hide() 
        
        self.speed_slider.valueChanged.connect(self.on_speed_change)
        self.speed_spin.valueChanged.connect(self.on_speed_change)
        speed_layout.addWidget(self.speed_slider)
        
        left_layout.addWidget(speed_container)

        self.main_splitter.addWidget(left_container)
        self.main_splitter.addWidget(self.right_splitter)
        
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
        
        # We need to save the new transform as 't_offset'
        # If the link has a parent, we must save the offset RELATIVE to that parent
        if link.parent_joint:
            parent_world = link.parent_joint.parent_link.t_world
            joint_rot = link.parent_joint.get_matrix()
            
            # T_world = T_parent_world @ T_offset @ T_joint_rot
            # => T_offset = Inv(T_parent_world) @ T_world @ Inv(T_joint_rot)
            inv_parent = np.linalg.inv(parent_world)
            inv_joint = np.linalg.inv(joint_rot)
            
            link.t_offset = inv_parent @ matrix @ inv_joint
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
                # Selected: Blue
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1976d2;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 5px 15px;
                    }
                    QPushButton:hover { background-color: #1976d2; }
                """)
            else:
                # Unselected: Black
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #000000;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 5px 15px;
                    }
                    QPushButton:hover { background-color: #333333; }
                """)

    def toggle_simulation(self, checked):
        """Toggles between Edit Mode and Simulation Mode."""
        if checked:
            # Enter Simulation Mode
            self.log("Entering Simulation Mode...")
            
            # Hide Navigation Bar
            self.findChild(QtWidgets.QWidget, "nav_bar_widget").setVisible(False)
            
            # Switch to Simulation Panel (Index 5)
            self.panel_stack.setCurrentWidget(self.simulation_tab)
            self.simulation_tab.refresh_joints()
            
            # Disable other controls if needed
            self.save_btn.setEnabled(False)
            self.load_btn.setEnabled(False)
            
        else:
            # Exit Simulation Mode
            self.log("Exiting Simulation Mode...")
            
            # Show Navigation Bar
            self.findChild(QtWidgets.QWidget, "nav_bar_widget").setVisible(True)
            
            # Switch back to previous panel (default to Links or whatever was active)
            # For simplicity, we go back to the first tab (Links) or keep state if tracked
            self.switch_panel(0)
            
            # Enable controls
            self.save_btn.setEnabled(True)
            self.load_btn.setEnabled(True)
            
            # Remove any speed overlay from canvas
            self.canvas.plotter.remove_actor("speed_overlay")
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

    def setup_links_tab(self):
        layout = QtWidgets.QVBoxLayout(self.links_tab)
        
        import_btn = QtWidgets.QPushButton("Import STEP/STL")
        import_btn.clicked.connect(self.import_mesh)
        layout.addWidget(import_btn)
        
        self.links_list = QtWidgets.QListWidget()
        self.links_list.itemClicked.connect(self.on_link_selected)
        layout.addWidget(self.links_list)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.set_base_btn = QtWidgets.QPushButton("Set as Base")
        self.remove_btn = QtWidgets.QPushButton("Remove")
        
        self.set_base_btn.clicked.connect(self.set_as_base)
        self.remove_btn.clicked.connect(self.remove_link)
        
        btn_layout.addWidget(self.set_base_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)

        self.color_btn = QtWidgets.QPushButton("Change Color")
        self.color_btn.clicked.connect(self.change_color)
        layout.addWidget(self.color_btn)
        
        layout.addStretch()

    def on_link_selected(self, item):
        name = item.text()
        
        # Allow all objects to be selected, including jointed ones
        # Users may need to select jointed objects to build further joints
        self.canvas.select_actor(name)
        
        # Update button text based on whether selection is the base
        if self.robot.base_link and name == self.robot.base_link.name:
            self.set_base_btn.setText("Deselect as Base")
        else:
            self.set_base_btn.setText("Set as Base")

    def set_as_base(self):
        item = self.links_list.currentItem()
        if not item:
            return
            
        name = item.text()
        if name not in self.robot.links:
            return
            
        link = self.robot.links[name]
        
        # TOGGLE LOGIC: If it's already the base, unset it
        if self.robot.base_link == link:
            self.robot.base_link = None
            link.is_base = False
            self.canvas.fixed_actors.clear()
            self.log(f"BASE UNSET: {name}. Link is now floating.")
            self.set_base_btn.setText("Set as Base")
        else:
            # 1. Calculate offset to center the mesh at (0,0,0)
            # We need to move the centroid to origin.
            # User requirement: "set that object's base at the center of base"
            centroid = link.mesh.centroid
            
            # Create a translation matrix that moves the mesh's centroid to (0,0,0)
            t_center = np.eye(4)
            t_center[:3, 3] = -centroid
            
            # 2. Update Link Properties
            # Unset old base flag if exists
            if self.robot.base_link:
                self.robot.base_link.is_base = False
                
            link.is_base = True
            link.t_offset = t_center # Permanent offset to center it
            
            # Base is defined at World Origin
            self.robot.base_link = link
            
            # LOCK in 3D Canvas (so it cannot be dragged)
            self.canvas.fixed_actors.clear()
            self.canvas.fixed_actors.add(name)
            self.set_base_btn.setText("Deselect as Base")
            self.log(f"BASE SET: {name}")
            self.log(f"Moved centroid {centroid} to (0,0,0)")
            self.canvas.plotter.reset_camera()
        
        # 3. Update Robot
        self.robot.update_kinematics()
        self.canvas.update_transforms(self.robot)
        
        # 4. Focus Camera
        self.update_link_colors()

    def go_to_joint_tab(self):
        item = self.links_list.currentItem()
        if not item:
            return
        
        name = item.text()
        # Switch to Joint Tab (Index 2)
        self.switch_panel(2)
        
        # Refresh links first to ensure combo boxes are up to date
        self.joint_tab.refresh_links()
        
        # Pre-select this link as the Child Link (since we are jointing IT to something else)
        self.joint_tab.select_child_link(name)
        
        self.log(f"Switched to Joint creation for: {name}")

    def remove_link(self):
        item = self.links_list.currentItem()
        if not item:
            return
        
        name = item.text()
        
        # 1. Remove from Robot Model (Core)
        self.robot.remove_link(name)
        
        # 2. Cleanup and Sync Graphics state
        self.canvas.fixed_actors.clear()
        if self.robot.base_link:
            self.canvas.fixed_actors.add(self.robot.base_link.name)
        
        # Remove from Scene (Graphics)
        self.canvas.remove_actor(name)
        
        # 3. Remove from UI List
        row = self.links_list.row(item)
        self.links_list.takeItem(row)
        
        self.log(f"Removed link: {name}")
        
        # Refresh kinematics just in case
        self.robot.update_kinematics()
        self.canvas.update_transforms(self.robot)
        self.update_link_colors()

    def update_link_colors(self):
        """Updates the icons in the link list to show Base (Red) vs Normal/Joint (Green)."""
        root = self.robot.base_link
        
        # Create helper to make colored icons
        def make_icon(color_str):
            pixmap = QtGui.QPixmap(20, 20)
            pixmap.fill(QtGui.QColor(color_str))
            return QtGui.QIcon(pixmap)
            
        red_icon = make_icon("#d32f2f")   # Base Red
        green_icon = make_icon("#388e3c") # Joint Green
        
        for i in range(self.links_list.count()):
            item = self.links_list.item(i)
            name = item.text()
            
            if name in self.robot.links:
                link = self.robot.links[name]
                if link == root:
                    item.setIcon(red_icon)
                    item.setToolTip("Base Link (Fixed/Locked)")
                else:
                    item.setIcon(green_icon)
                    item.setToolTip("Joint/Child Link")

    def apply_styles(self):
        # Premium light theme with blue, white, black, and grey
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f5f5f5;
                color: #212121;
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
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
                background-color: #e0e0e0;
                border: 1px solid #bbb;
                padding: 8px;
                border-radius: 4px;
                color: #212121;
            }
            QPushButton:hover {
                background-color: #1976d2;
                color: white;
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

    def refresh_ports(self):
        """Update the list of available COM ports."""
        self.port_combo.clear()
        ports = self.serial_mgr.get_available_ports()
        self.port_combo.addItems(ports)
        if not ports:
            self.port_combo.addItem("No Ports found")

    def toggle_connection(self):
        """Connect or disconnect from the selected serial port."""
        if not self.serial_mgr.is_connected:
            port = self.port_combo.currentText()
            if port == "No Ports found":
                self.log("Cannot connect: No serial ports detected.")
                return
                
            if self.serial_mgr.connect(port):
                self.connect_btn.setText("DISCONNECT")
                self.connect_btn.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold;")
        else:
            self.serial_mgr.disconnect()
            self.connect_btn.setText("CONNECT")
            self.connect_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")

    def on_generate_code(self):
        """Generates ESP32 code and populates the sidebar panel."""
        if not self.robot.joints:
            self.log("⚠️ No joints defined! Add some joints first.")
            return
            
        code = generate_esp32_firmware(self.robot, default_speed=self.current_speed)
        self.code_drawer.set_code(code)
        
        # Expand the splitter to show the code panel (Width 400 suggested)
        self.code_drawer.show()
        self.main_splitter.setSizes([350, 450, 400])
        
        self.log("⚡ ESP32 Code Generated in Sidebar.")

    def import_mesh(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Mesh", "", "3D Files (*.stl *.step *.stp *.obj)"
        )
        if file_path:
            self.log(f"Importing: {os.path.basename(file_path)}")
            import trimesh
            try:
                loaded = trimesh.load(file_path)
                
                # Handle Scenes (often returned by STEP/STEP files)
                if isinstance(loaded, trimesh.Scene):
                    self.log("Detected assembly/scene. Merging meshes...")
                    # force='mesh' ensures we get a single Trimesh object
                    mesh = loaded.to_mesh() 
                else:
                    mesh = loaded

                # VALIDATION: Check if mesh is empty
                if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
                     self.log("ERROR: Imported mesh has 0 vertices! The file might be empty or incompatible.")
                     return

                # Log mesh stats
                num_v = len(mesh.vertices)
                bounds = mesh.bounds
                size = bounds[1] - bounds[0]
                center = mesh.centroid
                self.log(f"Original Center: {center}")
                
                # NOTE: We do NOT auto-center the mesh geometry anymore.
                # Preserving the original CAD origin is critical for correct joint rotation.
                # If the object is far away, we rely on reset_camera() to find it.

                # Assign a random distinct color
                colors = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6"]
                link_color = random.choice(colors)
                
                name = os.path.basename(file_path).split('.')[0]
                link = self.robot.add_link(name, mesh)
                link.color = link_color
                self.links_list.addItem(name)
                
                # Initially show it at (1, 1, 1) as requested
                t_import = np.eye(4)
                t_import[:3, 3] = [1.0, 1.0, 1.0]
                link.t_offset = t_import
                
                self.canvas.update_link_mesh(name, mesh, t_import, color=link.color)
                self.log(f"Successfully loaded: {name} at (1, 1, 1)")
                
                # Force camera reset with a slight delay/update ensures it catches the new actor
                self.canvas.plotter.render()
                self.canvas.plotter.reset_camera()
                
                self.update_link_colors()
                
            except ImportError as ie:
                self.log(f"MISSING DEPENDENCY: {str(ie)}")
                QtWidgets.QMessageBox.critical(self, "Import Error", 
                    f"To load STEP files, you need extra libraries.\n\nError: {str(ie)}\n\n"
                    "I am currently trying to install 'cascadio' for you. "
                    "Please restart the app once the installation finishes.")
            except Exception as e:
                self.log(f"Error: {str(e)}")

    def on_tab_changed(self, index):
        # Disable dragging for all tabs except 'Links' (index 0)
        # This prevents accidental movement while Aligning or Creating Joints
        self.canvas.enable_drag = (index == 0)
        
        widget = self.panel_stack.widget(index)
        if hasattr(widget, 'refresh_links'):
            widget.refresh_links()
        if hasattr(widget, 'update_display'):
            widget.update_display()
        if hasattr(widget, 'refresh_sliders'):
            widget.refresh_sliders()

    def log(self, text):
        self.console.append(text)

    def change_color(self):
        item = self.links_list.currentItem()
        if not item:
            return
            
        name = item.text()
        if name not in self.robot.links:
            return
            
        link = self.robot.links[name]
        initial_color = QtGui.QColor(link.color)
        
        color = QtWidgets.QColorDialog.getColor(initial_color, self, f"Select Color for {name}")
        if color.isValid():
            hex_color = color.name()
            link.color = hex_color
            if name in self.canvas.actors:
                self.canvas.set_actor_color(name, hex_color)
            self.update_link_colors()
            self.log(f"Changed color of {name} to {hex_color}")

    def save_project(self):
        """Saves current robot configuration into a .trn zip file."""
        import json
        import zipfile
        import io
        import tempfile
        import shutil

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Project", "", "ToRoTRoN Project (*.trn)"
        )
        if not file_path:
            return
            
        if not file_path.endswith('.trn'):
            file_path += '.trn'

        try:
            # Create a temporary directory to gather files
            with tempfile.TemporaryDirectory() as temp_dir:
                mesh_dir = os.path.join(temp_dir, "meshes")
                os.makedirs(mesh_dir)

                robot_data = {
                    "links": [],
                    "joints": [],
                    "ui_state": {
                        "joint_panel_joints": {},
                        "program_code": "",
                        "live_sync": False,
                        "alignment_point": None,
                        "alignment_normal": None
                    }
                }

                # 1. Gather Links
                for name, link in self.robot.links.items():
                    mesh_filename = f"{name}.stl"
                    mesh_path = os.path.join(mesh_dir, mesh_filename)
                    
                    # Export mesh
                    link.mesh.export(mesh_path, file_type='stl')
                    
                    robot_data["links"].append({
                        "name": link.name,
                        "mesh_file": f"meshes/{mesh_filename}",
                        "color": link.color,
                        "is_base": link.is_base,
                        "t_offset": link.t_offset.tolist()
                    })

                # 2. Gather Joints (Robot Core)
                for name, joint in self.robot.joints.items():
                    robot_data["joints"].append({
                        "name": joint.name,
                        "parent_link": joint.parent_link.name,
                        "child_link": joint.child_link.name,
                        "joint_type": joint.joint_type,
                        "origin": joint.origin.tolist(),
                        "axis": joint.axis.tolist(),
                        "min_limit": joint.min_limit,
                        "max_limit": joint.max_limit,
                        "current_value": joint.current_value
                    })

                # 3. Gather UI State
                # Joint Panel UI Data
                if hasattr(self, 'joint_tab'):
                    for child_name, data in self.joint_tab.joints.items():
                        clean_data = data.copy()
                        if 'alignment_point' in clean_data and isinstance(clean_data['alignment_point'], np.ndarray):
                            clean_data['alignment_point'] = clean_data['alignment_point'].tolist()
                        robot_data["ui_state"]["joint_panel_joints"][child_name] = clean_data

                # Program Tab Code
                if hasattr(self, 'program_tab'):
                    robot_data["ui_state"]["program_code"] = self.program_tab.code_edit.toPlainText()
                    robot_data["ui_state"]["live_sync"] = self.program_tab.sync_hw_check.isChecked()

                # Align Panel Stored Point (for continuing joint creation)
                if hasattr(self, 'align_tab'):
                    if hasattr(self.align_tab, 'alignment_point') and self.align_tab.alignment_point is not None:
                        robot_data["ui_state"]["alignment_point"] = self.align_tab.alignment_point.tolist()
                    if hasattr(self.align_tab, 'alignment_normal') and self.align_tab.alignment_normal is not None:
                        robot_data["ui_state"]["alignment_normal"] = self.align_tab.alignment_normal.tolist()

                # 4. Write JSON
                json_path = os.path.join(temp_dir, "robot.json")
                with open(json_path, 'w') as f:
                    json.dump(robot_data, f, indent=4)

                # 4. ZIP everything up
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            abs_file = os.path.join(root, file)
                            rel_file = os.path.relpath(abs_file, temp_dir)
                            zipf.write(abs_file, rel_file)

            self.log(f"Project saved to: {file_path}")
            QtWidgets.QMessageBox.information(self, "Success", "Project saved successfully.")

        except Exception as e:
            self.log(f"SAVE ERROR: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Could not save project: {str(e)}")

    def load_project(self):
        """Loads a robot configuration from a .trn zip file."""
        import json
        import zipfile
        import tempfile
        import shutil
        import trimesh

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Project", "", "ToRoTRoN Project (*.trn)"
        )
        if not file_path:
            return

        try:
            # 1. Clear Current Robot
            self.robot = Robot()
            self.canvas.clear_highlights()
            # Remove all actors from canvas
            actor_names = list(self.canvas.actors.keys())
            for name in actor_names:
                self.canvas.remove_actor(name)
            self.canvas.fixed_actors.clear()
            self.links_list.clear()

            # Reset UI Panels
            if hasattr(self, 'joint_tab'): self.joint_tab.reset_joint_ui()
            if hasattr(self, 'align_tab'): self.align_tab.reset_panel()

            # 2. Extract ZIP to temp folder
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(file_path, 'r') as zipf:
                    zipf.extractall(temp_dir)

                # 3. Read JSON
                json_path = os.path.join(temp_dir, "robot.json")
                if not os.path.exists(json_path):
                    raise Exception("Invalid project file: robot.json missing")

                with open(json_path, 'r') as f:
                    robot_data = json.load(f)

                # 4. Load Links
                for l_data in robot_data["links"]:
                    name = l_data["name"]
                    mesh_rel_path = l_data["mesh_file"]
                    mesh_path = os.path.join(temp_dir, mesh_rel_path)
                    
                    if not os.path.exists(mesh_path):
                        self.log(f"WARNING: Mesh file missing for {name}")
                        continue

                    mesh = trimesh.load(mesh_path)
                    link = self.robot.add_link(name, mesh)
                    link.color = l_data.get("color", "lightgray")
                    link.is_base = l_data.get("is_base", False)
                    link.t_offset = np.array(l_data["t_offset"])
                    
                    if link.is_base:
                        self.robot.base_link = link
                        self.canvas.fixed_actors.add(name)

                    # Add to UI and Canvas
                    self.links_list.addItem(name)
                    self.canvas.update_link_mesh(name, mesh, link.t_offset, color=link.color)

                # 5. Load Joints (Robot Core)
                for j_data in robot_data["joints"]:
                    name = j_data["name"]
                    parent_name = j_data["parent_link"]
                    child_name = j_data["child_link"]
                    
                    if parent_name in self.robot.links and child_name in self.robot.links:
                        joint = self.robot.add_joint(name, parent_name, child_name)
                        joint.joint_type = j_data.get("joint_type", "revolute")
                        joint.origin = np.array(j_data["origin"])
                        joint.axis = np.array(j_data["axis"])
                        joint.min_limit = j_data.get("min_limit", -180.0)
                        joint.max_limit = j_data.get("max_limit", 180.0)
                        joint.current_value = j_data.get("current_value", 0.0)

                # 6. Load UI State
                ui_state = robot_data.get("ui_state", {})
                
                # Restore Joint Panel Data
                if hasattr(self, 'joint_tab'):
                    self.joint_tab.joints = ui_state.get("joint_panel_joints", {})
                    # Convert alignment points back to numpy
                    for child_name, data in self.joint_tab.joints.items():
                        if 'alignment_point' in data and data['alignment_point'] is not None:
                            data['alignment_point'] = np.array(data['alignment_point'])
                    
                    self.joint_tab.refresh_joints_history()
                    self.joint_tab.refresh_links()

                # Restore Program Tab
                if hasattr(self, 'program_tab'):
                    self.program_tab.code_edit.setPlainText(ui_state.get("program_code", ""))
                    self.program_tab.sync_hw_check.setChecked(ui_state.get("live_sync", False))

                # Restore Align Panel alignment data
                if hasattr(self, 'align_tab'):
                    ap = ui_state.get("alignment_point")
                    if ap: self.align_tab.alignment_point = np.array(ap)
                    an = ui_state.get("alignment_normal")
                    if an: self.align_tab.alignment_normal = np.array(an)

            # 7. Final Update
            self.robot.update_kinematics()
            self.canvas.update_transforms(self.robot)
            self.update_link_colors()
            
            # Refresh Matrices Panel
            if hasattr(self, 'matrices_tab'):
                self.matrices_tab.refresh_sliders()
                self.matrices_tab.update_display()

            self.canvas.plotter.reset_camera()
            
            self.log(f"Project loaded from: {file_path}")
            QtWidgets.QMessageBox.information(self, "Success", "Project loaded successfully.")

        except Exception as e:
            self.log(f"LOAD ERROR: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Load Error", f"Could not load project: {str(e)}")

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
