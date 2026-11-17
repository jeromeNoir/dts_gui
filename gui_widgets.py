"""Widgets of the DTS GUI: the input panel of a step (left) and the figure
panel (right).  Every input widget has value() and set_value()."""

import os

import numpy as np

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDateTimeEdit,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton,
    QRadioButton, QScrollArea, QSpinBox, QStyledItemDelegate,
    QStyleOptionViewItem, QTabWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import (FigureCanvasQTAgg,
                                               NavigationToolbar2QT)

DATETIME_FORMAT = "yyyy-MM-dd HH:mm:ss"


# ---------------------------------------------------------------------------
# input widgets
# ---------------------------------------------------------------------------
class PathField(QWidget):
    """Folder path: line edit + browse button (may be left empty)."""

    changed = Signal()

    def __init__(self, default, placeholder=""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(default or "")
        self.edit.setPlaceholderText(placeholder)
        self.edit.setCursorPosition(0)
        self.edit.editingFinished.connect(self.changed)
        button = QToolButton(text="…")
        button.clicked.connect(self._browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a folder",
                                                self.edit.text())
        if path:
            self.edit.setText(path)
            self.changed.emit()

    def value(self):
        return self.edit.text().strip()

    def set_value(self, value):
        self.edit.setText(value or "")
        self.changed.emit()


class PathListField(QWidget):
    """List of folders with add / remove buttons."""

    def __init__(self, default):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setMaximumHeight(90)
        buttons = QHBoxLayout()
        add, remove = QPushButton("Add…"), QPushButton("Remove")
        add.clicked.connect(self._add)
        remove.clicked.connect(lambda: [
            self.list.takeItem(self.list.row(item))
            for item in self.list.selectedItems()])
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.set_value(default)

    def _append(self, path):
        item = QListWidgetItem(os.path.basename(os.path.normpath(path)))
        item.setToolTip(path)
        item.setData(Qt.UserRole, path)
        self.list.addItem(item)

    def _add(self):
        start = self.value()[-1] if self.value() else ""
        path = QFileDialog.getExistingDirectory(
            self, "Add a configuration folder", os.path.dirname(start))
        if path:
            self._append(path)

    def value(self):
        return [self.list.item(i).data(Qt.UserRole)
                for i in range(self.list.count())]

    def set_value(self, paths):
        self.list.clear()
        for path in paths or []:
            self._append(path)


def float_spin(field):
    spin = QDoubleSpinBox()
    decimals = field.get("decimals", 2)
    spin.setDecimals(decimals)
    spin.setRange(field.get("minimum", -1e6), field.get("maximum", 1e6))
    spin.setSingleStep(10 ** (1 - decimals))
    if field.get("default") is not None:
        spin.setValue(field["default"])
    if field.get("unit"):
        spin.setSuffix(" " + field["unit"])
    return spin


class FloatField(QWidget):
    """Float spin box; with optional=True an 'auto' box gives None."""

    def __init__(self, field):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.spin = float_spin(field)
        layout.addWidget(self.spin, 1)
        self.auto = None
        if field.get("optional"):
            self.auto = QCheckBox(field.get("auto_text", "auto"))
            self.auto.toggled.connect(lambda on: self.spin.setEnabled(not on))
            self.auto.setChecked(field.get("auto_default",
                                           field.get("default") is None))
            self.spin.setEnabled(not self.auto.isChecked())
            layout.addWidget(self.auto)

    def value(self):
        if self.auto is not None and self.auto.isChecked():
            return None
        return self.spin.value()

    def set_value(self, value):
        if value is None and self.auto is not None:
            self.auto.setChecked(True)
            return
        if self.auto is not None:
            self.auto.setChecked(False)
        self.spin.setValue(float(value))


class DateTimeField(QWidget):
    """Date and time; with optional=True a 'none' box gives None."""

    def __init__(self, field):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QDateTimeEdit()
        self.edit.setDisplayFormat("dd.MM.yyyy HH:mm:ss")
        self.edit.setCalendarPopup(True)
        self.edit.setDateTime(QDateTime.fromString(
            field.get("default") or "2026-11-01 00:00:00", DATETIME_FORMAT))
        layout.addWidget(self.edit, 1)
        self.none = None
        if field.get("optional"):
            self.none = QCheckBox(field.get("none_text", "none"))
            self.none.setToolTip(field.get(
                "tip", "Checked = no limit (start / end of the record)"))
            self.none.toggled.connect(lambda on: self.edit.setEnabled(not on))
            self.none.setChecked(field.get("default") is None)
            layout.addWidget(self.none)

    def value(self):
        if self.none is not None and self.none.isChecked():
            return None
        return self.edit.dateTime().toString(DATETIME_FORMAT)

    def set_value(self, value):
        if value is None and self.none is not None:
            self.none.setChecked(True)
            return
        if self.none is not None:
            self.none.setChecked(False)
        self.edit.setDateTime(QDateTime.fromString(value, DATETIME_FORMAT))


def temperature_root(root):
    """Temperature folder of the XT (a root given as the XT data folder is
    accepted: its 'temperature' sub-folder is used)."""
    root = os.path.normpath(root or "")
    inner = os.path.join(root, "temperature")
    if os.path.basename(root) != "temperature" and os.path.isdir(inner):
        return inner
    return root


# called with a channel name when its (?) button is clicked (set by the GUI)
CHANNEL_INFO_HANDLER = None
CHANNELS_PER_ROW = 3


HELP_EXTRA = {}       # field name -> function giving text added on click


def _help_button(title, text, name=None):
    """(?) in a circle next to an input: a short explanation (plus, for some
    inputs, a text computed when it is clicked, see HELP_EXTRA)."""
    from PySide6.QtWidgets import QToolButton, QMessageBox

    def show(checked=False):
        message = text
        extra = HELP_EXTRA.get(name)
        if extra is not None:
            try:
                added = extra()
            except Exception as error:              # noqa: BLE001
                added = f"(not available: {error})"
            if added:
                message = f"{text}\n\n{added}"
        QMessageBox.information(button.window(), title, message)

    button = _info_button(title)
    button.clicked.disconnect()
    button.setToolTip(text)
    button.clicked.connect(show)
    return button


def _info_button(name):
    """Small (?) button next to a channel: how the channel is built."""
    from PySide6.QtWidgets import QToolButton
    button = QToolButton()
    button.setText("?")
    button.setFixedSize(16, 16)
    button.setStyleSheet(
        "QToolButton { border: 1.5px solid #0072B2; border-radius: 8px; "
        "color: #0072B2; font-weight: bold; font-size: 10px; padding: 0px; "
        "background: transparent; } "
        "QToolButton:hover { background: #0072B2; color: white; }")
    button.setToolTip(f"How '{name}' is built")
    button.clicked.connect(
        lambda checked=False, n=name: CHANNEL_INFO_HANDLER
        and CHANNEL_INFO_HANDLER(n))
    return button


def _channel_cell(widget, name):
    cell = QWidget()
    layout = QHBoxLayout(cell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)                 # room between the name and (?)
    layout.addWidget(widget)
    layout.addWidget(_info_button(name))
    return cell


def _place_cells(layout, cells):
    """Rows of CHANNELS_PER_ROW channel cells, packed to the left with an
    even spacing (no column alignment, which left gaps when a long name
    sat in another row); returns the row widgets."""
    rows = []
    for start in range(0, len(cells), CHANNELS_PER_ROW):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(14)            # between two channels
        for cell in cells[start:start + CHANNELS_PER_ROW]:
            row_layout.addWidget(cell)
        row_layout.addStretch(1)
        layout.addWidget(row)
        rows.append(row)
    return rows


def _old_names(names):
    """Channel names of settings saved before 2.37 ('channel n', 'mean')."""
    from channel_names import display_name
    if isinstance(names, str):
        return display_name(names)
    return [display_name(n) for n in (names or [])]


class ChannelBoxes(QWidget):
    """One check box per channel, with a (?) button (grid of 3 columns).
    ``changed`` is emitted when the user ticks or unticks a box."""

    changed = Signal()

    def __init__(self, choices, default):
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(4)
        self.boxes = {}
        self.cells = []
        self.set_choices(choices, default)

    def set_choices(self, choices, checked=None):
        if checked is None:
            checked = self.value() if self.boxes else choices
        for cell in self.cells:
            cell.setParent(None)             # removed at once from the panel
            cell.deleteLater()
        self.boxes, self.cells, cells = {}, [], []
        for index, name in enumerate(choices):
            box = QCheckBox(name)
            box.setChecked(name in checked or not checked)
            box.clicked.connect(lambda *_: self.changed.emit())
            self.boxes[name] = box
            cells.append(_channel_cell(box, name))
        self.cells = _place_cells(self.layout_, cells)

    def value(self):
        return [name for name, box in self.boxes.items() if box.isChecked()]

    def set_value(self, names):
        names = _old_names(names)
        missing = [n for n in (names or []) if n not in self.boxes]
        if missing:                       # e.g. settings of another record
            self.set_choices(list(names) + [n for n in self.boxes
                                            if n not in names], list(names))
        for name, box in self.boxes.items():
            box.setChecked(name in (names or []))


_PRODUCT_CACHE = {}


def preprocessed_files(folder):
    """Names of the preprocessed files (.nc with at least one group holding
    T_calibrated) of a configuration folder, DTS_preprocessed.nc first."""
    import netCDF4
    found = []
    try:
        names = sorted(n for n in os.listdir(folder)
                       if n.lower().endswith(".nc"))
    except OSError:
        return found
    for name in names:
        path = os.path.join(folder, name)
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            continue
        cached = _PRODUCT_CACHE.get(path)
        if cached is None or cached[0] != stamp:
            try:
                with netCDF4.Dataset(path) as handle:
                    ok = any("T_calibrated" in group.variables
                             for group in handle.groups.values())
            except Exception:
                ok = False
            _PRODUCT_CACHE[path] = cached = (stamp, ok)
        if cached[1]:
            found.append(name)
    found.sort(key=lambda n: (n != ProductList.PRODUCT, n))
    return found


class ProductList(QWidget):
    """Drop-down list of the configurations of a root folder that hold a
    preprocessed file (DTS_preprocessed.nc or another name).  value() is a
    one-item list (the configuration chosen), as the step expects."""

    PRODUCT = "DTS_preprocessed.nc"
    changed = Signal()

    def __init__(self, default):
        super().__init__()
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo.currentTextChanged.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.combo, 0, Qt.AlignLeft)
        self.note = QLabel("")
        self.note.setStyleSheet("color: gray;")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.root = ""
        self.wanted = list(default or [])

    def refresh(self, root):
        """List the sub-folders of ``root`` holding a preprocessed file."""
        if self.combo.count():
            self.wanted = self.value()
        self.root = root or ""
        names = []
        if os.path.isdir(self.root):
            names = sorted(n for n in os.listdir(self.root)
                           if os.path.isdir(os.path.join(self.root, n))
                           and preprocessed_files(os.path.join(self.root,
                                                               n)))
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(names)
        target = next((n for n in self.wanted if n in names), None)
        if target:
            self.combo.setCurrentText(target)
        self.combo.blockSignals(False)
        self.note.setText(
            f"{len(names)} configuration(s) found" if names else
            ("no configuration with a preprocessed file in this folder"
             if os.path.isdir(self.root) else "folder not found"))
        self.changed.emit()

    def value(self):
        text = self.combo.currentText()
        return [text] if text else []

    def set_value(self, names):
        names = [names] if isinstance(names, str) else list(names or [])
        self.wanted = names
        target = next((n for n in names
                       if self.combo.findText(n) >= 0), None)
        if target and target != self.combo.currentText():
            self.combo.setCurrentText(target)      # emits changed
        else:
            self.changed.emit()


