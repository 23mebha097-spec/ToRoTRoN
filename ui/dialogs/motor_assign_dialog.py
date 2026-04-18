from PyQt5 import QtWidgets, QtCore, QtGui


class MotorAssignDialog(QtWidgets.QDialog):
    """
    Motor type assignment dialog.

    Each independent joint shows two toggle buttons:
        [  Servo  ]  [  Stepper  ]

    Clicking a button selects that motor type with a clear
    visual fill effect. Matches the ToRoTRoN blue/white UI theme.

    Usage
    -----
        dlg = MotorAssignDialog(robot, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            assignments = dlg.get_assignments()
            # -> {"Joint1": "servo", "Joint2": "stepper", ...}
    """

    # ── Style constants (match main_window.py apply_styles) ──────────────────
    _FONT_FAMILY = "'Segoe UI', Roboto, sans-serif"
    _BLUE        = "#1976d2"
    _BLUE_DARK   = "#1565c0"
    _BLUE_LIGHT  = "#e3f2fd"
    _SLATE       = "#37474f"   # Blue Grey 800  — stepper (selected)
    _SLATE_DARK  = "#263238"   # Blue Grey 900  — stepper hover/border
    _SLATE_LIGHT = "#eceff1"   # Blue Grey 50   — stepper hover bg
    _TEXT        = "#212121"
    _GREY_BG     = "#f5f5f5"
    _BORDER      = "#e0e0e0"

    def __init__(self, robot, parent=None, previous_assignments=None):
        super().__init__(parent)
        self.robot    = robot
        self._prev    = previous_assignments or {}
        # maps joint_name → ("servo"|"stepper")
        self._selection: dict[str, str] = {}
        # maps joint_name → {"servo": QPushButton, "stepper": QPushButton}
        self._btns: dict[str, dict] = {}
        # maps joint_name → QWidget (the config area)
        self._config_widgets: dict[str, QtWidgets.QWidget] = {}
        # maps joint_name → detailed config (gear_ratio, servo_type, etc)
        self._configs: dict[str, dict] = {}
        
        self._result: dict[str, dict] = {}

        self.setWindowTitle("Motor & Firmware Config")
        self.setModal(True)
        self.setMinimumWidth(720) # Wider to accommodate config columns
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowCloseButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background: white;
                font-family: {self._FONT_FAMILY};
            }}
        """)

        self._build_ui()
        self._populate_joints()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Build
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title row ────────────────────────────────────────────────────────
        title_bar = QtWidgets.QWidget()
        title_bar.setStyleSheet(f"background: white; border-bottom: 2px solid {self._BLUE};")
        title_bar.setFixedHeight(70)
        tb_lay = QtWidgets.QHBoxLayout(title_bar)
        tb_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QtWidgets.QLabel("Firmware Configuration")
        title_lbl.setStyleSheet(f"""
            color: {self._BLUE};
            font-size: 20px;
            font-weight: bold;
            font-family: {self._FONT_FAMILY};
            background: transparent;
        """)
        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()

        headers = QtWidgets.QWidget()
        headers.setStyleSheet("background: transparent;")
        h_lay = QtWidgets.QHBoxLayout(headers)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(40)
        
        type_h = QtWidgets.QLabel("Motor Type")
        type_h.setFixedWidth(220)
        type_h.setAlignment(QtCore.Qt.AlignCenter)
        config_h = QtWidgets.QLabel("Detailed Config")
        config_h.setFixedWidth(180)
        config_h.setAlignment(QtCore.Qt.AlignCenter)
        
        for lbl in [type_h, config_h]:
            lbl.setStyleSheet("color: #757575; font-size: 11px; font-weight: bold; text-transform: uppercase;")
            h_lay.addWidget(lbl)
            
        tb_lay.addWidget(headers)
        root.addWidget(title_bar)

        # ── Scrollable joint rows ─────────────────────────────────────────────
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: white; border: none; }")

        self._rows_widget = QtWidgets.QWidget()
        self._rows_widget.setStyleSheet("background: white;")
        self._rows_layout = QtWidgets.QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch()

        scroll.setWidget(self._rows_widget)
        root.addWidget(scroll, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QtWidgets.QWidget()
        footer.setFixedHeight(72)
        footer.setStyleSheet(f"""
            QWidget {{
                background: {self._GREY_BG};
                border-top: 1px solid {self._BORDER};
            }}
        """)
        ft_lay = QtWidgets.QHBoxLayout(footer)
        ft_lay.setContentsMargins(24, 12, 24, 12)
        ft_lay.setSpacing(12)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFixedHeight(46)
        cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {self._TEXT};
                border: 2px solid {self._BORDER};
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                padding: 0 28px;
                font-family: {self._FONT_FAMILY};
            }}
            QPushButton:hover {{
                border-color: {self._BLUE};
                color: {self._BLUE};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self.generate_btn = QtWidgets.QPushButton("  Generate Firmware")
        self.generate_btn.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton)
        )
        self.generate_btn.setFixedHeight(46)
        self.generate_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                padding: 0 32px;
                font-family: {self._FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: {self._BLUE_DARK};
            }}
        """)
        self.generate_btn.clicked.connect(self._on_accept)

        ft_lay.addWidget(cancel_btn)
        ft_lay.addStretch()
        ft_lay.addWidget(self.generate_btn)
        root.addWidget(footer)

    # ─────────────────────────────────────────────────────────────────────────
    # Populate
    # ─────────────────────────────────────────────────────────────────────────

    def _get_independent_joints(self):
        slave_ids = set()
        for slaves in self.robot.joint_relations.values():
            for s_id, _ in slaves:
                slave_ids.add(s_id)
        return [n for n in self.robot.joints if n not in slave_ids]

    def _populate_joints(self):
        joint_names = self._get_independent_joints()

        if not joint_names:
            msg = QtWidgets.QLabel("No independent joints defined.\nAdd joints first.")
            msg.setAlignment(QtCore.Qt.AlignCenter)
            msg.setStyleSheet(f"color: #9e9e9e; font-size: 16px; padding: 40px;")
            self._rows_layout.insertWidget(0, msg)
            self.generate_btn.setEnabled(False)
            return

        for i, name in enumerate(joint_names):
            row = self._build_row(name, i)
            self._rows_layout.insertWidget(i, row)

        # Resize dialog
        row_h = 74
        visible = min(len(joint_names), 8)
        self._rows_widget.setMinimumHeight(visible * row_h)
        self.setMinimumHeight(70 + visible * row_h + 72)

    def _build_row(self, joint_name: str, index: int) -> QtWidgets.QWidget:
        is_even = (index % 2 == 0)
        bg = "white" if is_even else self._GREY_BG

        row = QtWidgets.QWidget()
        row.setFixedHeight(74)
        row.setStyleSheet(f"QWidget {{ background: {bg}; border-bottom: 1px solid {self._BORDER}; }}")

        lay = QtWidgets.QHBoxLayout(row)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(14)

        # ── Index badge ────────────────────────────────────────────────────
        badge = QtWidgets.QLabel(f"J{index + 1}")
        badge.setFixedSize(34, 34)
        badge.setAlignment(QtCore.Qt.AlignCenter)
        badge.setStyleSheet(f"""
            background: {self._BLUE_LIGHT};
            color: {self._BLUE};
            border-radius: 17px;
            font-size: 13px;
            font-weight: bold;
        """)
        lay.addWidget(badge)

        # ── Joint name ────────────────────────────────────────────────────
        name_lbl = QtWidgets.QLabel(joint_name)
        name_lbl.setStyleSheet(f"color: {self._TEXT}; font-size: 16px; font-weight: bold;")
        lay.addWidget(name_lbl, 1)

        # ── Toggle button pair ────────────────────────────────────────────
        btn_servo   = self._make_toggle_btn("Servo",   "servo")
        btn_stepper = self._make_toggle_btn("Stepper", "stepper")
        self._btns[joint_name] = {"servo": btn_servo, "stepper": btn_stepper}

        btn_group = QtWidgets.QWidget()
        btn_group.setFixedWidth(220)
        bg_lay = QtWidgets.QHBoxLayout(btn_group)
        bg_lay.setContentsMargins(0, 0, 0, 0)
        bg_lay.setSpacing(0)
        bg_lay.addWidget(btn_servo)
        bg_lay.addWidget(btn_stepper)
        lay.addWidget(btn_group)

        # ── Configuration Slot (Stepper Gear Ratio or Servo Type) ─────────
        config_slot = QtWidgets.QStackedWidget()
        config_slot.setFixedWidth(180)
        
        # 1. Stepper Config (Ratio)
        self.stepper_config = QtWidgets.QWidget()
        sc_lay = QtWidgets.QHBoxLayout(self.stepper_config)
        sc_lay.setContentsMargins(10, 0, 0, 0)
        sc_lay.setSpacing(5)
        
        lbl_ratio = QtWidgets.QLabel(" Ratio 1:")
        lbl_ratio.setStyleSheet("color: #757575; font-size: 11px;")
        
        ratio_sb = QtWidgets.QDoubleSpinBox()
        ratio_sb.setRange(0.1, 100.0)
        ratio_sb.setValue(1.0)
        ratio_sb.setSingleStep(0.1)
        ratio_sb.setFixedHeight(32)
        ratio_sb.setStyleSheet("""
            QDoubleSpinBox { border: 1px solid #ddd; border-radius: 4px; padding-left: 5px; font-weight: bold; }
        """)
        
        sc_lay.addWidget(lbl_ratio)
        sc_lay.addWidget(ratio_sb)
        
        # 2. Servo Config (Type)
        self.servo_config = QtWidgets.QWidget()
        sv_lay = QtWidgets.QHBoxLayout(self.servo_config)
        sv_lay.setContentsMargins(10, 0, 0, 0)
        
        type_cb = QtWidgets.QComboBox()
        type_cb.addItems(["Standard (0-180)", "Continuous"])
        type_cb.setFixedHeight(32)
        type_cb.setStyleSheet("""
            QComboBox { border: 1px solid #ddd; border-radius: 4px; padding-left: 5px; font-size: 12px; }
            QComboBox::drop-down { border: none; }
        """)
        sv_lay.addWidget(type_cb)

        config_slot.addWidget(self.servo_config)   # Index 0
        config_slot.addWidget(self.stepper_config) # Index 1
        lay.addWidget(config_slot)
        
        self._config_widgets[joint_name] = config_slot
        self._configs[joint_name] = {"ratio_sb": ratio_sb, "type_cb": type_cb}

        # Interaction
        btn_servo.clicked.connect(lambda _, jn=joint_name: self._select(jn, "servo"))
        btn_stepper.clicked.connect(lambda _, jn=joint_name: self._select(jn, "stepper"))

        # Restore
        prev_data = self._prev.get(joint_name, {})
        if isinstance(prev_data, str): 
            mtype = prev_data.lower()
        else:
            mtype = prev_data.get("type", "servo").lower()
            if mtype == "stepper": ratio_sb.setValue(prev_data.get("gear_ratio", 1.0))
            if mtype == "servo": type_cb.setCurrentText(prev_data.get("servo_mode", "Standard (0-180)"))

        self._selection[joint_name] = mtype
        self._apply_selection(joint_name, mtype)
        
        return row

    def _make_toggle_btn(self, label: str, mtype: str) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(label)
        btn.setFixedSize(110, 40)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setCheckable(True)
        return btn

    def _select(self, joint_name: str, mtype: str):
        self._selection[joint_name] = mtype
        self._apply_selection(joint_name, mtype)
        
        # Switch config UI
        stack = self._config_widgets[joint_name]
        stack.setCurrentIndex(1 if mtype == "stepper" else 0)

    def _apply_selection(self, joint_name: str, selected: str):
        btns = self._btns[joint_name]
        for mtype, btn in btns.items():
            is_sel = (mtype == selected)
            btn.blockSignals(True)
            btn.setChecked(is_sel)
            btn.blockSignals(False)
            btn.setStyleSheet(self._btn_style(mtype, is_sel))
        
        stack = self._config_widgets[joint_name]
        stack.setCurrentIndex(1 if selected == "stepper" else 0)

    def _btn_style(self, mtype: str, selected: bool) -> str:
        if mtype == "servo":
            sel_bg, sel_border, hover_bg, radius_l, radius_r = self._BLUE, self._BLUE_DARK, self._BLUE_LIGHT, "8px", "0px"
        else:
            sel_bg, sel_border, hover_bg, radius_l, radius_r = self._SLATE, self._SLATE_DARK, self._SLATE_LIGHT, "0px", "8px"

        if selected:
            return f"QPushButton {{ background: {sel_bg}; color: white; border: 2px solid {sel_border}; border-top-left-radius: {radius_l}; border-bottom-left-radius: {radius_l}; border-top-right-radius: {radius_r}; border-bottom-right-radius: {radius_r}; font-size: 14px; font-weight: bold; }}"
        else:
            border_c = self._BLUE if mtype == "servo" else self._SLATE
            return f"QPushButton {{ background: white; color: #757575; border: 2px solid {self._BORDER}; border-top-left-radius: {radius_l}; border-bottom-left-radius: {radius_l}; border-top-right-radius: {radius_r}; border-bottom-right-radius: {radius_r}; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background: {hover_bg}; color: {border_c}; border-color: {border_c}; }}"

    def _on_accept(self):
        self._result = {}
        for name, mtype in self._selection.items():
            conf = self._configs[name]
            if mtype == "stepper":
                self._result[name] = {"type": "stepper", "gear_ratio": conf["ratio_sb"].value()}
            else:
                self._result[name] = {"type": "servo", "servo_mode": conf["type_cb"].currentText()}
        self.accept()

    def get_assignments(self) -> dict:
        return dict(self._result)

