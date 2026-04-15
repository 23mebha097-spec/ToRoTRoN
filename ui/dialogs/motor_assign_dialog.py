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
        self._result: dict[str, str] = {}

        self.setWindowTitle("Motor Assignment")
        self.setModal(True)
        self.setMinimumWidth(560)
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

        # ── Title row (no banner — just a clean heading inside body) ─────────
        title_bar = QtWidgets.QWidget()
        title_bar.setStyleSheet(f"background: white; border-bottom: 2px solid {self._BLUE};")
        title_bar.setFixedHeight(62)
        tb_lay = QtWidgets.QHBoxLayout(title_bar)
        tb_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QtWidgets.QLabel("Motor Assignment")
        title_lbl.setStyleSheet(f"""
            color: {self._BLUE};
            font-size: 20px;
            font-weight: bold;
            font-family: {self._FONT_FAMILY};
            background: transparent;
        """)
        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()

        sub_lbl = QtWidgets.QLabel("Select motor type per joint")
        sub_lbl.setStyleSheet(f"""
            color: #757575;
            font-size: 13px;
            background: transparent;
        """)
        tb_lay.addWidget(sub_lbl)
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
            QPushButton:pressed {{
                background: #0d47a1;
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

        # Resize dialog to fit rows (max 8 visible without scroll)
        row_h = 68
        visible = min(len(joint_names), 8)
        self._rows_widget.setMinimumHeight(visible * row_h)
        self.setMinimumHeight(62 + visible * row_h + 72)

    def _build_row(self, joint_name: str, index: int) -> QtWidgets.QWidget:
        is_even = (index % 2 == 0)
        bg = "white" if is_even else self._GREY_BG

        row = QtWidgets.QWidget()
        row.setFixedHeight(68)
        row.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border-bottom: 1px solid {self._BORDER};
            }}
        """)

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
            font-family: {self._FONT_FAMILY};
        """)
        lay.addWidget(badge)

        # ── Joint name ────────────────────────────────────────────────────
        name_lbl = QtWidgets.QLabel(joint_name)
        name_lbl.setStyleSheet(f"""
            color: {self._TEXT};
            font-size: 17px;
            font-weight: bold;
            font-family: {self._FONT_FAMILY};
            background: transparent;
        """)
        lay.addWidget(name_lbl, 1)

        # ── Toggle button pair ────────────────────────────────────────────
        btn_servo   = self._make_toggle_btn("Servo",   "servo")
        btn_stepper = self._make_toggle_btn("Stepper", "stepper")

        self._btns[joint_name] = {"servo": btn_servo, "stepper": btn_stepper}

        # Default selection (restore from previous session)
        default = self._prev.get(joint_name, "servo").lower()
        self._selection[joint_name] = default
        self._apply_selection(joint_name, default)

        btn_servo.clicked.connect(
            lambda _, jn=joint_name: self._select(jn, "servo")
        )
        btn_stepper.clicked.connect(
            lambda _, jn=joint_name: self._select(jn, "stepper")
        )

        btn_group = QtWidgets.QWidget()
        btn_group.setStyleSheet("background: transparent;")
        btn_group_lay = QtWidgets.QHBoxLayout(btn_group)
        btn_group_lay.setContentsMargins(0, 0, 0, 0)
        btn_group_lay.setSpacing(0)
        btn_group_lay.addWidget(btn_servo)
        btn_group_lay.addWidget(btn_stepper)

        lay.addWidget(btn_group)
        return row

    def _make_toggle_btn(self, label: str, mtype: str) -> QtWidgets.QPushButton:
        """Creates an unstyled toggle button; style applied via _apply_selection."""
        btn = QtWidgets.QPushButton(label)
        btn.setFixedSize(110, 40)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setCheckable(True)
        # Base style applied immediately; selection highlights via _apply_selection
        return btn

    # ─────────────────────────────────────────────────────────────────────────
    # Selection logic
    # ─────────────────────────────────────────────────────────────────────────

    def _select(self, joint_name: str, mtype: str):
        self._selection[joint_name] = mtype
        self._apply_selection(joint_name, mtype)

    def _apply_selection(self, joint_name: str, selected: str):
        """Applies filled/outlined styles based on which type is selected."""
        btns = self._btns[joint_name]

        for mtype, btn in btns.items():
            is_sel = (mtype == selected)
            btn.blockSignals(True)
            btn.setChecked(is_sel)
            btn.blockSignals(False)
            btn.setStyleSheet(self._btn_style(mtype, is_sel))

    def _btn_style(self, mtype: str, selected: bool) -> str:
        if mtype == "servo":
            sel_bg     = self._BLUE
            sel_border = self._BLUE_DARK
            sel_text   = "white"
            hover_bg   = self._BLUE_LIGHT
            hover_text = self._BLUE
            radius_l   = "8px"
            radius_r   = "0px"
        else:
            sel_bg     = self._SLATE
            sel_border = self._SLATE_DARK
            sel_text   = "white"
            hover_bg   = self._SLATE_LIGHT
            hover_text = self._SLATE
            radius_l   = "0px"
            radius_r   = "8px"

        if selected:
            return f"""
                QPushButton {{
                    background: {sel_bg};
                    color: {sel_text};
                    border: 2px solid {sel_border};
                    border-top-left-radius:     {radius_l};
                    border-bottom-left-radius:  {radius_l};
                    border-top-right-radius:    {radius_r};
                    border-bottom-right-radius: {radius_r};
                    font-size: 15px;
                    font-weight: bold;
                    font-family: {self._FONT_FAMILY};
                }}
            """
        else:
            border_color = self._BLUE if mtype == "servo" else self._SLATE
            return f"""
                QPushButton {{
                    background: white;
                    color: #757575;
                    border: 2px solid {self._BORDER};
                    border-top-left-radius:     {radius_l};
                    border-bottom-left-radius:  {radius_l};
                    border-top-right-radius:    {radius_r};
                    border-bottom-right-radius: {radius_r};
                    font-size: 15px;
                    font-weight: bold;
                    font-family: {self._FONT_FAMILY};
                }}
                QPushButton:hover {{
                    background: {hover_bg};
                    color: {hover_text};
                    border-color: {border_color};
                }}
            """

    # ─────────────────────────────────────────────────────────────────────────
    # Accept / result
    # ─────────────────────────────────────────────────────────────────────────

    def _on_accept(self):
        self._result = dict(self._selection)
        self.accept()

    def get_assignments(self) -> dict:
        """
        Returns {joint_name: "servo" | "stepper"}.
        Valid only after dialog.exec_() == QDialog.Accepted.
        """
        return dict(self._result)