def _signed_duration(seconds):
    """'+13.6 d', '−2 min', '+37 s'."""
    sign = "+" if seconds >= 0 else "−"
    value = abs(seconds)
    return sign + (f"{value / 86400:.1f} d" if value >= 86400 else
                   f"{value / 3600:.1f} h" if value >= 3600 else
                   f"{value / 60:.0f} min" if value >= 60 else
                   f"{value:.0f} s")


class StcProfileList(QWidget):
    """Check list of the STC profiles of a folder (one CSV file per
    profile): columns start (UTC), distance from LéXPLORE (position of the
    .vp2 header against the LéXPLORE position of the physical parameters),
    duration, mean descent speed, time shift of the closest Combined DTS
    profile found in the DTS folder (DTS − STC start), its record, file.  value() is the list of the file names
    ticked."""

    changed = Signal()
    COLUMNS = ["Start (UTC)", "DTS time shift", "LeXPLORE time shift",
               "Distance", "Duration", "Descent", "DTS record", "File"]
    HEADER_TIPS = ["Start of the STC profile, dd.mm hh:mm:ss UTC",
                   "Closest Combined DTS profile of the DTS folder − STC "
                   "start (+: DTS after)",
                   "Closest LéXPLORE chain profile of the LéXPLORE folder − "
                   "STC start (+: chain after)",
                   "Distance from LéXPLORE (position of the .vp2 file)",
                   "Duration of the STC profile (first to last sample)",
                   "Mean descent speed, first sample to the deepest one",
                   "Preprocessed DTS record (configuration) holding the "
                   "closest DTS profile",
                   "CSV file of the profile"]

    def __init__(self, default):
        super().__init__()
        from PySide6.QtWidgets import QTreeWidget
        self.dts_root = ""         # DTS folder searched for the closest
        self.chain_root = ""       # LéXPLORE folder (chain time shift)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list = QTreeWidget()
        self.list.setHeaderLabels(self.COLUMNS)
        for column, tip in enumerate(self.HEADER_TIPS):
            self.list.headerItem().setToolTip(column, tip)
        self.list.setRootIsDecorated(False)
        self.list.setMaximumHeight(190)
        self.list.itemChanged.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        for text, state in (("All", True), ("None", False)):
            button = QPushButton(text)
            button.setStyleSheet("padding: 1px 10px;")
            button.clicked.connect(lambda checked=False, on=state:
                                   self._tick_all(on))
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.note = QLabel("")
        self.note.setStyleSheet("color: gray;")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.folder = ""
        self.wanted = default          # None: every profile ticked

    def _items(self):
        return [self.list.topLevelItem(row)
                for row in range(self.list.topLevelItemCount())]

    def _tick_all(self, on):
        for item in self._items():
            item.setCheckState(0, Qt.Checked if on else Qt.Unchecked)

    def refresh(self, folder):
        """List the CSV profiles of ``folder`` (start time first)."""
        import dts_core
        from PySide6.QtWidgets import QTreeWidgetItem
        if self.list.topLevelItemCount():
            self.wanted = self.value()
        self.folder = folder or ""
        profiles = dts_core.stc_profile_files(self.folder)
        products = dts_core.find_dts_products(self.dts_root)
        chain_times = dts_core.lexplore_times(self.chain_root)
        self.list.blockSignals(True)
        self.list.clear()
        for name, start in profiles:
            lat, lon = dts_core.stc_position(self.folder, name)
            distance = dts_core.distance_to_lexplore(lat, lon)
            location = (f"{distance:.0f} m" if np.isfinite(distance)
                        else "no position")
            try:
                profile = dts_core.read_stc_csv(
                    os.path.join(self.folder, name))
                speed = dts_core.stc_descent_speed(profile)
                seconds = ((profile["end"] - profile["start"])
                           / np.timedelta64(1, "ms")) / 1000.0
            except Exception:                      # noqa: BLE001
                speed, seconds = np.nan, np.nan
            descent = f"{speed:.2f} m/s" if np.isfinite(speed) else "–"
            duration = (f"{seconds:.0f} s" if np.isfinite(seconds)
                        and seconds < 600 else f"{seconds / 60:.1f} min"
                        if np.isfinite(seconds) else "–")
            closest = dts_core.closest_dts_profile(products, start)
            if closest is None:
                shift, record = "–", "–"
                shift_tip = ("no preprocessed DTS file with a Combined "
                             "channel in the DTS folder")
            else:
                shift = _signed_duration(closest["shift_s"])
                record = closest["configuration"]
                shift_tip = (f"closest DTS profile: {str(closest['time'])[:19]}"
                             f" UTC, channel {closest['channel']} of "
                             f"{closest['path']}")
            if chain_times.size:
                index = int(np.argmin(np.abs(chain_times - start)))
                gap = ((chain_times[index] - start)
                       / np.timedelta64(1, "ms")) / 1000.0
                chain_shift = _signed_duration(gap)
                chain_tip = (f"closest LéXPLORE chain profile: "
                             f"{str(chain_times[index])[:19]} UTC")
            else:
                chain_shift = "–"
                chain_tip = "no LéXPLORE chain data in the LéXPLORE folder"
            item = QTreeWidgetItem(
                [f"{str(start)[8:10]}.{str(start)[5:7]} {str(start)[11:19]}",
                 shift, chain_shift, location, duration, descent, record,
                 name])
            item.setData(0, Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if self.wanted is None
                               or name in self.wanted else Qt.Unchecked)
            tip = (f"{lat:.5f} N, {lon:.5f} E (.vp2 header): "
                   f"{distance:.0f} m from LéXPLORE"
                   if np.isfinite(distance) else
                   "no position: no .vp2 file with the same name")
            tip += ("; mean descent speed from the first sample to the "
                    "deepest one" if np.isfinite(speed) else "")
            for column in range(len(self.COLUMNS)):
                item.setToolTip(column, shift_tip if column in (1, 6)
                                else chain_tip if column == 2 else tip)
            for column in (1, 2, 3, 4, 5):
                item.setTextAlignment(column, Qt.AlignRight | Qt.AlignVCenter)
            self.list.addTopLevelItem(item)
        for column in range(len(self.COLUMNS)):
            self.list.resizeColumnToContents(column)
        self.list.blockSignals(False)
        self.note.setText(
            f"{len(profiles)} profile(s); {len(products)} preprocessed DTS "
            f"record(s) in the DTS folder. Distance: from LéXPLORE; time "
            f"shifts: closest DTS (Combined) or LéXPLORE profile − STC start"
            if profiles
            else ("no STC profile (.csv) in this folder"
                  if os.path.isdir(self.folder) else "folder not found"))
        self.changed.emit()

    def set_dts_root(self, root):
        """DTS folder searched for the closest DTS profiles."""
        self.dts_root = root or ""
        self.refresh(self.folder)

    def value(self):
        return [item.data(0, Qt.UserRole) for item in self._items()
                if item.checkState(0) == Qt.Checked]

    def set_value(self, names):
        """None: every profile ticked; a list: those profiles."""
        self.wanted = None if names is None else list(names)
        for item in self._items():
            item.setCheckState(0, Qt.Checked if self.wanted is None
                               or item.data(0, Qt.UserRole) in self.wanted
                               else Qt.Unchecked)


