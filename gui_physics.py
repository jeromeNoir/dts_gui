"""gui_physics.py -- Advanced > Physical parameters window of the DTS GUI.

The window is built from dts_core.PHYSICAL_PARAMETERS: a new physical
parameter added to that list appears here without any change to this file.
The values are stored in dts_core.PHYSICS and used by every step at run
time (the steps already run keep their results until they are run again).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

import dts_core as core


def _text(value):
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


class PhysicsDialog(QDialog):
    """Non-modal window: see and change the physical parameters."""

    applied = Signal(list)        # names of the parameters that changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Physical parameters")
        self.resize(560, 720)
        self.inputs = {}           # name -> (widget, kind)
        self.mode_rows = []        # (widget, label, mode) shown per mode
        outer = QVBoxLayout(self)
        intro = QLabel(
            "Physical parameters used by the steps. Press <b>Apply</b> to "
            "use the new values; the steps already run keep their results "
            "until they are run again. The values are saved with the "
            "analysis settings.")
        intro.setWordWrap(True)
        outer.addWidget(intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        groups = {}
        for name, label, unit, default, group, kind, extra in \
                core.PHYSICAL_PARAMETERS:
            if group not in groups:
                box = QGroupBox(group)
                groups[group] = QFormLayout(box)
                body_layout.addWidget(box)
            form = groups[group]
            if kind == "choice":
                widget = QComboBox()
                widget.addItems(extra["choices"])
            else:
                widget = QLineEdit()
                widget.setAlignment(Qt.AlignRight)
                widget.setMaximumWidth(140)
            tip = extra.get("help", "")
            tip += f"\n(default: {_text(default)}{' ' + unit if unit else ''})"
            widget.setToolTip(tip.strip())
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(widget)
            if unit:
                row_layout.addWidget(QLabel(unit))
            row_layout.addStretch(1)
            caption = QLabel(label)
            caption.setToolTip(tip.strip())
            form.addRow(caption, row)
            self.inputs[name] = (widget, kind)
            if extra.get("mode"):
                self.mode_rows.append((row, caption, extra["mode"]))
        body_layout.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        outer.addWidget(self.message)
        buttons = QHBoxLayout()
        defaults = QPushButton("Reset to defaults")
        defaults.clicked.connect(self.reset_defaults)
        apply_button = QPushButton("Apply")
        apply_button.setStyleSheet("font-weight: bold; padding: 4px 16px;")
        apply_button.clicked.connect(self.apply)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        buttons.addWidget(defaults)
        buttons.addStretch(1)
        buttons.addWidget(apply_button)
        buttons.addWidget(close)
        outer.addLayout(buttons)
        self.inputs["EOS_MODE"][0].currentTextChanged.connect(
            self.update_modes)
        self.load(core.PHYSICS)

    def load(self, values):
        for name, (widget, kind) in self.inputs.items():
            value = values.get(name, core.PHYSICS_DEFAULTS[name])
            if kind == "choice":
                widget.setCurrentText(str(value))
            else:
                widget.setText(_text(value))
        self.update_modes()
        self.message.setText("")

    def update_modes(self, *_):
        """Show only the inputs of the density mode chosen."""
        mode = self.inputs["EOS_MODE"][0].currentText()
        for row, caption, wanted in self.mode_rows:
            row.setVisible(wanted == mode)
            caption.setVisible(wanted == mode)

    def values(self):
        """The values typed; raises ValueError on a number that cannot be
        read."""
        out = {}
        for name, (widget, kind) in self.inputs.items():
            if kind == "choice":
                out[name] = widget.currentText()
                continue
            text = widget.text().strip().replace(",", ".")
            try:
                out[name] = float(text)
            except ValueError:
                raise ValueError(f"{name}: '{widget.text()}' is not a "
                                 f"number") from None
        return out

    def apply(self):
        try:
            values = self.values()
        except ValueError as error:
            self.message.setText(f"<span style='color:#D55E00'>{error}"
                                 "</span>")
            return
        changed = core.set_physics(values)
        self.message.setText(
            ("changed: " + ", ".join(changed) + " — run the steps again to "
             "use the new values") if changed else "no change")
        self.applied.emit(changed)

    def reset_defaults(self):
        self.load(core.PHYSICS_DEFAULTS)
        self.message.setText("defaults shown: press Apply to use them")
