"""View › View all variables: the variables kept in memory by the GUI
(session.data), with a short description, their format and their size."""
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QPlainTextEdit, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout)

# what each variable represents ("{ch}" dicts are keyed by channel name)
DESCRIPTIONS = {
    # ---- preprocessing: Load raw data -------------------------------------
    "DATA_FOLDER": "Configuration folder of the raw XT files loaded",
    "LOG_FOLDER": "Log folder of the XT (next to the temperature folder)",
    "CHANNELS_AVAILABLE": "Sub-folders found in the configuration folder",
    "CHANNELS": "Channels loaded from the raw data",
    "CONFIGURATION_TABLE": "Configuration of each channel (XT settings, "
                           "number of profiles, first/last time, sampling)",
    "IS_TIME_CORRECTION": "True when the XT clock is corrected to real UTC",
    "REFERENCE_LOCAL_TIME": "Reference local time of the clock correction",
    "UTC_OFFSET": "Offset added to the XT time stamps to get UTC",
    "USE_LEXPLORE": "True when the LéXPLORE chain is used",
    "LEXPLORE_ROOT": "Folder of the LéXPLORE thermistor-chain files",
    "LEXPLORE_STATUS": "Coverage of the DTS record by the chain data",
    "IS_LEXPLORE_DATA_AVAILABLE": "True when chain data cover the DTS record",
    "DATA_LEXPLORE": "LéXPLORE chain over the DTS record: time (UTC), depth "
                     "(m), temperature (°C, depth × time)",
    "DTS_WINDOW": "First and last time of the DTS record (UTC)",
    "RAW_CACHE": "Every raw profile of each channel: fibre position x (m), "
                 "temperature, start/end times",
    "DATA_DTS_RAW": "First raw profile of each channel (all the columns of "
                    "the XT file)",
    "DATA_DTS_RAW_TRUNCATED": "First raw profile of each channel cut to "
                              "[0, measurement length]",
    # ---- preprocessing: mirror distance and concatenation -----------------
    "MAX_DEPTH": "Mirror distance (bottom of the U) of each channel, time "
                 "mean (m of fibre from the connector)",
    "MAX_DEPTH_ALL": "Mirror distance of every profile (m)",
    "MAX_DEPTH_TIME": "Times of the mirror distances (UTC)",
    "MAX_DEPTH_mean": "Common mirror distance of all the channels (m)",
    "FOLDED_FIRST": "First profile of each channel folded: depth, down leg, "
                    "up leg, mean",
    "CHANNELS_FOLDED": "Channels folded and concatenated",
    "z_common": "Common depth grid of the folded profiles (m from the "
                "connector)",
    "dz": "Spacing of the common depth grid (m)",
    "TIME": "Time of every profile (UTC, centre of the measurement)",
    "Z": "Depth grid of each channel (m from the connector)",
    "T_MATRIX_mean": "Folded temperature, mean of the two legs (°C, depth × "
                     "time), connector coordinate",
    "T_MATRIX_down": "Folded temperature, descending leg (°C, depth × time)",
    "T_MATRIX_up": "Folded temperature, ascending leg (°C, depth × time)",
    # ---- preprocessing: depth calibration and save ------------------------
    "VERTICAL_OFFSET": "Chain fit of every fitted step: time, z offset (m), "
                       "rms (K), T shift (K)",
    "CALIBRATION_BASE": "Time base of the chain fit (record with the "
                        "longest sampling period) and its period",
    "CALIBRATION_WINDOW": "Time window of the chain fit",
    "CALIBRATION_DONE": "Depth calibration run last (chain or manual)",
    "CALIBRATION_METHOD": "Calibration applied by Save",
    "CALIBRATION_OPTION": "Shifts applied by Save (Z and T, or Z only)",
    "FIT_DEPTHS": "Chain sensor depths used in the fit (m)",
    "SCATTER_FIT": "DTS vs chain points of the fit and the line fitted",
    "TIME_WINDOWS": "Time windows of the chain fit (UTC)",
    "Z_SURFACE": "Manual calibration: water surface (m of fibre below the "
                 "connector)",
    "Z_SHIFT": "Depth shift applied to each channel (m)",
    "Z_SHIFT_STD": "Standard deviation of the depth shift (m)",
    "T_SHIFT": "Temperature shift applied to each channel (K)",
    "T_SHIFT_STD": "Standard deviation of the temperature shift (K)",
    "T_USHAPED_UNCALIBRATED": "Folded record before calibration: time, z "
                              "(m from the connector), temperature (°C)",
    "T_USHAPED_CALIBRATED": "Calibrated record: time, z (m from the water "
                            "surface), temperature (°C)",
    "OUTPUT_FOLDER": "Folder where the preprocessed file is written",
    "PRODUCT_NAME": "Name of the preprocessed file written",
    # ---- analysis: Load preprocessed data ---------------------------------
    "A_FOLDERS": "Configuration folders of the preprocessed files loaded",
    "A_FILES": "Preprocessed files loaded (configuration / file)",
    "A_PRODUCT": "Content of the preprocessed files (concatenated in time)",
    "A_CHANNELS_AVAILABLE": "Channels found in the preprocessed files",
    "A_CHAIN_ALL": "LéXPLORE chain over the whole record",
    "A_LEXPLORE": "LéXPLORE chain used by the analyses: time, depth, "
                  "temperature",
    "A_IS_LEXPLORE": "True when chain data are available",
    "A_SHOW_CHAIN": "True when the chain is drawn on the maps",
    "A_TIME": "Time of every profile of each channel (UTC)",
    "A_Z": "Depth grid of each channel (m from the water surface)",
    "A_T": "Calibrated temperature of each channel (°C, depth × time)",
    "A_DZ": "Depth-grid spacing (m)",
    "A_MAX_DEPTH": "Deepest calibrated depth (m)",
    "A_RESOLUTION": "Instrument resolution of each channel (K, std over the "
                    "fibre inside the XT)",
    "A_RESOLUTION_ALL": "Instrument resolution of every channel found (K)",
    "A_RESOLUTION_KEY": "Fibre range used for the resolution (m)",
    "A_LOAD_SELECTED": "Channels drawn on the maps of Load preprocessed data",
    "A_PROFILE_TIMES": "Individual profiles (label, UTC time)",
    "A_RESAMPLE_WARNING": "Warning of the resampling, if any",
    "A_RESAMPLED": "Channels created by Resampling data",
    "A_CHANNEL_INFO": "How each channel was built (text of the (?) buttons)",
    "A_WINDOW": "Time window of the step running",
    "A_LAYER": "Layer of the step running",
    # ---- analysis steps ---------------------------------------------------
    "A_T_PICK": "Isotherm followed (°C)",
    "A_N_PROFILES": "Brunt–Väisälä frequency N of every profile (Hz, depth "
                    "× time)",
    "A_N_MEAN": "Time-mean N profile (Hz)",
    "A_N_STD": "Standard deviation of N over time (Hz)",
    "A_N_DEPTH": "Depth grid of N (m)",
    "A_N_TIME": "Times of the N profiles (UTC)",
    "A_N2_PROFILES": "Signed N² (s⁻²) per record: N² < 0 marks unstable "
                     "water",
    "A_SOUND_SPEED": "Speed of sound c(z, t) (m/s) per channel",
    "A_SOUND_INFO": "Sound speed: mean density ρ̄, salinity and reference "
                    "temperature used per channel",
    "A_SOUND_FLAGS": "Sound speed: T, P, S switched on or off",
    "A_STC": "STC profiles read (time, depth, T, measured c, c "
             "recalculated, position from the .vp2 file) and the matching "
             "DTS profiles",
    "A_N_ISO": "N range at the depth of the isotherm (Hz)",
    "A_LAYERS": "Multi-layer decomposition: layering, method, interfaces "
                "(time, Z1[, Z2]) of each record",
    "A_LAYER_PARAMS": "Settings of the three-layer best fit (rms tolerance, "
                      "min. points, min. gap)",
    "A_F_CORIOLIS": "Coriolis (inertial) frequency f (Hz)",
    "A_LATITUDE": "Latitude used for f (°N, Advanced › Physical "
                  "parameters)",
    "A_POINCARE": "Estimated V1 Poincaré frequency band (Hz)",
    "A_ISO_FFT": "Spectrum of the isotherm depth (frequency, amplitude)",
    "A_ISOTHERM": "Isotherm depth vs time per record (Following an isotherm)",
    "A_ISO_PICK_DEPTH": "Depth of the isotherm analysed in 3.2 vs time",
    "A_FFT_DEPTH": "FFT over time at each depth: frequency, depth, amplitude",
    "A_FFT_DEPTH_COLOUR_LIMITS": "Colour limits of the frequency × depth maps (K)",
    "A_KZ_SPECTRA": "Vertical FFT of every profile: time, k_z, amplitude",
    "A_FFT2": "2D FFT per channel and layer: frequency, |k_z|, amplitude",
    "A_GRADIENT": "Vertical temperature gradient dT/dz maps per channel",
    "A_GRADIENT_PROFILES": "Instants of the gradient profiles",
    "A_STAIRCASES": "Staircases detected at each individual profile",
    "A_SEISMOGRAM": "Profiles of the seismogram-like plot per channel",
    "A_CONFIGURATION_TABLE": "Configuration of the preprocessed data loaded",
    "A_STAIRCASE_TIMES": "Individual profiles of the last staircase "
                         "detection (label, UTC time)",
}