class PreprocessedFileList(QWidget):
    """Drop-down list of the preprocessed files of the configuration chosen
    (DTS_preprocessed.nc first).  value() is a one-item list
    'configuration / file.nc', as the step expects."""

    SEPARATOR = " / "

    def __init__(self, default):
        super().__init__()
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        layout.addWidget(self.combo, 0, Qt.AlignLeft)
        self.note = QLabel("")
        self.note.setStyleSheet("color: gray;")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.wanted = list(default or [])
        self.configuration = ""

    def refresh(self, root, configurations):
        if self.combo.count():
            self.wanted = self.value() + [
                w for w in self.wanted if w not in self.value()]
        configuration = (configurations or [""])[0]
        self.configuration = configuration
        files = (preprocessed_files(os.path.join(root or "", configuration))
                 if configuration else [])
        self.combo.clear()
        self.combo.addItems(files)
        wanted = [w.split(self.SEPARATOR, 1)[1] for w in self.wanted
                  if w.startswith(configuration + self.SEPARATOR)]
        target = next((f for f in wanted if f in files), None)
        if target:
            self.combo.setCurrentText(target)
        self.note.setText(f"{len(files)} preprocessed file(s) in this "
                          "configuration" if files else
                          "choose a configuration above")

    def value(self):
        name = self.combo.currentText()
        return ([self.configuration + self.SEPARATOR + name]
                if name and self.configuration else [])

    def set_value(self, entries):
        entries = [entries] if isinstance(entries, str) else list(
            entries or [])
        self.wanted = entries
        for entry in entries:
            if entry.startswith(self.configuration + self.SEPARATOR):
                name = entry.split(self.SEPARATOR, 1)[1]
                if self.combo.findText(name) >= 0:
                    self.combo.setCurrentText(name)
                    return


class LayerBoxes(QWidget):
    """One check box per layer of the multi-layer decomposition (and the
    whole column); value() = the labels ticked."""

    changed = Signal()

    def __init__(self, choices, default):
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(2)
        self.boxes = {}
        self.wanted = list(default or [])
        self.set_choices(choices, self.wanted)

    def set_choices(self, choices, ticked=None):
        """New list of layers; a layer stays ticked when its name (before
        ':') was ticked."""
        if ticked is None:
            ticked = self.value() if self.boxes else self.wanted
        names = {t.split(":")[0] for t in ticked}
        for box in self.boxes.values():
            box.setParent(None)
            box.deleteLater()
        self.boxes = {}
        for label in choices:
            box = QCheckBox(label)
            box.setChecked(label.split(":")[0] in names)
            box.toggled.connect(lambda *_: self.changed.emit())
            self.layout_.addWidget(box)
            self.boxes[label] = box
        if self.boxes and not self.value():
            next(iter(self.boxes.values())).setChecked(True)

    def value(self):
        return [label for label, box in self.boxes.items()
                if box.isChecked()]

    def set_value(self, labels):
        labels = [labels] if isinstance(labels, str) else list(labels or [])
        self.wanted = labels
        names = {t.split(":")[0] for t in labels}
        for label, box in self.boxes.items():
            box.setChecked(label.split(":")[0] in names)


class ChannelRadios(QWidget):
    """One radio button per channel (exactly one channel), with (?)."""

    def __init__(self, choices, default):
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(4)
        self.group = QButtonGroup(self)
        self.buttons = {}
        self.cells = []
        self.set_choices(choices, default)

    def set_choices(self, choices, current=None):
        current = current or self.value()
        for button in self.buttons.values():
            self.group.removeButton(button)
        for cell in self.cells:
            cell.setParent(None)
            cell.deleteLater()
        self.buttons, self.cells, cells = {}, [], []
        for index, name in enumerate(choices):
            button = QRadioButton(name)
            self.group.addButton(button)
            self.buttons[name] = button
            cells.append(_channel_cell(button, name))
        self.cells = _place_cells(self.layout_, cells)
        target = current if current in self.buttons else (
            "Combined" if "Combined" in self.buttons
            else (choices[0] if choices else None))
        if target:
            self.buttons[target].setChecked(True)

    def value(self):
        return next((name for name, button in self.buttons.items()
                     if button.isChecked()), None)

    def set_value(self, name):
        name = _old_names(name) if name else name
        if name and name not in self.buttons:
            self.set_choices(list(self.buttons) + [name], name)
        if name in self.buttons:
            self.buttons[name].setChecked(True)


class ProfileTimeField(QComboBox):
    """Editable drop-down of a UTC time: the individual profiles of the
    shared list ('P1 – 2026-10-21 04:34:55'), or a time typed by hand.
    value() is the time 'YYYY-MM-DD hh:mm:ss'."""

    SEPARATOR = " – "

    def __init__(self, field):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setMinimumContentsLength(28)
        self.lineEdit().setPlaceholderText("YYYY-MM-DD hh:mm:ss, or a "
                                           "profile of the list")
        self.setToolTip(field.get("tip", ""))
        self.set_value(field.get("default", ""))

    def set_profiles(self, rows):
        """Items = the individual profiles (label, time); the text typed or
        chosen is kept."""
        text = self.currentText()
        self.blockSignals(True)
        self.clear()
        for label, when in rows or []:
            when = str(when).strip()
            if when:
                self.addItem(f"{str(label).strip()}{self.SEPARATOR}{when}")
        self.setEditText(text)
        self.blockSignals(False)

    def value(self):
        text = self.currentText().strip()
        if self.SEPARATOR in text:
            text = text.split(self.SEPARATOR, 1)[1].strip()
        return text

    def set_value(self, value):
        self.setEditText(str(value or ""))


class TimeTable(QWidget):
    """Editable table: (label, time) or (start, end) rows."""

    changed = Signal()

    def __init__(self, headers, rows):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(110)
        self.table.setMaximumHeight(150)
        buttons = QHBoxLayout()
        add, remove = QPushButton("+ row"), QPushButton("− row")
        clear = QPushButton("Clear")
        add.clicked.connect(lambda: self._append(
            [""] * self.table.columnCount()))
        remove.clicked.connect(self._remove_current)
        clear.clicked.connect(lambda: self.set_value([]))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.set_value(rows)
        self.table.cellChanged.connect(lambda *_: self.changed.emit())

    def _remove_current(self):
        self.table.removeRow(self.table.currentRow())
        self.changed.emit()

    def append_row(self, row):
        """Add one row (e.g. a time window selected on a map)."""
        self.table.blockSignals(True)
        self._append(row)
        self.table.blockSignals(False)
        self.changed.emit()

    def _append(self, row):
        index = self.table.rowCount()
        self.table.insertRow(index)
        for column, text in enumerate(row):
            self.table.setItem(index, column, QTableWidgetItem(str(text)))

    def value(self):
        rows = []
        for index in range(self.table.rowCount()):
            row = tuple((self.table.item(index, c).text().strip()
                         if self.table.item(index, c) else "")
                        for c in range(self.table.columnCount()))
            if any(row):
                rows.append(row)
        return rows

    def set_value(self, rows):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in rows or []:
            self._append(row)
        self.table.blockSignals(False)
        self.changed.emit()


class SimpleField:
    """Adds value()/set_value() to a plain Qt widget."""

    @staticmethod
    def wrap(widget, getter, setter):
        widget.value = getter
        widget.set_value = setter
        return widget


