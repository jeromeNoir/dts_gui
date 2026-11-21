"""Advanced > Python script: run a user script inside the GUI.

The script (.py) is read from its file at every Execute and executed with
``exec`` in the GUI's own process, in a namespace that gives it the data in
memory, the GUI's library and the GUI itself (``script_namespace``).  What
it puts in ``results`` is kept in the session variable SCRIPT_RESULTS (one
entry per script, listed in View all variables and Save variables); the
figures made with ``figure(name)`` are shown under Advanced > Python
script.  A script may also add an item of its own to the Advanced menu
with ``add_advanced_step``.  See Claude_for_developer.md and the folder
Example_Scripts/ next to the GUI."""
import contextlib
import datetime
import io
import os
import time
import traceback

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

SCRIPT_STEP = "adv.script"            # the step (menu item) of the scripts
RESULTS_VARIABLE = "SCRIPT_RESULTS"    # session variable: {script: results}
RUNS_VARIABLE = "SCRIPT_RUNS"          # session variable: the runs made
EXAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "Example_Scripts")

SCRIPT_TEMPLATE = '''"""A script for the DTS GUI (Advanced > Python script).

Run it with Execute. The names below are given to every script:
  session, S     the session (dts_steps.Session) and its variables
                 S = session.data, e.g. S["A_TIME"], S["A_Z"], S["A_T"]
                 (dicts by channel: time (nt,) UTC datetime64, depth (nz,)
                 m from the surface, temperature (nz, nt) degC)
  np, core, steps, figs
                 numpy, dts_core (calculations, no Qt), dts_steps (the
                 steps), gui_figures (the figures of the steps)
  params(step)   the current inputs of a step's panel, e.g.
                 params("ana.4.2.6") -> {"CHANNELS": [...], ...}
  run_step(step, p=None)
                 the GUI's own function of a step on the data in memory
                 (p: its inputs, default params(step)) -> [(title, figure)]
  records(p)     [(name, time, depth, T)] of the channels ticked in p
                 (+ the LeXPLORE chain when p["INCLUDE_CHAIN"])
  results        a dict: put here what the script produces (kept in the
                 session variable SCRIPT_RESULTS, listed in Save variables)
  figure(name)   a new matplotlib figure shown under Advanced > Python
                 script once the script ends
  show(name, fig)  show a figure made elsewhere (e.g. by figs.*)
  log(text)      a line in the log (print() goes to the output too)
  gui            the main window; QtWidgets, QtCore, QtGui
  add_advanced_step(section, step_functions)
                 a new item of the Advanced menu (see the examples)
  copy_section(source_id, new_id, title)
                 a copy of the panel description of a step
See Claude_for_developer.md and Example_Scripts/ next to the GUI.
"""

# example: the time mean temperature profile of every channel ticked in
# Load data and analysis settings
for channel, T in S["A_T"].items():
    results[f"T_time_mean_{channel}"] = np.nanmean(T, axis=1)

fig = figure("Time-mean temperature")
ax = fig.add_subplot(111)
for channel, T in S["A_T"].items():
    ax.plot(np.nanmean(T, axis=1), S["A_Z"][channel], label=channel)
ax.invert_yaxis()
ax.set_xlabel("T (degC)")
ax.set_ylabel("depth (m)")
ax.legend()
'''


def script_key(path):
    """Name of a script (its file name without .py)."""
    return os.path.splitext(os.path.basename(path or ""))[0]