def human_bytes(n):
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0


def memory(value, depth=0):
    """Approximate memory used by a value (bytes)."""
    if isinstance(value, np.ndarray):
        return value.nbytes
    if depth > 6:
        return 0
    if isinstance(value, dict):
        return sum(memory(v, depth + 1) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(memory(v, depth + 1) for v in value)
    if hasattr(value, "memory_usage"):            # pandas
        try:
            return int(value.memory_usage(deep=True).sum())
        except Exception:
            return 0
    if isinstance(value, str):
        return len(value)
    return 8


def describe(value):
    """(format, size) of a value."""
    if isinstance(value, np.ndarray):
        return (f"array {value.dtype}",
                " × ".join(str(n) for n in value.shape) or "scalar")
    if isinstance(value, dict):
        return "dict", f"{len(value)} entries"
    if isinstance(value, (list, tuple)):
        return type(value).__name__, f"{len(value)} items"
    if hasattr(value, "shape") and hasattr(value, "columns"):
        return "table (pandas)", " × ".join(str(n) for n in value.shape)
    if value is None:
        return "None", ""
    if isinstance(value, (bool, np.bool_)):
        return "bool", str(bool(value))
    if isinstance(value, str):
        value = str(value)
        return "text", value if len(value) <= 60 else value[:57] + "…"
    if isinstance(value, (int, float, np.integer, np.floating)):
        try:
            return type(value).__name__, f"{float(value):.6g}"
        except (TypeError, ValueError):
            return type(value).__name__, str(value)
    if isinstance(value, (np.datetime64, np.timedelta64)):
        return type(value).__name__, str(value)
    return type(value).__name__, ""


def value_text(value, depth=0):
    """Readable text of a value for the 'Show value' window: arrays with
    their statistics and (shortened) content, dicts and lists entry by
    entry."""
    pad = "    " * depth
    if isinstance(value, np.ndarray):
        lines = [f"array {value.dtype}, shape {value.shape}"]
        if value.size and value.dtype.kind in "fiu":
            finite = value[np.isfinite(value)] if value.dtype.kind == "f" \
                else value
            n_nan = value.size - finite.size
            if finite.size:
                lines.append(f"min {finite.min():.6g}, max {finite.max():.6g}, "
                             f"mean {finite.mean():.6g}, NaN {n_nan}")
            else:
                lines.append(f"all NaN ({n_nan})")
        elif value.size and value.dtype.kind == "M":
            lines.append(f"from {value.min()} to {value.max()}")
        with np.printoptions(threshold=200, edgeitems=5, linewidth=100,
                             precision=5):
            lines.append(np.array2string(value))
        return "\n".join(pad + line for line in "\n".join(lines).split("\n"))
    if isinstance(value, dict):
        if depth > 3:
            return pad + f"dict with {len(value)} entries"
        out = []
        for key, child in value.items():
            text = value_text(child, depth + 1)
            if "\n" in text or isinstance(child, (dict, np.ndarray, list,
                                                  tuple)):
                out.append(f"{pad}{key}:\n{text}")
            else:
                out.append(f"{pad}{key}: {text.strip()}")
        return "\n".join(out) if out else pad + "{} (empty)"
    if isinstance(value, (list, tuple)):
        if depth > 3 or len(value) > 50:
            head = ", ".join(str(v) for v in list(value)[:20])
            return pad + f"{type(value).__name__} of {len(value)}: {head}" + \
                (" ..." if len(value) > 20 else "")
        if not any(isinstance(v, (dict, np.ndarray, list, tuple))
                   for v in value):
            return pad + repr(list(value) if isinstance(value, list)
                              else tuple(value))
        return "\n".join(f"{pad}[{i}]:\n{value_text(v, depth + 1)}"
                         for i, v in enumerate(value))
    if hasattr(value, "to_string"):                # pandas table
        return "\n".join(pad + line for line in value.to_string().split("\n"))
    return pad + repr(value)


def describe_key(name):
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name]
    return ""