def make_field(field):
    kind = field["kind"]
    if kind == "dir":
        widget = PathField(field.get("default"), field.get("placeholder", ""))
    elif kind == "dirs":
        widget = PathListField(field.get("default"))
    elif kind == "text":
        widget = QLineEdit(field.get("default", ""))
        SimpleField.wrap(widget, widget.text, widget.setText)
    elif kind == "float":
        widget = FloatField(field)
    elif kind == "int":
        widget = QSpinBox()
        widget.setRange(field.get("minimum", -10 ** 6),
                        field.get("maximum", 10 ** 6))
        widget.setValue(field.get("default", 0))
        if field.get("unit"):
            widget.setSuffix(" " + field["unit"])
        SimpleField.wrap(widget, widget.value,
                         lambda v, w=widget: w.setValue(int(v)))
    elif kind == "radio":
        from PySide6.QtWidgets import QRadioButton
        widget = QRadioButton(field["label"])
        widget.setChecked(bool(field.get("default")))
        SimpleField.wrap(widget, widget.isChecked,
                         lambda v, w=widget: w.setChecked(bool(v)))
    elif kind == "bool":
        widget = QCheckBox()
        widget.setChecked(bool(field.get("default")))
        SimpleField.wrap(widget, widget.isChecked,
                         lambda v, w=widget: w.setChecked(bool(v)))
    elif kind in ("choice", "configuration"):
        widget = QComboBox()
        widget.addItems(field.get("choices", []) if kind == "choice"
                        else [field.get("default", "")])
        widget.setCurrentText(field.get("default", ""))
        SimpleField.wrap(widget, widget.currentText, widget.setCurrentText)
    elif kind == "channels":
        choices = field["choices"]
        widget = ChannelBoxes(field["default"] if isinstance(choices, str)
                              else choices, field.get("default"))
    elif kind == "products":
        widget = ProductList(field.get("default"))
    elif kind == "product_files":
        widget = PreprocessedFileList(field.get("default"))
    elif kind == "stc_profiles":
        widget = StcProfileList(field.get("default"))
    elif kind == "channel":
        widget = ChannelRadios(["CH1", "CH3", "Combined"],
                               field.get("default"))
    elif kind == "datetime":
        widget = DateTimeField(field)
    elif kind == "profile_time":
        widget = ProfileTimeField(field)
    elif kind == "timetable":
        widget = TimeTable(["label", f"time ({field.get('zone', 'UTC')})"],
                           field.get("default"))
    elif kind == "named_windows":
        zone = field.get("zone", "UTC")
        widget = TimeTable(["label", f"start ({zone})", f"end ({zone})"],
                           field.get("default"))
    elif kind == "layers":
        default = field.get("default") or []
        widget = LayerBoxes(list(field.get("choices") or default), default)
    elif kind == "layer":
        widget = QComboBox()
        widget.addItems([field.get("default", "")])
        widget.setCurrentText(field.get("default", ""))
        widget.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        SimpleField.wrap(widget, widget.currentText, widget.setCurrentText)
    elif kind == "window":
        widget = QComboBox()
        widget.addItems([field.get("default", "")])
        widget.setCurrentText(field.get("default", ""))
        widget.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        SimpleField.wrap(widget, widget.currentText, widget.setCurrentText)
    elif kind == "windows":
        zone = field.get("zone", "UTC")
        widget = TimeTable([f"start ({zone})", f"end ({zone})"],
                           field.get("default"))
    elif kind == "info":
        widget = QLabel(str(field.get("default", "")))
        SimpleField.wrap(widget, widget.text, widget.setText)
    else:
        raise ValueError(f"unknown field kind {kind!r}")
    if field.get("tip"):
        widget.setToolTip(field["tip"])
    return widget


# ---------------------------------------------------------------------------
# left panel
# ---------------------------------------------------------------------------
NON_INPUT_KINDS = ("heading", "note", "button", "toggle")