class ScriptBox(QWidget):
    """The panel of Advanced > Python script: choice of the script (the
    examples of the GUI and the scripts opened), its text (read only),
    Execute, the output and the results kept."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.extra = []                    # scripts opened by the user
        self.figures = {}                  # script -> [(title, figure)]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        box = QGroupBox("Script")
        grid = QVBoxLayout(box)
        self.combo = QComboBox()
        self.combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setToolTip("The scripts of the GUI's Example_Scripts "
                              "folder and those opened")
        grid.addWidget(self.combo)
        row = QHBoxLayout()
        self.open_button = QPushButton("Open…")
        self.open_button.setToolTip("Choose a Python script (.py) anywhere")
        self.new_button = QPushButton("New…")
        self.new_button.setToolTip("Write a template script (with the names "
                                   "given to scripts and an example) and "
                                   "select it")
        row.addWidget(self.open_button)
        row.addWidget(self.new_button)
        row.addStretch(1)
        grid.addLayout(row)
        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: gray;")
        grid.addWidget(self.path_label)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.preview.setMinimumHeight(180)
        self.preview.setToolTip("The script (read only: edit it in your "
                                "editor; it is read again at Execute)")
        grid.addWidget(self.preview, 1)
        layout.addWidget(box, 1)
        self.execute_button = QPushButton("▶  Execute")
        self.execute_button.setStyleSheet("font-weight: bold; "
                                          "padding: 6px 16px;")
        self.execute_button.setToolTip(
            "Run the script (read again from its file) on the data in "
            "memory: what it puts in `results` is kept (SCRIPT_RESULTS), "
            "its figures are shown on the right")
        layout.addWidget(self.execute_button)
        box = QGroupBox("Output")
        column = QVBoxLayout(box)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.output.setMaximumBlockCount(5000)
        self.output.setMinimumHeight(110)
        column.addWidget(self.output)
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["result", "format", "size"])
        self.result_tree.setMinimumHeight(100)
        self.result_tree.setToolTip("What the scripts produced (results), by "
                                    "script; also in Save variables "
                                    "(SCRIPT_RESULTS)")
        column.addWidget(self.result_tree)
        self.clear_button = QPushButton("Remove the results of this script")
        column.addWidget(self.clear_button)
        layout.addWidget(box)
        self.combo.currentIndexChanged.connect(lambda *_: self.show_script())
        self.open_button.clicked.connect(lambda *_: self.open_script())
        self.new_button.clicked.connect(lambda *_: self.new_script())
        self.execute_button.clicked.connect(lambda *_: self.execute())
        self.clear_button.clicked.connect(lambda *_: self.clear_results())
        self.fill()

    # ---- the scripts --------------------------------------------------------
    def found(self):
        try:
            return [os.path.join(EXAMPLES, name)
                    for name in sorted(os.listdir(EXAMPLES))
                    if name.endswith(".py") and not name.startswith(".")]
        except OSError:
            return []

    def current_path(self):
        return self.combo.currentData(Qt.UserRole)

    def fill(self, select=None):
        keep = select or self.current_path()
        paths = self.found() + [p for p in self.extra
                                if p not in self.found()]
        self.combo.blockSignals(True)
        self.combo.clear()
        for path in paths:
            self.combo.addItem(os.path.basename(path), path)
            self.combo.setItemData(self.combo.count() - 1, path,
                                   Qt.ToolTipRole)
        if not paths:
            self.combo.addItem("(no script found: Open… or New…)", None)
        if keep in paths:
            self.combo.setCurrentIndex(paths.index(keep))
        self.combo.blockSignals(False)
        self.show_script()

    def select(self, path):
        if path and path not in self.extra:
            self.extra.append(path)
        self.fill(select=path)

    def show_script(self):
        path = self.current_path()
        self.path_label.setText(path or "")
        try:
            with open(path, encoding="utf-8") as handle:
                self.preview.setPlainText(handle.read())
        except (OSError, TypeError):
            self.preview.setPlainText("")
        self.execute_button.setEnabled(bool(path))
        self.fill_results()

    def open_script(self):
        start = os.path.dirname(self.current_path() or "") or EXAMPLES
        path, _ = QFileDialog.getOpenFileName(
            self, "Python script", start,
            "Python script (*.py);;All files (*)")
        if path:
            self.select(path)

    def new_script(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "New Python script",
            os.path.join(os.path.expanduser("~"), "my_dts_script.py"),
            "Python script (*.py)")
        if not path:
            return
        if not path.endswith(".py"):
            path += ".py"
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(SCRIPT_TEMPLATE)
        except OSError as error:
            QMessageBox.warning(self, "New script", str(error))
            return
        self.main.write_log(f"template script written: {path}\n")
        self.select(path)

    # ---- execution ----------------------------------------------------------
    def execute(self, path=None):
        """Run a script; True when it ran without error."""
        main = self.main
        path = path or self.current_path()
        if not path:
            return False
        if main.busy_running():
            QMessageBox.information(self, "Python script",
                                    "A step is running: wait for its end.")
            return False
        name = script_key(path)
        results, lines, made = {}, [], []
        namespace = main.script_namespace(path, results, lines, made)
        buffer = io.StringIO()
        main.write_log(f"===== Advanced › Python script: {name} =====\n"
                       f"{path}\n")
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        started = time.time()
        ok, error = True, ""
        try:
            with open(path, encoding="utf-8") as handle:
                code = handle.read()
            with contextlib.redirect_stdout(buffer), \
                    contextlib.redirect_stderr(buffer):
                exec(compile(code, path, "exec"), namespace)
        except Exception:                          # noqa: BLE001
            ok = False
            error = traceback.format_exc(limit=-6)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        seconds = time.time() - started
        out = buffer.getvalue()
        self.output.setPlainText(
            out + ("\n".join(lines) + "\n" if lines and not out else "")
            + (f"\nERROR:\n{error}" if error else "")
            + f"\n-- {'done' if ok else 'FAILED'} in {seconds:.2f} s, "
              f"{len(results)} result(s): {', '.join(results) or 'none'}")
        if out.strip():
            main.write_log(out.rstrip() + "\n")
        if not ok:
            main.write_log(f"script {name} FAILED:\n{error.rstrip()}\n")
        data = main.session.data
        if results or ok:
            kept = dict(data.get(RESULTS_VARIABLE) or {})
            kept[name] = results
            data[RESULTS_VARIABLE] = kept
            main.session.origin[RESULTS_VARIABLE] = SCRIPT_STEP
        runs = [r for r in (data.get(RUNS_VARIABLE) or [])
                if r["script"] != name]
        runs.append(dict(
            script=name, path=path, ok=ok,
            time=datetime.datetime.now().isoformat(timespec="seconds"),
            seconds=round(seconds, 3), results=sorted(results),
            figures=[title for title, _ in made],
            error=error.strip().splitlines()[-1] if error else ""))
        data[RUNS_VARIABLE] = runs
        main.session.origin[RUNS_VARIABLE] = SCRIPT_STEP
        if made or name in self.figures:
            self.figures[name] = [(f"{name}: {title}", fig)
                                  for title, fig in made]
            main.show_script_figures(
                [item for items in self.figures.values() for item in items])
        main.record_script(path, ok)
        main.session.variables_used[SCRIPT_STEP] = (
            [RESULTS_VARIABLE], SCRIPT_STEP)
        main.statusBar().showMessage(
            f"script {name} {'done' if ok else 'FAILED'} ({seconds:.2f} s): "
            f"{len(results)} result(s)")
        main.refresh_save_variables()
        self.fill_results()
        return ok

    def clear_results(self):
        name = script_key(self.current_path())
        data = self.main.session.data
        kept = dict(data.get(RESULTS_VARIABLE) or {})
        kept.pop(name, None)
        data[RESULTS_VARIABLE] = kept
        if self.figures.pop(name, None) is not None:
            self.main.show_script_figures(
                [item for items in self.figures.values() for item in items])
        self.main.write_log(f"script {name}: results removed\n")
        self.main.refresh_save_variables()
        self.fill_results()

    def fill_results(self):
        import gui_variables
        self.result_tree.clear()
        kept = self.main.session.data.get(RESULTS_VARIABLE) or {}
        for name, results in kept.items():
            top = QTreeWidgetItem([name, "script", ""])
            for key, value in results.items():
                fmt, size = gui_variables.describe(value)
                QTreeWidgetItem(top, [str(key), fmt, size])
            self.result_tree.addTopLevelItem(top)
            top.setExpanded(True)
        for column in range(3):
            self.result_tree.resizeColumnToContents(column)
        self.clear_button.setEnabled(
            script_key(self.current_path()) in kept)


__all__ = ["ScriptBox", "SCRIPT_TEMPLATE", "SCRIPT_STEP", "np", "QtCore",
           "QtGui", "QtWidgets"]