class VariablesDialog(QDialog):
    """Tree of the variables in memory: dicts open to their entries."""

    COLUMNS = ("Variable", "Description", "Made by (first)", "Format",
               "Size", "Memory")

    def __init__(self, session, parent=None, step_label=None):
        super().__init__(parent)
        self.session = session
        self.step_label = step_label or (lambda step: step)
        self.values = {}                     # id(item) -> (name, value)
        self.setWindowTitle("All variables in memory")
        self.resize(1100, 700)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Filter:"))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("part of a name or of a description")
        self.filter.textChanged.connect(self.apply_filter)
        top.addWidget(self.filter, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.fill)
        top.addWidget(refresh)
        layout.addLayout(top)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.context_menu)
        self.tree.setToolTip("Right click on a variable to see its value")
        layout.addWidget(self.tree, 1)
        self.total = QLabel("")
        self.total.setStyleSheet("color: gray;")
        layout.addWidget(self.total)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self.fill()

    def _item(self, parent, name, value, description, level, origin=""):
        fmt, size = describe(value)
        item = QTreeWidgetItem(parent, [name, description, origin, fmt, size,
                                        human_bytes(memory(value))])
        item.setToolTip(1, description)
        item.setToolTip(2, origin)
        self.values[id(item)] = (name, value)
        if level < 3 and isinstance(value, dict):
            for key, child in value.items():
                self._item(item, str(key), child, "", level + 1)
        elif (level < 3 and isinstance(value, (list, tuple))
              and 0 < len(value) <= 12
              and any(isinstance(v, (dict, np.ndarray, list, tuple))
                      for v in value)):
            for index, child in enumerate(value):
                self._item(item, f"[{index}]", child, "", level + 1)
        return item

    def fill(self):
        self.tree.clear()
        self.values = {}
        data = self.session.data
        origin = getattr(self.session, "origin", {})
        total = 0
        for name in sorted(data, key=lambda k: (k.startswith("A_"),
                                                k.lower())):
            value = data[name]
            total += memory(value)
            step = origin.get(name)
            self._item(self.tree, name, value, describe_key(name), 0,
                       self.step_label(step) if step else "—")
        for column, width in enumerate((210, 400, 260, 110, 120, 70)):
            self.tree.setColumnWidth(column, width)
        self.total.setText(f"{len(data)} variables, about "
                           f"{human_bytes(total)} in memory. Variables "
                           "without the prefix A_ come from the "
                           "preprocessing, those with A_ from the analysis. "
                           "'Made by': the step that first created the "
                           "variable in this session (— when it was made "
                           "outside a step). Right click: show the value.")
        self.apply_filter(self.filter.text())

    def context_menu(self, position):
        item = self.tree.itemAt(position)
        if item is None or id(item) not in self.values:
            return
        menu = QMenu(self)
        action = menu.addAction("Show value")
        if menu.exec(self.tree.viewport().mapToGlobal(position)) == action:
            self.show_value(item)

    def show_value(self, item):
        name, value = self.values[id(item)]
        path = [item.text(0)]
        parent = item.parent()
        while parent is not None:
            path.insert(0, parent.text(0))
            parent = parent.parent()
        dialog = QDialog(self)
        dialog.setWindowTitle(" › ".join(path))
        dialog.resize(800, 560)
        layout = QVBoxLayout(dialog)
        fmt, size = describe(value)
        layout.addWidget(QLabel(f"<b>{' › '.join(path)}</b> — {fmt}"
                                + (f", {size}" if size else "")))
        text = QPlainTextEdit()
        text.setReadOnly(True)
        font = QFont("Menlo")
        font.setStyleHint(QFont.Monospace)
        text.setFont(font)
        try:
            content = value_text(value)
        except Exception as error:                 # noqa: BLE001
            content = f"(value cannot be shown: {error})"
        if len(content) > 400_000:
            content = content[:400_000] + "\n... (cut)"
        text.setPlainText(content)
        layout.addWidget(text, 1)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        dialog.show()
        self._value_dialogs = getattr(self, "_value_dialogs", []) + [dialog]

    def apply_filter(self, text):
        text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setHidden(bool(text) and text not in item.text(0).lower()
                           and text not in item.text(1).lower())