class ParameterPanel(QWidget):
    """Inputs of one panel, its action buttons, Reset and Run (All)."""

    run_requested = Signal()
    action_requested = Signal(str)            # step id of a box button
    toggle_changed = Signal(str, bool)        # name of a toggle, state

    def __init__(self, section):
        super().__init__()
        self.section = section
        self.fields = {}          # name -> widget
        self.specs = {}           # name -> field description
        self.action_buttons = []
        self.toggles = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 0, 4, 0)
        self.group_boxes = {}
        self.radio_groups = {}
        # entries: (title, fields, layout to add the box to, key); a params
        # item ("__tabs__", [(tab title, [groups]), ...]) puts its groups in
        # the tabs of one tab widget
        entries, tab_layouts = [], []
        self.tab_widget = None
        for item in section["params"]:
            if item[0] == "__tabs__":
                from PySide6.QtWidgets import QTabWidget
                tabs = QTabWidget()
                tabs.setDocumentMode(True)
                tabs.setStyleSheet(
                    "QTabBar::tab { padding: 4px 10px; font-weight: bold; "
                    "color: white; background: #5B7A99; "
                    "border-top-left-radius: 4px; "
                    "border-top-right-radius: 4px; margin-right: 2px; } "
                    "QTabBar::tab:selected { background: #0072B2; }")
                self.tab_widget = tabs
                entries.append(("__widget__", tabs, body_layout, None))
                for tab_title, groups in item[1]:
                    page = QWidget()
                    page_layout = QVBoxLayout(page)
                    page_layout.setContentsMargins(0, 4, 0, 0)
                    tabs.addTab(page, tab_title)
                    tab_layouts.append(page_layout)
                    for title, fields in groups:
                        entries.append((title, fields, page_layout,
                                        f"{tab_title}/{title}"))
            else:
                entries.append((item[0], item[1], body_layout, item[0]))
        for group_title, group_fields, target, group_key in entries:
            if group_title == "__widget__":
                target.addWidget(group_fields)
                continue
            box = QGroupBox(group_title)
            self.group_boxes[group_key] = box
            box.setVisible(group_title not in section.get("hidden_groups",
                                                          ()))
            form = QFormLayout(box)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            for field in group_fields:
                kind = field["kind"]
                if kind == "heading":
                    heading = QLabel(f"<b>{field['label']}</b>")
                    heading.setStyleSheet("padding-top: 6px;")
                    form.addRow(heading)
                    continue
                if kind == "note":
                    note = QLabel(field["label"])
                    note.setWordWrap(True)
                    note.setStyleSheet("color: gray;")
                    form.addRow(note)
                    continue
                if kind == "toggle":
                    toggle = QPushButton(field["label"])
                    toggle.setCheckable(True)
                    toggle.setStyleSheet(
                        "QPushButton { padding: 4px; } "
                        "QPushButton:checked { background: #D55E00; "
                        "color: white; font-weight: bold; }")
                    toggle.toggled.connect(
                        lambda on, button=toggle, text=field["label"],
                        hint=field.get("on_text", "on"):
                        button.setText(text + (f"  ({hint})" if on else "")))
                    if field.get("tip"):
                        toggle.setToolTip(field["tip"])
                    toggle.toggled.connect(
                        lambda on, name=field["name"]:
                        self.toggle_changed.emit(name, on))
                    form.addRow(toggle)
                    self.toggles[field["name"]] = toggle
                    continue
                if kind == "button":
                    button = QPushButton(field["label"])
                    button.setStyleSheet("font-weight: bold; "
                                         "padding: 3px 14px;")
                    if field.get("tip"):
                        button.setToolTip(field["tip"])
                    steps = field.get("steps") or [field["step"]]
                    button.clicked.connect(
                        lambda checked=False, steps="|".join(steps):
                        self.action_requested.emit(steps))
                    row = QWidget()
                    row_layout = QHBoxLayout(row)
                    row_layout.setContentsMargins(0, 2, 0, 2)
                    row_layout.addStretch(1)
                    row_layout.addWidget(button)
                    form.addRow(row)
                    self.action_buttons.append(button)
                    continue
                widget = make_field(field)
                label = field["label"]
                if kind in ("datetime", "profile_time") \
                        and field.get("zone"):
                    label += f" ({field['zone']})"
                if kind in ("timetable", "windows", "dirs", "channels",
                            "channel", "named_windows", "layers",
                            "stc_profiles"):
                    form.addRow(QLabel(label))
                    form.addRow(widget)
                elif kind == "radio":          # mutually exclusive boxes
                    from PySide6.QtWidgets import QButtonGroup
                    group = self.radio_groups.get(field["group"])
                    if group is None:
                        group = QButtonGroup(self)
                        group.setExclusive(True)
                        self.radio_groups[field["group"]] = group
                    group.addButton(widget)
                    if field.get("tip"):
                        widget.setToolTip(field["tip"])
                    form.addRow(widget)
                else:
                    # a field with 'check': a tick box in place of its
                    # label switches it on or off (value in check["name"])
                    check = field.get("check")
                    if check:
                        box_check = QCheckBox(label)
                        box_check.setChecked(bool(check.get("default", True)))
                        SimpleField.wrap(
                            box_check, box_check.isChecked,
                            lambda v, b=box_check: b.setChecked(bool(v)))
                        if check.get("tip"):
                            box_check.setToolTip(check["tip"])
                        self.fields[check["name"]] = box_check
                        self.specs[check["name"]] = dict(
                            name=check["name"], kind="bool",
                            default=bool(check.get("default", True)))
                        box_check.toggled.connect(widget.setEnabled)
                        widget.setEnabled(box_check.isChecked())
                        label = box_check
                    if field.get("help"):      # input + (?) on one row
                        row = QWidget()
                        row_layout = QHBoxLayout(row)
                        row_layout.setContentsMargins(0, 0, 0, 0)
                        row_layout.setSpacing(6)
                        wide = kind in ("dir", "dirs", "text")
                        row_layout.addWidget(widget, 1 if wide else 0)
                        row_layout.addWidget(_help_button(
                            field["label"], field["help"],
                            field.get("name")))
                        if not wide:
                            row_layout.addStretch(1)
                        form.addRow(label, row)
                    else:
                        form.addRow(label, widget)
                self.fields[field["name"]] = widget
                self.specs[field["name"]] = field
            target.addWidget(box)
        for page_layout in tab_layouts:
            page_layout.addStretch(1)
        if not section["params"]:
            note = QLabel("No input for this step.")
            note.setStyleSheet("color: gray; padding: 8px;")
            body_layout.addWidget(note)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        self.body = body
        self.scroll = scroll
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Reset")
        self.reset_button.setToolTip("Back to the default values")
        self.reset_button.clicked.connect(self.reset)
        self.run_button = QPushButton("▶  Run All" if section.get("actions")
                                      else "▶  Run")
        self.run_button.setStyleSheet("font-weight: bold; padding: 5px 16px;")
        self.run_button.clicked.connect(self.run_requested)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        buttons.addWidget(self.run_button)
        self.run_button.setVisible(not section.get("hide_run"))
        outer.addLayout(buttons)

        rule = section.get("groups_shown_by")
        if rule:
            self.fields[rule[0]].currentTextChanged.connect(
                self.apply_conditional_groups)
            self.apply_conditional_groups()
        # a window step shows the window size while on auto (the value
        # used), and starts from it when auto is unticked
        for name, spec in self.specs.items():
            source = spec.get("follows")
            if source and source in self.fields and \
                    getattr(self.fields[name], "auto", None) is not None:
                step, width = self.fields[name], self.fields[source]

                def follow(*_, step=step, width=width):
                    if step.auto.isChecked():
                        step.spin.setValue(width.spin.value())

                width.spin.valueChanged.connect(follow)
                step.auto.toggled.connect(follow)
                follow()
        # inputs enabled only while their radio button is checked
        for name, spec in self.specs.items():
            radio = spec.get("enabled_by")
            if radio and radio in self.fields:
                widget = self.fields[name]
                self.fields[radio].toggled.connect(widget.setEnabled)
                widget.setEnabled(self.fields[radio].isChecked())
        # the product list follows its root folder
        for name, spec in self.specs.items():
            if spec["kind"] == "products":
                root = self.fields[spec["root_field"]]
                product_list = self.fields[name]
                root.changed.connect(
                    lambda *_, r=root, l=product_list: l.refresh(r.value()))
                product_list.refresh(root.value())
        # the STC profile list follows its folder and the DTS folder (as
        # soon as the text names an existing folder)
        for name, spec in self.specs.items():
            if spec["kind"] == "stc_profiles":
                folder = self.fields[spec["root_field"]]
                profile_list = self.fields[name]
                dts = self.fields.get(spec.get("dts_field", ""))
                dts_check = self.fields.get(
                    (self.specs.get(spec.get("dts_field", ""), {})
                     .get("check") or {}).get("name", ""))
                chain = self.fields.get(spec.get("chain_field", ""))
                chain_check = self.fields.get(
                    (self.specs.get(spec.get("chain_field", ""), {})
                     .get("check") or {}).get("name", ""))

                def on(field, check):
                    return field.value() if field is not None and (
                        check is None or check.isChecked()) else ""

                def update(*_, f=folder, l=profile_list, d=dts,
                           c=dts_check, h=chain, hc=chain_check):
                    root = on(d, c)
                    l.chain_root = on(h, hc)
                    if os.path.isdir(f.value() or ""):
                        l.dts_root = root
                        l.refresh(f.value())

                for field in (folder, dts, chain):
                    if field is not None:
                        field.changed.connect(update)
                        field.edit.textChanged.connect(update)
                for check in (dts_check, chain_check):
                    if check is not None:
                        check.toggled.connect(update)
                profile_list.dts_root = on(dts, dts_check)
                profile_list.chain_root = on(chain, chain_check)
                profile_list.refresh(folder.value())
        # the file list follows the root folder and the configurations
        for name, spec in self.specs.items():
            if spec["kind"] == "product_files":
                root = self.fields[spec["root_field"]]
                configurations = self.fields[spec["configurations_field"]]
                file_list = self.fields[name]
                configurations.changed.connect(
                    lambda *_, r=root, c=configurations, l=file_list:
                    l.refresh(r.value(), c.value()))
                file_list.refresh(root.value(), configurations.value())
        # the configuration list follows the data root
        for name, spec in self.specs.items():
            if spec["kind"] == "configuration":
                root = self.fields[spec["root_field"]]
                root.changed.connect(self.refresh_configurations)
                self.fields[name].currentTextChanged.connect(
                    self.refresh_folder_channels)
                self.refresh_configurations()

    def needed_width(self):
        """Width that shows every input without cutting text (the body,
        the vertical scroll bar and the margins)."""
        self.body.adjustSize()
        width = max(self.body.sizeHint().width(),
                    self.body.minimumSizeHint().width())
        bar = self.scroll.verticalScrollBar().sizeHint().width()
        return width + bar + 12

    def apply_conditional_groups(self, *_):
        """Groups shown only for some values of a choice (section key
        'groups_shown_by': (field, {value: [group titles]}))."""
        rule = self.section.get("groups_shown_by")
        if not rule:
            return
        name, mapping = rule
        value = self.fields[name].currentText()
        conditional = {t for titles in mapping.values() for t in titles}
        for title in conditional:
            if title in self.group_boxes:
                self.group_boxes[title].setVisible(
                    title in mapping.get(value, []))

    def show_groups(self, visible=True):
        """Show the groups hidden at start (e.g. after loading data)."""
        for title in self.section.get("hidden_groups", ()):
            if title in self.group_boxes:
                self.group_boxes[title].setVisible(visible)

    def set_running(self, running):
        """Disable the buttons while a computation runs."""
        for button in [self.run_button] + self.action_buttons:
            button.setEnabled(not running)

    # ---- dynamic lists ----------------------------------------------------
    def refresh_configurations(self):
        for name, spec in self.specs.items():
            if spec["kind"] != "configuration":
                continue
            combo = self.fields[name]
            folder = temperature_root(
                self.fields[spec["root_field"]].value())
            current = combo.currentText() or spec.get("default", "")
            names = (sorted(n for n in os.listdir(folder)
                            if os.path.isdir(os.path.join(folder, n)))
                     if os.path.isdir(folder) else [])
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names or [current])
            combo.setCurrentText(current if current in names or not names
                                 else names[0])
            combo.blockSignals(False)
            self.refresh_folder_channels()

    def refresh_folder_channels(self):
        """Channel boxes of step 0 = the channel folders found."""
        for name, spec in self.specs.items():
            if spec["kind"] != "configuration":
                continue
            folder = os.path.join(
                temperature_root(self.fields[spec["root_field"]].value()),
                self.fields[name].currentText())
            if not os.path.isdir(folder):
                continue
            from channel_names import display_name
            channels = [display_name(n) for n in sorted(
                n for n in os.listdir(folder)
                if os.path.isdir(os.path.join(folder, n))
                and n.lower().startswith("channel"))]
            if "CHANNELS" in self.fields and channels:
                self.fields["CHANNELS"].set_choices(channels, channels)

    def set_profile_choices(self, rows):
        """Drop-downs of times ('profile_time'): the individual profiles."""
        for name, spec in self.specs.items():
            if spec["kind"] == "profile_time":
                self.fields[name].set_profiles(rows)

    def set_layer_choices(self, items):
        """Lists 'Layer': the whole column and the layers of the multi-layer
        decomposition (the choice kept when its label is still there)."""
        for name, spec in self.specs.items():
            if spec["kind"] == "layers":
                self.fields[name].set_choices(list(items))
                continue
            if spec["kind"] != "layer":
                continue
            combo = self.fields[name]
            label = combo.currentText().split(":")[0]
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(items)
            match = [i for i in items if i.split(":")[0] == label]
            combo.setCurrentText(match[0] if match else items[0])
            combo.blockSignals(False)

    def set_window_choices(self, items):
        """Lists 'Time window' of the panel: the whole record and the
        windows of Load preprocessed data (the current choice kept when still there,
        matched by its label)."""
        for name, spec in self.specs.items():
            if spec["kind"] != "window":
                continue
            combo = self.fields[name]
            current = combo.currentText()
            label = current.split(":")[0]
            if spec.get("first_item"):     # e.g. 'Same as DTS time window'
                items = [spec["first_item"]] + list(items[1:])
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(items)
            match = [i for i in items if i.split(":")[0] == label]
            combo.setCurrentText(match[0] if match else items[0])
            combo.blockSignals(False)

    def set_choice_items(self, name, items):
        """New list for a choice field (the current value kept when it is
        still in the list)."""
        combo = self.fields[name]
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        combo.setCurrentText(current if current in items else items[0])
        combo.blockSignals(False)

    def set_channel_choices(self, source, channels):
        """Channel fields whose choices come from ``source`` ("pre",
        "files" or "analysis") receive the channels found in the data."""
        for name, spec in self.specs.items():
            if spec["kind"] in ("channels", "channel") \
                    and spec.get("choices") == source:
                if spec["kind"] == "channels":       # new data: all ticked
                    ticked = (list(channels)[:1] if spec.get("first_only")
                              else list(channels))
                    self.fields[name].set_choices(list(channels), ticked)
                else:
                    self.fields[name].set_choices(list(channels))

    # ---- values -----------------------------------------------------------
    def values(self, step=None):
        """Inputs of the panel; with a step, the fields reserved to other
        steps (spec 'only_for') are left out."""
        base = step[:-len(".replot")] if step and step.endswith(".replot") \
            else step
        return {name: widget.value() for name, widget in self.fields.items()
                if base is None
                or base in self.specs[name].get("only_for", [base])}

    def set_values(self, values):
        for name, value in values.items():
            if name in self.fields:
                if isinstance(value, list) and self.specs[name]["kind"] in (
                        "timetable", "windows", "named_windows"):
                    value = [tuple(row) for row in value]
                self.fields[name].set_value(value)

    def reset(self):
        for name, spec in self.specs.items():
            default = spec.get("default")
            if spec["kind"] in ("channels",):
                self.fields[name].set_value(list(self.fields[name].boxes))
            elif spec["kind"] == "layers":
                self.fields[name].set_value(default)
                continue
            elif spec["kind"] in ("configuration", "info", "window",
                                  "layer"):
                if spec["kind"] in ("window", "layer"):
                    self.fields[name].setCurrentIndex(0)
                continue
            elif spec["kind"] in ("products", "product_files"):
                self.fields[name].set_value(default)
            else:
                self.fields[name].set_value(default)


