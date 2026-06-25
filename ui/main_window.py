from PyQt5 import QtWidgets, QtCore, QtGui
from core.robot import Robot
from ui.panels.align_panel import AlignPanel
from ui.panels.joint_panel import JointPanel
from ui.panels.matrices_panel import MatricesPanel
from ui.panels.gripper_panel import GripperPanel
from ui.panels.simulation_panel import SimulationPanel
from core.serial_manager import SerialManager
import os
import time
import numpy as np
import random
from pathlib import Path
from ui.widgets.code_drawer import CodeDrawer
from core.firmware_gen import generate_esp32_firmware

# Mixin imports — each provides a subset of MainWindow methods
from ui.mixins.links_mixin import LinksMixin
from ui.mixins.hardware_mixin import HardwareMixin
from ui.mixins.project_mixin import ProjectMixin
from ui.mixins.navigation_mixin import NavigationMixin

class TypeOnlyDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def stepBy(self, steps): pass
    def wheelEvent(self, event): event.ignore()

class TypeOnlySpinBox(QtWidgets.QSpinBox):
    def stepBy(self, steps): pass
    def wheelEvent(self, event): event.ignore()


class MainWindow(QtWidgets.QMainWindow, LinksMixin, HardwareMixin, ProjectMixin, NavigationMixin):
    log_signal = QtCore.pyqtSignal(str)
    
    def __init__(self, enable_3d: bool = True):
        super().__init__()
        self.enable_3d = enable_3d
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
        top_layout.setContentsMargins(15, 5, 15, 5)
        top_layout.setSpacing(10)
        
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

        self.load_btn = QtWidgets.QPushButton()
        self.load_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        self.load_btn.setToolTip("Open project")
        self.load_btn.setFixedSize(36, 36)
        self.load_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 18px;
            }
            QPushButton:hover {
                border-color: #1976d2;
            }
        """)
        self.load_btn.clicked.connect(self.load_project)
        top_layout.addWidget(self.load_btn)

        self.save_btn = QtWidgets.QPushButton()
        self.save_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.save_btn.setToolTip("Save project")
        self.save_btn.setFixedSize(36, 36)
        self.save_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 18px;
            }
            QPushButton:hover {
                border-color: #1976d2;
            }
        """)
        self.save_btn.clicked.connect(self.save_project)
        top_layout.addWidget(self.save_btn)
        
        top_layout.addStretch()
        
        # --- COM Port Section ---
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setFixedWidth(200)
        self.port_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                color: #212121;
                font-size: 13px;
            }
        """)
        top_layout.addWidget(self.port_combo)
        
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; border-radius: 6px; padding: 8px 18px; font-size: 13px;")
        self.connect_btn.clicked.connect(self.toggle_connection)
        top_layout.addWidget(self.connect_btn)
        
        refresh_btn = QtWidgets.QPushButton()
        refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setCursor(QtCore.Qt.PointingHandCursor)
        refresh_btn.setToolTip("Refresh serial ports")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 18px;
            }
            QPushButton:hover {
                border-color: #1976d2;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_ports)
        top_layout.addWidget(refresh_btn)

        # Simulation toggle button
        self.sim_toggle_btn = QtWidgets.QPushButton()
        simulation_icon_path = Path(__file__).resolve().parents[1] / "assets" / "simulation_symbol.svg"
        self.sim_toggle_btn.setIcon(QtGui.QIcon(str(simulation_icon_path)))
        self.sim_toggle_btn.setToolTip("Simulation Mode")
        self.sim_toggle_btn.setFixedSize(40, 40)
        self.sim_toggle_btn.setIconSize(QtCore.QSize(24, 24))
        self.sim_toggle_btn.setCheckable(True)
        self.sim_toggle_btn.setChecked(False)
        self.sim_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #212121;
                border: 1px solid #bbb;
                border-radius: 8px;
                font-weight: bold;
                padding: 0px;
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
            ("Gripper", "Control and calibrate robotic grippers"),
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
        self.gripper_tab = GripperPanel(self)
        self.simulation_tab = SimulationPanel(self)
        
        self.panel_stack.addWidget(self.links_tab)
        self.panel_stack.addWidget(self.align_tab)
        self.panel_stack.addWidget(self.joint_tab)
        self.panel_stack.addWidget(self.matrices_tab)
        self.panel_stack.addWidget(self.gripper_tab)
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
        
        # Connect tab change handler for feature switching (like disabling drag)
        self.panel_stack.currentChanged.connect(self.on_tab_changed)
        
        # Refresh ports on launch
        self.refresh_ports()
        
        # Right Side - Vertical Splitter (Canvas on top, Console on bottom)
        self.right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        # --- CANVAS AREA ---
        self.canvas = None
        self.canvas_container = QtWidgets.QWidget()
        self.canvas_container.setStyleSheet("background-color: #fafafa;")
        self.canvas_container_layout = QtWidgets.QVBoxLayout(self.canvas_container)
        self.canvas_container_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_container_layout.setSpacing(0)

        self.canvas_status = QtWidgets.QLabel("Loading 3D engine...")
        self.canvas_status.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas_status.setStyleSheet(
            "color: #616161; font-size: 14px; font-family: 'Segoe UI', Roboto, sans-serif;"
        )
        self.canvas_container_layout.addWidget(self.canvas_status, 1)
        self.right_splitter.addWidget(self.canvas_container)
        
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
        
        self.speed_spin = TypeOnlySpinBox()
        self.speed_spin.setRange(0, 100)
        self.speed_spin.setValue(self.current_speed)
        self.speed_spin.setSuffix("%")
        self.speed_spin.setFixedWidth(80)
        self.speed_spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
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

        self._left_container = left_container
        self._left_container.setEnabled(False)

        if self.enable_3d:
            QtCore.QTimer.singleShot(0, self._init_canvas)
        else:
            self._set_canvas_error("3D disabled (run with --no-3d / TOROTRON_NO_3D=1).")

    def _set_canvas_error(self, message: str, details: str | None = None):
        self.canvas_status.setText(message if not details else f"{message}\n\n{details}")

    def _init_canvas(self):
        try:
            from graphics.canvas import RobotCanvas

            canvas = RobotCanvas()
            canvas.mw = self

            self.canvas_container_layout.removeWidget(self.canvas_status)
            self.canvas_status.setParent(None)
            self.canvas_container_layout.addWidget(canvas, 1)

            self.canvas = canvas
            self._left_container.setEnabled(True)

            self.iso_btn = QtWidgets.QPushButton(self.canvas)
            self.iso_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))
            self.iso_btn.setToolTip("Reset to Isometric View")
            self.iso_btn.setFixedSize(38, 38)
            self.iso_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.iso_btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 19px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                    border-color: #1976d2;
                }
                QPushButton:pressed {
                    background-color: #e3f2fd;
                }
            """)
            self.iso_btn.clicked.connect(lambda: self.canvas.view_isometric())

            # --- Focus Point Button (next to isometric) ---
            self.focus_btn = QtWidgets.QPushButton(self.canvas)
            self.focus_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton))
            self.focus_btn.setToolTip("Set Focus Point - click a surface to zoom in")
            self.focus_btn.setFixedSize(38, 38)
            self.focus_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.focus_btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 19px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                    border-color: #1976d2;
                }
                QPushButton:pressed {
                    background-color: #e3f2fd;
                }
            """)
            self.focus_btn.clicked.connect(lambda: self.canvas.start_focus_point_picking())

            # --- Gripper Surface Button (bottom-right of canvas) ---
            self.gripper_surface_btn = QtWidgets.QPushButton("Select Gripper Surface", self.canvas)
            self.gripper_surface_btn.setToolTip("Click to select the inner surface of the gripper for contact")
            self.gripper_surface_btn.setFixedSize(160, 40)
            self.gripper_surface_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.gripper_surface_btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #2e7d32;
                    border: 2px solid #4caf50;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #e8f5e9;
                }
                QPushButton:pressed {
                    background-color: #c8e6c9;
                }
            """)
            self.gripper_surface_btn.clicked.connect(self.joint_tab.on_select_gripper_surface_only)
            self.gripper_surface_btn.setVisible(False)  # Only visible in Joint Mode

            self.home_position = (0.0, 0.0, 0.0)

            original_resize = self.canvas.resizeEvent

            def patched_resize(event):
                # Call original resize first
                if original_resize:
                    original_resize(event)
                
                # SAFETY: Ensure buttons exist and are initialized
                if not hasattr(self, 'canvas') or self.canvas is None:
                    return
                
                # Check each button before moving it to avoid AttributeErrors during bootstrap
                if hasattr(self, 'iso_btn') and self.iso_btn:
                    self.iso_btn.move(self.canvas.width() - 160, 24)
                
                if hasattr(self, 'focus_btn') and self.focus_btn:
                    self.focus_btn.move(self.canvas.width() - 160, 68)
                
                if hasattr(self, 'gripper_surface_btn') and self.gripper_surface_btn:
                    self.gripper_surface_btn.move(self.canvas.width() - 180, self.canvas.height() - 60)
                
            self.canvas.resizeEvent = patched_resize

            self.canvas.on_drop_callback = self.sync_link_transform
            self.canvas.on_deselect_callback = self.on_deselect

            # Global shortcut so Home works from any panel / mode.
            self.home_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+H"), self)
            self.home_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
            self.home_shortcut.activated.connect(self.go_home)
        except Exception:
            self._left_container.setEnabled(False)
            self._set_canvas_error("Failed to initialize 3D engine.", traceback.format_exc())

    # ------------------------------------------------------------------
    # Global Home Position
    # ------------------------------------------------------------------
    def _resolve_home_tcp_link(self):
        """Resolve the TCP link used for Home navigation."""
        tcp_link = None
        if hasattr(self, 'simulation_tab') and hasattr(self.simulation_tab, '_get_tcp_link'):
            tcp_link = self.simulation_tab._get_tcp_link()

        if not tcp_link:
            for link in self.robot.links.values():
                if link.parent_joint and not link.child_joints:
                    tcp_link = link
                    break

        return tcp_link

    def apply_home_from_fields(self):
        """Set Home XYZ from the fields, rejecting unreachable targets by default."""
        try:
            x = float(self.home_x_spin.value())
            y = float(self.home_y_spin.value())
            z = float(self.home_z_spin.value())

            tcp_link = self._resolve_home_tcp_link()
            if not tcp_link:
                # No arm loaded yet; allow storing values for later.
                self.set_home_coordinates(x, y, z, log_change=True)
                return

            _, local_tool_pt, _ = self.get_link_tool_point(tcp_link)
            ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
            target_world = np.array([x * ratio, y * ratio, z * ratio], dtype=float)

            modifiers = QtWidgets.QApplication.keyboardModifiers()
            force_save = bool(modifiers & QtCore.Qt.ShiftModifier)
            if not force_save and not self._ik_reachable(target_world, tcp_link, local_tool_pt):
                self.log(
                    f"[Home] Update rejected: XYZ unreachable "
                    f"(hold Shift while clicking Update to save anyway)."
                )
                self.show_toast("Home XYZ unreachable", "warning")
                return

            self.set_home_coordinates(x, y, z, log_change=True)
        except Exception as e:
            self.log(f"[Home] Update failed: {e}")
            self.show_toast("Home Update Failed", "error")

    def set_home_to_current_tool(self):
        """Set Home XYZ to the current tool (live point) position."""
        try:
            tcp_link = self._resolve_home_tcp_link()
            if not tcp_link:
                self.log("[Home] Error: No robot arm detected (link with joint needed).")
                self.show_toast("No robot arm detected", "warning")
                return

            pos_world, _, _ = self.get_link_tool_point(tcp_link)
            ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
            pos_cm = np.array(pos_world, dtype=float) / ratio
            self.set_home_coordinates(pos_cm[0], pos_cm[1], pos_cm[2], log_change=True)
            self.show_toast("Home set to current tool position", "success")
        except Exception as e:
            self.log(f"[Home] Set Here failed: {e}")
            self.show_toast("Set Home Failed", "error")

    def get_home_coordinates(self):
        """Return the current Home coordinates in centimeters."""
        if hasattr(self, "home_x") and hasattr(self, "home_y") and hasattr(self, "home_z"):
            return (
                float(self.home_x.value()),
                float(self.home_y.value()),
                float(self.home_z.value()),
            )
        if hasattr(self, "home_x_spin") and hasattr(self, "home_y_spin") and hasattr(self, "home_z_spin"):
            return (
                float(self.home_x_spin.value()),
                float(self.home_y_spin.value()),
                float(self.home_z_spin.value()),
            )
        return (0.0, 0.0, 0.0)

    def set_home_coordinates(self, x, y, z, *, log_change=False):
        """Synchronize the canonical Home coordinates across every visible editor."""
        coords = (float(x), float(y), float(z))
        for names in (
            ("home_x", "home_y", "home_z"),
            ("home_x_spin", "home_y_spin", "home_z_spin"),
        ):
            widgets = [getattr(self, name, None) for name in names]
            if not all(widgets):
                continue
            for widget, value in zip(widgets, coords):
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)

        self.home_position = coords
        if log_change:
            self.log(f"[Home] Coordinates set to X={coords[0]:.2f}, Y={coords[1]:.2f}, Z={coords[2]:.2f} cm")

    def _move_robot_to_world_balanced(self, tcp_link, target_world, tool_local, *, speed_pct=None, label="Home"):
        """Move through a safe lift -> travel -> descend path using IK + FK updates."""
        if tcp_link is None:
            return False

        ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
        speed_pct = float(getattr(self, "current_speed", 50) if speed_pct is None else speed_pct)
        speed_pct = max(20.0, min(speed_pct, 60.0))

        start_world, _, _ = self.get_link_tool_point(tcp_link)
        start_cm = np.array(start_world, dtype=float) / ratio
        target_cm = np.array(target_world, dtype=float) / ratio

        # Try the exact Home target first. In many layouts this is already reachable
        # and avoids over-lifting the arm into an unreachable posture.
        direct_target = target_cm * ratio
        if self._animate_ik_waypoint(
            direct_target,
            tcp_link,
            tool_local,
            speed_pct=speed_pct,
            label=f"{label} direct",
        ):
            return True

        # If the direct solve fails, retry with a few gentler lift heights.
        # Keeping the lift modest prevents the "safe" path from exceeding workspace limits.
        xy_span_cm = float(np.linalg.norm(target_cm[:2] - start_cm[:2]))
        z_span_cm = float(abs(target_cm[2] - start_cm[2]))
        base_lift_cm = max(2.0, min(6.0, 0.12 * xy_span_cm + 0.08 * z_span_cm))
        lift_candidates = [
            base_lift_cm,
            min(6.0, base_lift_cm + 1.5),
            min(8.0, base_lift_cm + 3.0),
        ]

        for attempt_idx, safe_lift_cm in enumerate(lift_candidates, start=1):
            safe_z_cm = max(start_cm[2], target_cm[2]) + safe_lift_cm
            waypoints_cm = [
                np.array([start_cm[0], start_cm[1], safe_z_cm], dtype=float),
                np.array([target_cm[0], target_cm[1], safe_z_cm], dtype=float),
                np.array([target_cm[0], target_cm[1], target_cm[2]], dtype=float),
            ]

            ok = True
            for idx, waypoint_cm in enumerate(waypoints_cm, start=1):
                waypoint_world = waypoint_cm * ratio
                if not self._animate_ik_waypoint(
                    waypoint_world,
                    tcp_link,
                    tool_local,
                    speed_pct=speed_pct,
                    label=f"{label} attempt {attempt_idx} step {idx}/{len(waypoints_cm)}",
                ):
                    ok = False
                    break

            if ok:
                return True

        return False

    def _ik_reachable(self, target_world, tcp_link, tool_local, *, max_iters=900):
        """Check reachability without animating or leaving joint state modified."""
        if tcp_link is None:
            return False

        ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
        start_vals = {n: j.current_value for n, j in self.robot.joints.items()}
        try:
            reached = self.robot.inverse_kinematics(
                target_world,
                tcp_link,
                max_iters=max_iters,
                tolerance=0.5 * ratio,
                tool_offset=tool_local,
            )
        finally:
            for n, v in start_vals.items():
                if n in self.robot.joints:
                    self.robot.joints[n].current_value = v
            self.robot.update_kinematics()
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.update_transforms(self.robot)

        return bool(reached)

    def _clamp_world_target_to_reachable(self, start_world, target_world, tcp_link, tool_local):
        """
        If the exact target is unreachable, binary-search the furthest reachable
        point along the line segment from start_world -> target_world.
        """
        start_world = np.array(start_world, dtype=float)
        target_world = np.array(target_world, dtype=float)

        if self._ik_reachable(target_world, tcp_link, tool_local):
            return target_world

        lo = 0.0
        hi = 1.0
        for _ in range(14):
            mid = (lo + hi) / 2.0
            cand = start_world + (target_world - start_world) * mid
            if self._ik_reachable(cand, tcp_link, tool_local, max_iters=220):
                lo = mid
            else:
                hi = mid

        return start_world + (target_world - start_world) * lo

    def _animate_ik_waypoint(self, target_world, tcp_link, tool_local, *, speed_pct=50.0, label="Target"):
        """Solve IK for one waypoint, then animate the FK transition smoothly."""
        if tcp_link is None:
            return False

        ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
        start_vals = {n: j.current_value for n, j in self.robot.joints.items()}

        reached = self.robot.inverse_kinematics(
            target_world,
            tcp_link,
            max_iters=350,
            tolerance=0.5 * ratio,
            tool_offset=tool_local,
        )
        if not reached:
            for n, v in start_vals.items():
                if n in self.robot.joints:
                    self.robot.joints[n].current_value = v
            self.robot.update_kinematics()
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.update_transforms(self.robot)
            self.log(f"[Home] {label} is unreachable.")
            return False

        target_vals = {n: j.current_value for n, j in self.robot.joints.items()}
        for n, v in start_vals.items():
            if n in self.robot.joints:
                self.robot.joints[n].current_value = v
        self.robot.update_kinematics()
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas.update_transforms(self.robot)

        max_diff = 0.0
        for n, v0 in start_vals.items():
            v1 = target_vals.get(n, v0)
            max_diff = max(max_diff, abs(v1 - v0))

        steps = int(max(8, min(60, max_diff / max(1.0, (101.0 - speed_pct) / 8.0)))) if max_diff > 0.01 else 1
        step_delay = 0.035 if speed_pct >= 45 else 0.05
        if speed_pct < 30:
            step_delay = 0.06

        if hasattr(self, "serial_mgr") and self.serial_mgr.is_connected:
            for name, value in target_vals.items():
                try:
                    self.serial_mgr.send_command(name, float(value), speed=speed_pct)
                except Exception:
                    pass

        for i in range(1, steps + 1):
            a = i / steps
            for n, v0 in start_vals.items():
                j = self.robot.joints.get(n)
                if j is None:
                    continue
                v1 = target_vals.get(n, v0)
                j.current_value = v0 + (v1 - v0) * a

            self.robot.update_kinematics()
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.update_transforms(self.robot)
            self.update_live_ui()
            QtWidgets.QApplication.processEvents()
            time.sleep(step_delay)

        return True

    def go_home(self, *args):
        """
        Move the robot's live point to the configured Home position.
        """
        try:
            x, y, z = self.get_home_coordinates()
            self.set_home_coordinates(x, y, z)

            ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
            target_world = np.array([x * ratio, y * ratio, z * ratio])
            
            self.log(f"[Home] Navigating live point to: X={x:.2f}, Y={y:.2f}, Z={z:.2f}...")

            # 1. Identify TCP (Tool Center Point) Link
            tcp_link = self._resolve_home_tcp_link()
            
            if not tcp_link:
                self.log("[Home] Error: No robot arm detected (link with joint needed).")
                return

            # 2. Get local tool offset (fingertip midpoint or custom offset)
            _, local_tool_pt, _ = self.get_link_tool_point(tcp_link)
            
            # 3. Move through a balanced IK/FK path: lift -> travel -> descend.
            success = self._move_robot_to_world_balanced(
                tcp_link,
                target_world,
                local_tool_pt,
                speed_pct=getattr(self, "current_speed", 50),
                label="Home",
            )

            if success:
                self.log(f"✅ [Home] Successfully moved to Home position.")

                if hasattr(self, "serial_mgr") and self.serial_mgr.is_connected:
                    home_speed = max(float(getattr(self, "current_speed", 50)), 80.0)
                    try:
                        self.serial_mgr.sync_all_to_hardware(speed=home_speed)
                    except Exception as sync_err:
                        self.log(f"[Home] Hardware sync failed: {sync_err}")

                # 4. Global UI Refresh
                if hasattr(self, "canvas") and self.canvas is not None:
                    self.canvas.plotter.render()
                
                # Refresh all active tabs safely
                tabs = [
                    ('joint_tab', 'Joint'),
                    ('simulation_tab', 'Simulation'),
                    ('gripper_tab', 'Gripper')
                ]
                for attr, name in tabs:
                    tab = getattr(self, attr, None)
                    if tab and hasattr(tab, 'refresh_joints'):
                        try:
                            tab.refresh_joints()
                        except Exception as e:
                            print(f"Error refreshing {name} tab: {e}")

                self.update_live_ui()  # Syncs the "LP" row
                    
            else:
                modifiers = QtWidgets.QApplication.keyboardModifiers()
                allow_nearest = bool(modifiers & QtCore.Qt.ShiftModifier)

                # Exact Home is required unless user explicitly requests nearest reachable.
                if not allow_nearest:
                    self.log("[Home] Warning: Could not reach Home position (Out of workspace).")
                    self.show_toast("Home Position Unreachable", "warning")
                    return

                # Clamp the Home target to the nearest reachable point so Home
                # doesn't "always fail" when the stored XYZ is out-of-workspace.
                start_world, _, _ = self.get_link_tool_point(tcp_link)
                clamped_world = self._clamp_world_target_to_reachable(
                    start_world,
                    target_world,
                    tcp_link,
                    local_tool_pt,
                )

                if clamped_world is not None and np.linalg.norm(np.array(clamped_world) - target_world) > 1e-9:
                    ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
                    clamped_cm = np.array(clamped_world, dtype=float) / ratio
                    self.log(
                        f"[Home] Home target unreachable; clamping to reachable point: "
                        f"X={clamped_cm[0]:.2f}, Y={clamped_cm[1]:.2f}, Z={clamped_cm[2]:.2f} cm"
                    )

                    clamped_ok = self._move_robot_to_world_balanced(
                        tcp_link,
                        clamped_world,
                        local_tool_pt,
                        speed_pct=getattr(self, "current_speed", 50),
                        label="Home (clamped)",
                    )
                    if clamped_ok:
                        self.show_toast("Moved to nearest reachable point (Home unchanged)", "info")
                        self.log("[Home] Moved to nearest reachable point.")

                        if hasattr(self, "serial_mgr") and self.serial_mgr.is_connected:
                            home_speed = max(float(getattr(self, "current_speed", 50)), 80.0)
                            try:
                                self.serial_mgr.sync_all_to_hardware(speed=home_speed)
                            except Exception as sync_err:
                                self.log(f"[Home] Hardware sync failed: {sync_err}")

                        if hasattr(self, "canvas") and self.canvas is not None:
                            self.canvas.plotter.render()

                        tabs = [
                            ("joint_tab", "Joint"),
                            ("simulation_tab", "Simulation"),
                            ("gripper_tab", "Gripper"),
                        ]
                        for attr, name in tabs:
                            tab = getattr(self, attr, None)
                            if tab and hasattr(tab, "refresh_joints"):
                                try:
                                    tab.refresh_joints()
                                except Exception as e:
                                    print(f"Error refreshing {name} tab: {e}")

                        self.update_live_ui()
                        return

                self.log(f"⚠️ [Home] Warning: Could not reach Home position (Out of workspace).")
                self.show_toast("Home Position Unreachable", "warning")

        except Exception as e:
            self.log(f"❌ [Home] Critical Error: {str(e)}")
            traceback.print_exc()
            self.show_toast("Home Command Failed", "error")

    def _start_joint_animation(self, joint_ids, child_names, targets):
        if not joint_ids:
            return

        for joint_id, target in zip(joint_ids, targets):
            joint = self.robot.joints.get(joint_id)
            if joint is not None:
                joint.current_value = float(target)

        self.robot.update_kinematics()
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas.update_transforms(self.robot)

        if hasattr(self, "joint_tab"):
            for child_name, target in zip(child_names, targets):
                try:
                    self.joint_tab.apply_joint_rotation(child_name, float(target))
                except Exception:
                    pass

        if hasattr(self, "matrices_tab"):
            for child_name, target in zip(child_names, targets):
                try:
                    self.matrices_tab.sync_slider(child_name, float(target))
                except Exception:
                    pass

        if hasattr(self, "simulation_tab") and hasattr(self.simulation_tab, "update_display"):
            try:
                self.simulation_tab.update_display()
            except Exception:
                pass

        self.update_live_ui()

    def _move_tcp_to_xyz(self, x, y, z, tcp_link):
        if tcp_link is None:
            return False

        ratio = self.canvas.grid_units_per_cm if hasattr(self, "canvas") and self.canvas is not None else 10.0
        target_world = np.array([x * ratio, y * ratio, z * ratio], dtype=float)
        try:
            _, tool_local, _ = self.get_link_tool_point(tcp_link, return_vec=True)
            reached = self.robot.inverse_kinematics(
                target_world,
                tcp_link,
                max_iters=300,
                tolerance=0.5 * ratio,
                tool_offset=tool_local,
            )
            self.robot.update_kinematics()
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.update_transforms(self.robot)
            self.update_live_ui()
            return bool(reached)
        except Exception:
            traceback.print_exc()
            return False

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