PHYSICS_ENTRY = "PHYSICAL_PARAMETERS"
CATEGORIES = ("Preprocessing variables", "Analysis variables",
              "Physical parameters", "STC variables")
STC_VARIABLES = ("A_STC",)          # variables of the STC profiler
MAX_DEPTH = 3                      # levels of a dictionary listed


def category_of(name):
    """Category of a session variable (the physical parameters apart)."""
    if name in STC_VARIABLES:
        return "STC variables"
    return ("Analysis variables" if name.startswith("A_")
            else "Preprocessing variables")


class SaveVariablesDialog(QDialog):
    """Advanced › Save variables: the variables in four categories
    (preprocessing, analysis, physical parameters, STC), each category with
    a tick box selecting all its variables, and every variable — and every
    entry of a dictionary variable (channel, profile, ...) — with its own
    tick box.  Save asks the file name, folder and format (npz, NetCDF,
    HDF5, txt, csv, MATLAB)."""

    COLUMNS = ("Variable", "Description", "Format", "Size", "Memory")

    def __init__(self, session, parent=None, log=print):
        super().__init__(parent)
        self.session = session
        self.log = log
        self.paths = {}            # id(item) -> path (name, key, key, ...)
        self.setWindowTitle("Save variables")
        self.resize(1000, 700)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Tick the variables to save — a category ticks all its "
            "variables, a variable ticks all its entries — then press "
            "Save: the file name, the folder and the format (npz, NetCDF, "
            "HDF5, txt, csv, MATLAB) are asked. The list is updated after "
            "every step.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setAlternatingRowColors(True)
        self.tree.itemChanged.connect(self.update_total)
        layout.addWidget(self.tree, 1)
        self.total = QLabel("")
        self.total.setStyleSheet("color: gray;")
        layout.addWidget(self.total)
        row = QHBoxLayout()
        for text, state in (("All", True), ("None", False)):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, on=state:
                                   self.tick_all(on))
            row.addWidget(button)
        for text, slot in (("Expand all", lambda: self.tree.expandAll()),
                           ("Collapse", self.collapse),
                           ("Refresh", self.fill)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        row.addStretch(1)
        self.save_button = QPushButton("Save…")
        self.save_button.setStyleSheet("font-weight: bold; "
                                       "padding: 4px 16px;")
        self.save_button.clicked.connect(lambda: self.save())
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(self.save_button)
        row.addWidget(close)
        layout.addLayout(row)
        self.fill()

    # ---- content ----------------------------------------------------------
    def entries(self):
        """{category: {name: value}}: every session variable and the
        physical parameters (one entry each)."""
        import dts_core
        out = {category: {} for category in CATEGORIES}
        for name, value in self.session.data.items():
            out[category_of(name)][name] = value
        for name in dts_core.PHYSICS_DEFAULTS:
            out["Physical parameters"][name] = dts_core.PHYSICS[name]
        return out

    def _description(self, category, name):
        if category == "Physical parameters":
            import dts_core
            for key, label, unit, *_ in dts_core.PHYSICAL_PARAMETERS:
                if key == name:
                    return label + (f" ({unit})" if unit else "")
        return describe_key(name)

    def _add(self, parent, path, value, description, level, ticked):
        fmt, size = describe(value)
        item = QTreeWidgetItem(parent, [str(path[-1]), description, fmt,
                                        size, human_bytes(memory(value))])
        item.setToolTip(1, description)
        children = isinstance(value, dict) and value and level < MAX_DEPTH
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable
                      | (Qt.ItemIsAutoTristate if children else Qt.NoItemFlags))
        self.paths[id(item)] = path
        if children:
            for key, child in value.items():
                self._add(item, path + (key,), child, "", level + 1, ticked)
        else:
            item.setCheckState(0, Qt.Checked if path in ticked
                               or path[:1] in ticked else Qt.Unchecked)
        return item

    def fill(self):
        ticked = set(self.ticked_paths()) if self.tree.topLevelItemCount() \
            else set()
        expanded = {self.tree.topLevelItem(i).text(0)
                    for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).isExpanded()}
        self.tree.blockSignals(True)
        self.tree.clear()
        self.paths = {}
        for category, variables in self.entries().items():
            size = sum(memory(v) for v in variables.values())
            top = QTreeWidgetItem(self.tree, [
                f"{category}  ({len(variables)})", "", "", "",
                human_bytes(size)])
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            top.setFlags(top.flags() | Qt.ItemIsUserCheckable
                         | Qt.ItemIsAutoTristate)
            self.paths[id(top)] = ("__category__", category)
            names = sorted(variables, key=str.lower)
            for name in names:
                self._add(top, (name,), variables[name],
                          self._description(category, name), 0, ticked)
            if not names:
                top.setCheckState(0, Qt.Unchecked)
                top.setDisabled(True)
                top.setText(1, "nothing in memory yet")
            top.setExpanded(category in expanded or not expanded)
        self.tree.blockSignals(False)
        for column, width in enumerate((280, 420, 110, 110, 70)):
            self.tree.setColumnWidth(column, width)
        self.update_total()

    def collapse(self):
        self.tree.collapseAll()
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setExpanded(True)

    # ---- ticks ------------------------------------------------------------
    def _leaves(self, item=None):
        items = ([self.tree.topLevelItem(i)
                  for i in range(self.tree.topLevelItemCount())]
                 if item is None else
                 [item.child(i) for i in range(item.childCount())])
        for child in items:
            if child.childCount():
                yield from self._leaves(child)
            elif self.paths.get(id(child), ("__category__",))[0] \
                    != "__category__":
                yield child

    def ticked_paths(self):
        """Paths (variable, key, ...) of the entries ticked."""
        return [self.paths[id(item)] for item in self._leaves()
                if item.checkState(0) == Qt.Checked]

    # old name kept for the tests and the callers
    def ticked(self):
        return sorted({path[0] for path in self.ticked_paths()})

    def tick_all(self, on):
        self.tree.blockSignals(True)
        for item in self._leaves():
            item.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self.tree.blockSignals(False)
        self.fill()                       # parents follow (tristate)

    def tick_category(self, category, on=True):
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if self.paths.get(id(top)) == ("__category__", category):
                top.setCheckState(0, Qt.Checked if on else Qt.Unchecked)

    def set_ticked(self, names):
        self.tree.blockSignals(True)
        for item in self._leaves():
            item.setCheckState(0, Qt.Checked if self.paths[id(item)][0]
                               in names else Qt.Unchecked)
        self.tree.blockSignals(False)
        self.fill()

    def selection(self):
        """{name: value} of the entries ticked; a dictionary keeps only its
        entries ticked (nested)."""
        values = {}
        for variables in self.entries().values():
            values.update(variables)
        out = {}
        for path in self.ticked_paths():
            value = values.get(path[0])
            for key in path[1:]:
                value = value[key]
            target = out
            for key in path[:-1]:
                target = target.setdefault(key, {})
            target[path[-1]] = value
        # physical parameters: one group
        physics = {n: out.pop(n) for n in list(out)
                   if n in self.entries()["Physical parameters"]
                   and n not in self.session.data}
        if physics:
            out[PHYSICS_ENTRY] = physics
        return out

    def update_total(self, *_):
        paths = self.ticked_paths()
        names = {p[0] for p in paths}
        self.total.setText(f"{len(names)} variable(s) ticked "
                           f"({len(paths)} entries)")
        self.save_button.setEnabled(bool(paths))

    # ---- save -------------------------------------------------------------
    def save(self, path=None, chosen_filter=""):
        """Write the entries ticked; returns the files written."""
        import os
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import gui_export
        from gui_widgets import FigurePanel
        selection = self.selection()
        if not selection:
            return []
        if path is None:
            folder = (FigurePanel.last_save_folder
                      or os.path.expanduser("~"))
            path, chosen_filter = QFileDialog.getSaveFileName(
                self, "Save variables",
                os.path.join(folder, "DTS_variables"),
                gui_export.file_filter())
            if not path:
                return []
        fmt = gui_export.format_of(path, chosen_filter)
        tree = gui_export.to_tree(selection)
        try:
            files = gui_export.write(path, fmt, tree,
                                     title="DTS GUI variables: "
                                           + ", ".join(selection))
        except Exception as error:                 # noqa: BLE001
            QMessageBox.warning(self, "Save variables",
                                f"Could not save the variables:\n{error}")
            return []
        FigurePanel.last_save_folder = os.path.dirname(files[0])
        self.log(f"{len(selection)} variable(s) saved ({fmt}): "
                 + ", ".join(files) + "\n")
        return files