# ---------------------------------------------------------------------------
# right panel
# ---------------------------------------------------------------------------
def status_dot(colour, size=12):
    """Small filled circle used as an icon."""
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(colour))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pixmap)


INDENT_ROLE = Qt.UserRole + 3            # indentation level of a list item
INDENT_STEP = 18                          # pixels per level


class IndentDelegate(QStyledItemDelegate):
    """Shifts the whole item (check box, icon and text) to the right by its
    indentation level, so that the check boxes line up with the text."""

    def _shifted(self, option, index):
        level = index.data(INDENT_ROLE) or 0
        if level:
            option = QStyleOptionViewItem(option)
            option.rect = option.rect.adjusted(level * INDENT_STEP, 0, 0, 0)
        return option

    def paint(self, painter, option, index):
        super().paint(painter, self._shifted(option, index), index)

    def editorEvent(self, event, model, option, index):
        return super().editorEvent(event, model,
                                   self._shifted(option, index), index)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.decorationPosition = QStyleOptionViewItem.Right   # circle

    def sizeHint(self, option, index):
        """Height computed for the narrower (indented) width, so that long
        names wrap instead of being cut."""
        return super().sizeHint(self._shifted(option, index), index)


class FigurePanel(QWidget):
    """Result area of one or several panels: the tabs (live matplotlib
    figures or tables) and, on the right, the list of the figures with
    tick boxes.  Ticked figures are shown as tabs (after *Update plots*,
    or at once when a step makes them); a tab closed with its x is
    unticked.  Every result belongs to the step that made it, so a step
    replaces only its own results; tabs follow the order of the steps."""

    clicked = Signal(str, float, float)   # owner step, data coordinates
    display_requested = Signal(dict)      # display options, Update plots
    sublist_requested = Signal(str, str, list)  # owner, title, ticked items
    figures_shown = Signal(list)          # (owner, title) hidden -> shown

    COLOUR_MAPS = ["seismic", "coolwarm", "RdBu_r", "viridis", "plasma",
                   "inferno", "magma", "cividis", "turbo", "gray"]

    def __init__(self, section, catalogue=(), step_names=None,
                 display=False):
        super().__init__()
        self.section = section
        self.order = list(section.get("actions") or [section["id"]])
        self.catalogue = list(catalogue)       # (owner, title, default)
        self.step_names = step_names or {}
        # visibility: catalogue default, limited to the figures of the
        # active step(s) (None: every step), unless shown / hidden by hand
        self.default = {(owner, title): bool(default)
                        for owner, title, default in self.catalogue}
        self.active = None
        self.manual = {}
        # figures shown in every step of the menu (e.g. the configuration)
        self.pinned = {(owner, title) for owner, title, _ in self.catalogue
                       if (owner, title) in self.PINNED}
        self.checked = dict(self.default)
        self.results = {}          # owner -> [(title, item)]
        self.sublists = {}         # (owner, title) -> {item name: ticked}
        self.pages = {}            # (owner, title) -> page widget
        self.canvas_of = {}        # (owner, title) -> canvas
        self.owner_of_canvas = {}
        self.toolbars = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setStyleSheet(
            "background: palette(alternate-base); padding: 6px;"
            "border-radius: 4px;")
        self.set_description(section.get("description", ""))

        from PySide6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        splitter.addWidget(self.tabs)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(4, 0, 0, 0)
        title = QLabel("<b>Figures</b>")
        side_layout.addWidget(title)
        self.figure_list = QListWidget()
        self.figure_list.setToolTip("Ticked figures are shown as tabs. "
                                    "Green circle: ready to be displayed; "
                                    "red circle: not available yet (run "
                                    "the step)")
        # rows as wide as the list (long titles wrap), so that the circle
        # drawn at the right end of a row is always visible
        self.figure_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.figure_list.setWordWrap(True)
        self.figure_list.setResizeMode(QListWidget.Adjust)
        self._delegate = IndentDelegate(self.figure_list)  # keep ref
        self.figure_list.setItemDelegate(self._delegate)
        self.figure_list.itemChanged.connect(self._on_item_changed)
        self.figure_list.itemClicked.connect(self._on_item_clicked)
        self._just_toggled = False
        self.figure_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.figure_list.customContextMenuRequested.connect(
            self._figure_menu)
        self._syncing = False
        self.dot_ready = status_dot("#1A9E3F")       # green
        self.dot_missing = status_dot("#D62728")     # red
        side_layout.addWidget(self.figure_list, 1)
        self.display_fields = None
        if display:
            box = QGroupBox("Display of the maps")
            form = QFormLayout(box)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            shading_on = QCheckBox()
            shading_on.setToolTip("Off: plain cells ('nearest'); on: the "
                                  "kind below")
            shading_kind = QComboBox()
            shading_kind.addItems(["gouraud", "nearest", "auto"])
            colour_map = QComboBox()
            colour_map.addItems(self.COLOUR_MAPS)
            colour_map.setToolTip(
                "seismic, coolwarm, RdBu_r: diverging; viridis, plasma, "
                "inferno, magma, cividis: perceptually uniform (cividis also "
                "colour-blind safe); turbo: rainbow; gray: grey scale")
            form.addRow("Smooth shading", shading_on)
            form.addRow("Shading kind", shading_kind)
            form.addRow("Colour map", colour_map)
            side_layout.addWidget(box)
            self.display_fields = dict(IS_SHADING=shading_on,
                                       SHADING=shading_kind,
                                       CMAP=colour_map)
        self.update_button = QPushButton("Update plots")
        self.update_button.setStyleSheet("font-weight: bold; padding: 4px;")
        self.update_button.setToolTip(
            "Redraw every map with the display options (the figures are "
            "shown or hidden as soon as they are ticked)")
        self.update_button.clicked.connect(self.apply_list)
        side_layout.addWidget(self.update_button)
        self.update_button.setVisible(bool(display))   # display options only
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([900, 230])
        layout.addWidget(splitter, 1)
        layout.addWidget(self.description)       # below the figures

        self.message = None
        self.rebuild_list()
        self.refresh_tabs()

    # ---- public -----------------------------------------------------------
    def set_description(self, text):
        self.description.setText(text)
        self.description.setVisible(bool(text))

    def set_figures(self, owner, figures, message_if_empty=""):
        """Replace the results of ``owner`` by ``figures`` [(title, Figure
        or DataFrame)] and show the ticked ones."""
        for (key_owner, key_title) in [k for k in self.pages
                                       if k[0] == owner]:
            page = self.pages.pop((key_owner, key_title))
            canvas = self.canvas_of.pop((key_owner, key_title), None)
            if canvas is not None:
                self.toolbars.pop(id(canvas), None)
                self.owner_of_canvas.pop(id(canvas), None)
            index = self.tabs.indexOf(page)
            if index >= 0:
                self.tabs.removeTab(index)
            page.deleteLater()
        self.results[owner] = list(figures)
        for title, item in figures:
            self.default.setdefault((owner, title), not self._in_catalogue(
                owner))           # titles outside the catalogue: shown
            self.checked[(owner, title)] = self._visible((owner, title))
            page, canvas = self._make_page(item)
            self.pages[(owner, title)] = page
            if canvas is not None:
                self.canvas_of[(owner, title)] = canvas
                self.owner_of_canvas[id(canvas)] = owner
        if message_if_empty:
            self.empty_message = message_if_empty
        self.rebuild_list()
        self.refresh_tabs(focus=owner)

    def _figure_menu(self, position):
        """Right click on a figure name: Show / Hide, Focus and Save
        data."""
        from PySide6.QtWidgets import QMenu
        item = self.figure_list.itemAt(position)
        if item is None:
            return
        key = item.data(Qt.UserRole)
        sub = item.data(Qt.UserRole + 1)
        shown = item.checkState() != Qt.Unchecked
        menu = QMenu(self)
        if not key and not sub:          # header: every figure below it
            toggle = menu.addAction("Hide all" if shown else "Show all")
            chosen = menu.exec(
                self.figure_list.viewport().mapToGlobal(position))
            if chosen is toggle:
                item.setCheckState(Qt.Unchecked if shown else Qt.Checked)
            return
        # an individual profile (P1, P2, ...): Show / Hide that profile;
        # Focus and Save data act on the figure that holds it
        owner, title = tuple(sub[:2]) if sub else tuple(key)
        toggle = menu.addAction(("Hide" if shown else "Show")
                                + (f" {sub[2]}" if sub else ""))
        focus = menu.addAction("Focus" + (f" '{title}'" if sub else ""))
        computed = (owner, title) in self.pages
        focus.setEnabled(computed)
        menu.addSeparator()
        save = menu.addAction("Save data…" + (f" of '{title}'" if sub
                                               else ""))
        save.setEnabled(computed)
        if not computed:
            focus.setToolTip("not computed yet: run the step")
            save.setToolTip("not computed yet: run the step")
        chosen = menu.exec(self.figure_list.viewport().mapToGlobal(position))
        if chosen is toggle:
            self.figure_action(item, "toggle")
        elif chosen is focus:
            self.figure_action(item, "focus")
        elif chosen is save:
            self.figure_action(item, "save")

    def figure_action(self, item, action):
        """'toggle': show a hidden figure (or profile) or hide a shown one;
        'focus': show the figure and bring its tab forward."""
        sub = item.data(Qt.UserRole + 1)
        owner, title = tuple(sub[:2]) if sub else tuple(
            item.data(Qt.UserRole))
        if action == "toggle":
            shown = item.checkState() == Qt.Checked
            item.setCheckState(Qt.Unchecked if shown else Qt.Checked)
        elif action == "focus":
            self.show_figure(owner, title)
        elif action == "save":
            self.save_figure_data(owner, title)

    # folder of the last 'Save data' (the next dialog opens there)
    last_save_folder = ""

    def figure_object(self, owner, title):
        """The matplotlib figure of a computed result (None if absent)."""
        for name, figure in self.results.get(owner, []):
            if name == title:
                return figure
        return None

    def save_figure_data(self, owner, title, path=None, chosen_filter=""):
        """Save the variables used to produce one figure (the session
        variables read or written by the step that drew it, its inputs
        and the physical parameters): the user chooses the file name, the
        folder and the format (npz, NetCDF, HDF5, txt, csv, MATLAB).
        Returns the files written."""
        import gui_export
        figure = self.figure_object(owner, title)
        if figure is None:
            QMessageBox.warning(self, "Save data",
                                f"'{title}' is not computed yet.")
            return []
        window = self.window()
        variables = (window.figure_variables(owner)
                     if hasattr(window, "figure_variables") else None)
        if path is None:
            default = os.path.join(FigurePanel.last_save_folder or
                                   os.path.expanduser("~"),
                                   gui_export._clean(title))
            path, chosen_filter = QFileDialog.getSaveFileName(
                self, f"Save the data of '{title}'", default,
                gui_export.file_filter())
            if not path:
                return []
        fmt = gui_export.format_of(path, chosen_filter)
        if variables:
            tree = gui_export.to_tree(variables)
            what = "variables of the figure"
        else:                       # no record of the run: drawn data
            tree = gui_export.figure_data(figure)
            what = "data drawn on the figure"
        try:
            files = gui_export.write(path, fmt, tree, title=title)
        except Exception as error:                 # noqa: BLE001
            QMessageBox.warning(self, "Save data",
                                f"Could not save the data:\n{error}")
            return []
        FigurePanel.last_save_folder = os.path.dirname(files[0])
        names = [n for n in (variables or {})
                 if n not in ("step_inputs", "physical_parameters")]
        text = (f"{what} '{title}' saved ({fmt}"
                + (f"; {', '.join(names)}" if names else "") + "): "
                + ", ".join(files) + "\n")
        (window.write_log if hasattr(window, "write_log") else print)(text)
        return files

    pending_focus = None

    def focus_pending(self, owner, clear=True):
        """Bring forward the figure waiting for focus (e.g. Individual
        profiles after a profile was ticked) once ``owner`` has drawn it."""
        key = self.pending_focus
        if key is None or key[0] != owner:
            return
        page = self.pages.get(key)
        if page is not None and self.tabs.indexOf(page) >= 0:
            self.tabs.setCurrentWidget(page)
            if clear:
                self.pending_focus = None

    def _visible(self, key):
        """Shown by hand / hidden by hand, otherwise the default of the
        figure if its step is active."""
        if key in self.manual:
            return self.manual[key]
        if key in self.pinned:
            return True
        if self.active is not None and key[0] not in self.active:
            return False
        return self.default.get(key, True)

    PINNED = {("pre.1.load", "Configuration")}

    def set_active_owners(self, owners):
        """Only the figures of ``owners`` (the steps of the panel on the
        left) are shown; the figures shown or hidden by hand in the
        previous step return to that default."""
        self.active = set(owners)
        self.manual = {}
        for key in set(self.checked) | set(self.default):
            self.checked[key] = self._visible(key)
        self.rebuild_list()
        self.refresh_tabs()

    def show_figure(self, owner, title):
        """Tick one figure and bring its tab forward (False if it is not
        computed yet)."""
        self.checked[(owner, title)] = True
        self.manual[(owner, title)] = True
        self.rebuild_list()
        self.refresh_tabs()
        page = self.pages.get((owner, title))
        if page is None:
            return False
        self.tabs.setCurrentWidget(page)
        return True

    def canvas(self, owner, title):
        return self.canvas_of.get((owner, title))

    def select_owner(self, owners):
        """Bring forward the first visible tab made by one of ``owners``."""
        for owner in owners:
            for title, _ in self.results.get(owner, []):
                page = self.pages.get((owner, title))
                if page is not None and self.tabs.indexOf(page) >= 0:
                    self.tabs.setCurrentWidget(page)
                    return

    def mark_owners_outdated(self, outdated_steps):
        """⚠ in the title of the tabs made by an outdated step."""
        for (owner, title), page in self.pages.items():
            index = self.tabs.indexOf(page)
            if index < 0:
                continue
            if owner in outdated_steps:
                self.tabs.setTabText(index, "⚠ " + title)
                self.tabs.setTabToolTip(index, "Outdated: an earlier step "
                                               "was run again since")
            else:
                self.tabs.setTabText(index, title)
                self.tabs.setTabToolTip(index, "")

    # ---- list of figures --------------------------------------------------
    def _in_catalogue(self, owner):
        return any(o == owner for o, _, _ in self.catalogue)

    def _titles(self, owner):
        titles = [t for o, t, _ in self.catalogue if o == owner]
        titles += [t for t, _ in self.results.get(owner, [])
                   if t not in titles]
        return titles

    GROUP_ROLE = Qt.UserRole + 2         # "all" or ("step", owner)

    def rebuild_list(self):
        from PySide6.QtGui import QBrush, QColor, QFont
        self._syncing = True
        self.figure_list.clear()
        font = QFont()
        font.setBold(True)
        if any(self._titles(owner) for owner in self.order):
            every = QListWidgetItem("All figures")
            every.setFont(font)
            every.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            every.setData(self.GROUP_ROLE, "all")
            every.setData(INDENT_ROLE, 0)
            every.setToolTip("Tick or untick every figure (then Update "
                             "plots)")
            self.figure_list.addItem(every)
        for owner in self.order:
            titles = self._titles(owner)
            if not titles:
                continue
            if len(self.order) > 1:
                header = QListWidgetItem(self.step_names.get(owner, owner))
                header.setFont(font)
                header.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                header.setData(self.GROUP_ROLE, ("step", owner))
                header.setData(INDENT_ROLE, 1)
                header.setToolTip("Tick or untick every figure of this step "
                                  "(then Update plots)")
                self.figure_list.addItem(header)
            computed = {t for t, _ in self.results.get(owner, [])}
            level = 2 if len(self.order) > 1 else 1
            for title in titles:
                item = QListWidgetItem(title)
                item.setData(INDENT_ROLE, level)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if self.checked.get(
                    (owner, title)) else Qt.Unchecked)
                item.setData(Qt.UserRole, (owner, title))
                if title in computed:
                    item.setIcon(self.dot_ready)
                    item.setToolTip("ready to be displayed")
                else:
                    item.setIcon(self.dot_missing)
                    item.setForeground(QBrush(QColor("gray")))
                    item.setToolTip("not available yet: run the step")
                self.figure_list.addItem(item)
                parent_on = bool(self.checked.get((owner, title)))
                for name, on in self.sublists.get((owner, title),
                                                  {}).items():
                    on = on and parent_on      # figure hidden: all off
                    sub = QListWidgetItem(name)
                    sub.setData(INDENT_ROLE, level + 1)
                    sub.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    sub.setCheckState(Qt.Checked if on else Qt.Unchecked)
                    sub.setData(Qt.UserRole + 1, (owner, title, name))
                    sub.setToolTip("shown in the figure '" + title + "'")
                    self.figure_list.addItem(sub)
        self._syncing = False
        self._sync_groups()

    def _figure_items(self, owner=None):
        items = []
        for row in range(self.figure_list.count()):
            item = self.figure_list.item(row)
            key = item.data(Qt.UserRole)
            if key and (owner is None or tuple(key)[0] == owner):
                items.append(item)
        return items

    @staticmethod
    def _state_of(items):
        ticked = sum(item.checkState() == Qt.Checked for item in items)
        if items and ticked == len(items):
            return Qt.Checked
        return Qt.PartiallyChecked if ticked else Qt.Unchecked

    def _sync_groups(self):
        """Tick state of 'All figures' and of the step headers from the
        figures below them (partly ticked when only some are)."""
        self._syncing = True
        for row in range(self.figure_list.count()):
            item = self.figure_list.item(row)
            group = item.data(self.GROUP_ROLE)
            if group == "all":
                item.setCheckState(self._state_of(self._figure_items()))
            elif group:
                item.setCheckState(self._state_of(
                    self._figure_items(tuple(group)[1])))
        self._syncing = False

    def _on_item_clicked(self, item):
        """A click on a figure name (or a profile of it) brings the figure
        forward; a click on a hidden figure's name shows it.  A click on the
        check box only ticks or unticks."""
        toggled, self._just_toggled = self._just_toggled, False
        sub = item.data(Qt.UserRole + 1)
        key = tuple(sub[:2]) if sub else item.data(Qt.UserRole)
        if not key:
            return                                  # header
        key = tuple(key)
        if key not in self.pages:
            return                                  # not computed yet
        if toggled:
            if item.checkState() == Qt.Checked:     # just ticked: forward
                page = self.pages[key]
                if self.tabs.indexOf(page) >= 0:
                    self.tabs.setCurrentWidget(page)
            return
        self.show_figure(*key)

    def _on_item_changed(self, item):
        if self._syncing:
            return
        self._just_toggled = True
        group = item.data(self.GROUP_ROLE)
        key = item.data(Qt.UserRole)
        sub = item.data(Qt.UserRole + 1)
        if key and (tuple(key)) in self.sublists:
            # a figure with a sub-list: its items follow its tick
            self._syncing = True
            for row in range(self.figure_list.count()):
                other = self.figure_list.item(row)
                data = other.data(Qt.UserRole + 1)
                if data and tuple(data[:2]) == tuple(key):
                    other.setCheckState(item.checkState())
            self._syncing = False
        elif sub and item.checkState() == Qt.Unchecked and not any(
                self.figure_list.item(row).checkState() == Qt.Checked
                for row in range(self.figure_list.count())
                if tuple((self.figure_list.item(row).data(Qt.UserRole + 1)
                          or (None, None))[:2]) == tuple(sub[:2])):
            # the last profile unticked: its figure is hidden too
            self._syncing = True
            for row in range(self.figure_list.count()):
                other = self.figure_list.item(row)
                data = other.data(Qt.UserRole)
                if data and tuple(data) == tuple(sub[:2]):
                    other.setCheckState(Qt.Unchecked)
            self._syncing = False
        elif sub and item.checkState() == Qt.Checked:
            # ticking one item of a sub-list ticks its figure
            self._syncing = True
            for row in range(self.figure_list.count()):
                other = self.figure_list.item(row)
                data = other.data(Qt.UserRole)
                if data and tuple(data) == tuple(sub[:2]):
                    other.setCheckState(Qt.Checked)
            self._syncing = False
        if group:
            # a click on a partly ticked box ticks everything below it
            state = item.checkState()
            state = Qt.Checked if state == Qt.PartiallyChecked else state
            owner = None if group == "all" else tuple(group)[1]
            self._syncing = True
            for figure in self._figure_items(owner):
                figure.setCheckState(state)
            for row in range(self.figure_list.count()):
                other = self.figure_list.item(row)
                data = other.data(Qt.UserRole + 1)
                if data and (owner is None or data[0] == owner):
                    other.setCheckState(state)
            self._syncing = False
        self._sync_groups()
        self.apply_ticks()                 # show / hide at once

    def set_sublist(self, owner, title, names):
        """Tickable sub-items of one figure (e.g. one per individual
        profile); a new name is ticked, the known ones keep their tick."""
        old = self.sublists.get((owner, title), {})
        default = bool(self.checked.get((owner, title)))
        self.sublists[(owner, title)] = {name: old.get(name, default)
                                         for name in names}
        self.rebuild_list()

    def sublist_ticked(self, owner, title):
        return [name for name, on in self.sublists.get((owner, title),
                                                       {}).items() if on]

    def display_values(self):
        if not self.display_fields:
            return {}
        fields = self.display_fields
        return dict(IS_SHADING=fields["IS_SHADING"].isChecked(),
                    SHADING=fields["SHADING"].currentText(),
                    CMAP=fields["CMAP"].currentText())

    def set_display_values(self, values):
        if not self.display_fields:
            return
        fields = self.display_fields
        fields["IS_SHADING"].setChecked(bool(values.get("IS_SHADING")))
        fields["SHADING"].setCurrentText(values.get("SHADING", "gouraud"))
        fields["CMAP"].setCurrentText(values.get("CMAP", "seismic"))

    def apply_list(self):
        """'Update plots': show the ticked figures and ask for the maps to
        be redrawn with the display options."""
        self.apply_ticks()
        if self.display_fields:
            self.display_requested.emit(self.display_values())

    def apply_ticks(self):
        """Show the ticked figures and hide the others (called at once
        when a box of the list is ticked or unticked)."""
        changed, shown = set(), []
        for row in range(self.figure_list.count()):
            item = self.figure_list.item(row)
            key = item.data(Qt.UserRole)
            if key:
                on = item.checkState() == Qt.Checked
                if self.checked.get(tuple(key)) != on:   # shown / hidden
                    self.manual[tuple(key)] = on         # by hand
                    if on and tuple(key) in self.pages:
                        shown.append(tuple(key))
                self.checked[tuple(key)] = on
            sub = item.data(Qt.UserRole + 1)
            if sub:
                owner, title, name = sub
                on = item.checkState() == Qt.Checked
                if self.sublists[(owner, title)].get(name) != on:
                    self.sublists[(owner, title)][name] = on
                    changed.add((owner, title))
        self.refresh_tabs()
        if shown:                          # brought up to date at once
            self.figures_shown.emit(shown)
        for owner, title in changed:
            if self.sublist_ticked(owner, title):   # its figure comes
                self.pending_focus = (owner, title)  # forward when redrawn
                self.focus_pending(owner, clear=False)
            self.sublist_requested.emit(owner, title,
                                        self.sublist_ticked(owner, title))

    def _close_tab(self, index):
        page = self.tabs.widget(index)
        key = next((k for k, p in self.pages.items() if p is page), None)
        if key is None:
            return
        self.checked[key] = False
        self.manual[key] = False
        self.rebuild_list()
        self.refresh_tabs()

    # ---- tabs -------------------------------------------------------------
    def refresh_tabs(self, focus=None):
        wanted = [(owner, title) for owner in self.order
                  for title, _ in self.results.get(owner, [])
                  if self.checked.get((owner, title))]
        current = self.tabs.currentWidget()
        if self.message is not None:
            self.tabs.removeTab(self.tabs.indexOf(self.message))
            self.message.deleteLater()
            self.message = None
        for index in reversed(range(self.tabs.count())):
            page = self.tabs.widget(index)
            key = next((k for k, p in self.pages.items() if p is page), None)
            if key not in wanted:
                self.tabs.removeTab(index)
        for position, key in enumerate(wanted):
            page = self.pages[key]
            if self.tabs.indexOf(page) != position:
                if self.tabs.indexOf(page) >= 0:
                    self.tabs.removeTab(self.tabs.indexOf(page))
                self.tabs.insertTab(position, page, key[1])
        if not wanted and not self.results:
            self.tabs.tabBar().hide()       # nothing computed yet: empty
            return
        if not wanted:
            text = getattr(self, "empty_message", "") or (
                "No figure shown: tick figures in the list on the right and "
                "press Update plots." if self.results else
                "Press Run to compute this step." if len(self.order) == 1
                else "Use the buttons of the panel, or Run All.")
            self.message = QLabel(text)
            self.message.setAlignment(Qt.AlignCenter)
            self.message.setWordWrap(True)
            self.message.setStyleSheet("color: gray; font-size: 14px;")
            self.tabs.addTab(self.message, "")
            self.tabs.tabBar().hide()
            return
        self.tabs.tabBar().show()
        if focus is not None and any(k[0] == focus for k in wanted):
            self.tabs.setCurrentWidget(
                self.pages[next(k for k in wanted if k[0] == focus)])
        elif current is not None and self.tabs.indexOf(current) >= 0:
            self.tabs.setCurrentWidget(current)

    def _make_page(self, item):
        import pandas as pd
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        if isinstance(item, pd.DataFrame):
            table = QTableWidget(item.shape[0], item.shape[1])
            table.setHorizontalHeaderLabels([str(c) for c in item.columns])
            table.setVerticalHeaderLabels([str(i) for i in item.index])
            for row in range(item.shape[0]):
                for column in range(item.shape[1]):
                    cell = QTableWidgetItem(str(item.iat[row, column]))
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row, column, cell)
            table.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch)
            page_layout.addWidget(table)
            return page, None
        canvas = FigureCanvasQTAgg(item)
        # the figure never shrinks below its own size: when the window is
        # smaller, horizontal and vertical scroll bars appear (larger
        # windows: the figure grows with them)
        canvas.setMinimumSize(int(item.get_figwidth() * 75),
                              int(item.get_figheight() * 75))
        canvas.mpl_connect("button_press_event", self._on_click)
        toolbar = NavigationToolbar2QT(canvas, page)
        self.toolbars[id(canvas)] = toolbar
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(canvas)
        page_layout.addWidget(toolbar)
        page_layout.addWidget(scroll, 1)
        canvas.draw_idle()
        return page, canvas

    def _on_click(self, event):
        toolbar = self.toolbars.get(id(event.canvas))
        toolbar_active = toolbar is not None and bool(toolbar.mode)
        if event.inaxes is None or event.button != 1 or toolbar_active:
            return
        if event.xdata is not None and event.ydata is not None:
            self.clicked.emit(self.owner_of_canvas.get(id(event.canvas), ""),
                              float(event.xdata), float(event.ydata))
