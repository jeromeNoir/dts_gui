"""DTS GUI — preprocessing and analysis of Silixa XT-DTS records.

Version 2.6 (14.11.2026).

Start:   python dts_gui.py
Needs:   Python 3.9+, PySide6, numpy, pandas, matplotlib, netCDF4

Files:   dts_gui.py       main window, menus, running of the steps
         gui_sections.py  description of every step (inputs, menus)
         gui_widgets.py   input widgets and figure panel
         dts_steps.py     the steps (computation + calls to the figures)
         gui_figures.py   the figures
         dts_core.py      computation library (reading, folding, FFT, ...)
         gui_help.py      texts of the Help menu

All times entered in the GUI are UTC, except the reference local time of
the clock correction (Preprocessing > 0).
"""

import contextlib
import json
import threading
import os

import numpy as np
import sys
import traceback

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QStackedWidget,
    QToolBar, QToolButton, QVBoxLayout, QWidget)

import warnings

import matplotlib
matplotlib.use("QtAgg")
warnings.filterwarnings("ignore", message="constrained_layout not applied")

import dts_steps                                           # noqa: E402
import gui_help                                            # noqa: E402
import gui_physics                                         # noqa: E402
from gui_sections import MENUS, all_groups                 # noqa: E402
from gui_widgets import FigurePanel, ParameterPanel        # noqa: E402
import gui_widgets                                         # noqa: E402

VERSION = "3.20"
VERSION_DATE = "16.11.2026"
dts_steps.core.WRITER = f"DTS GUI v{VERSION}"


# ---------------------------------------------------------------------------
# background execution of the steps
# ---------------------------------------------------------------------------
class _Stream(QObject):
    """File-like object sending printed text to the log."""
    text = Signal(str)

    def write(self, text):
        if text:
            self.text.emit(text)
        if threading.current_thread() is not threading.main_thread():
            dts_steps.core.check_cancel()  # every printed line: stop point
        return len(text)

    def flush(self):
        pass


class Worker(QThread):
    """Runs one step outside the GUI thread."""

    log = Signal(str)
    step_done = Signal(str, object)           # step id, [(title, Figure)]
    step_failed = Signal(str, str)            # step id, message
    step_interrupted = Signal(str)

    def __init__(self, session, key, params):
        super().__init__()
        self.session, self.key, self.params = session, key, params
        self.ok = False

    def run(self):
        stream = _Stream()
        stream.text.connect(self.log)
        with contextlib.redirect_stdout(stream), \
                contextlib.redirect_stderr(stream):
            function = dts_steps.STEPS[self.key][0]
            self.session.params_used[self.key] = dict(self.params)
            before = set(self.session.data)
            try:
                figures = function(self.session, self.params)
            except dts_steps.StepError as error:
                self.step_failed.emit(self.key, str(error))
                return
            except dts_steps.core.Interrupted:
                self.step_interrupted.emit(self.key)
                return
            except Exception:                           # noqa: BLE001
                self.step_failed.emit(self.key, traceback.format_exc())
                return
            owner = dts_steps.FIGURE_OWNER.get(self.key, self.key)
            for name in set(self.session.data) - before:   # new variables
                self.session.origin.setdefault(name, self.key)
            self.session.figures[owner] = figures
            self.ok = True
            self.step_done.emit(self.key, figures)


# ---------------------------------------------------------------------------
# main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DTS — preprocessing and analysis  (v{VERSION})")
        self.resize(1500, 950)
        self.session = dts_steps.Session()
        self.sections = [(menu_name.replace("&", ""), section)
                         for menu_name, sections in MENUS
                         for section in sections
                         if not section.get("is_menu")]
        self.section_by_id = {s["id"]: s for _, s in self.sections}
        self.panel_of_step = {}
        for _, section in self.sections:
            for step in section.get("actions") or [section["id"]]:
                self.panel_of_step[step] = section["id"]
            for _, fields in all_groups(section):
                for field in fields:
                    if field["kind"] == "button" and not str(
                            field.get("step", "")).startswith("@"):
                        for step in field.get("steps") or [field["step"]]:
                            self.panel_of_step.setdefault(step, section["id"])
        for step, owner in dts_steps.FIGURE_OWNER.items():
            self.panel_of_step[step] = self.panel_of_step[owner]
        self.menu_of = {s["id"]: m for m, s in self.sections}
        self.actions = {}
        self.pages = {}               # id -> (ParameterPanel, FigurePanel)
        self.shared_panels = {}       # menu name -> shared FigurePanel
        self.map_selectors = []       # SpanSelectors on the T maps
        self.surface_selection = False
        self.done, self.outdated = set(), set()
        # "pre" / "files" / "analysis" -> list: empty until data are loaded
        self.channel_sources = {"pre": [], "files": [], "analysis": []}
        self.window_items = [dts_steps.WHOLE_RECORD]  # lists 'Time window'
        self.layer_items = [dts_steps.WHOLE_COLUMN]   # lists 'Layer'
        self.window_selectors = []    # SpanSelectors on the analysis maps
        self.worker = None
        self.queue = []
        self.analysis_runs = {}      # analysis step -> inputs, run order
        self.saved_runs = []         # steps of an opened analysis settings
        self.current = None
        gui_widgets.HELP_EXTRA["INCLUDE_CHAIN"] = self.chain_variables_help
        gui_widgets.HELP_EXTRA["STC_FOLDER"] = self.stc_resolution_help
        gui_widgets.HELP_EXTRA["DTS_FOLDER"] = self.dts_resolution_help
        gui_widgets.HELP_EXTRA["LEXPLORE_FOLDER"] = \
            self.chain_resolution_help
        gui_widgets.CHANNEL_INFO_HANDLER = self.show_channel_info
        self._build_menus()
        self._build_menu_toolbar()
        self._build_central()
        self.show_section("pre.1")

    # ---- menus ------------------------------------------------------------
    def _build_menus(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        reset_action = QAction("Reset all…", self)
        reset_action.triggered.connect(self.reset_all)
        file_menu.addAction(reset_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self, shortcut=QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        for menu_name, sections in MENUS:
            menu = bar.addMenu(menu_name)
            if "Advanced" in menu_name:
                for text, slot in (("Physical parameters…",
                                    self.show_physics),
                                   ("Save variables…",
                                    self.show_save_variables)):
                    action = QAction(text, self)
                    action.triggered.connect(slot)
                    menu.addAction(action)
                menu.addSeparator()
            with_children = {s["parent"] for s in sections if s["parent"]}
            submenus = {None: menu}
            for section in sections:
                if section.get("in_file_menu"):
                    continue                    # in the File menu
                target = submenus[section["parent"]]
                label = section["title"]
                if section["number"] in with_children:
                    submenu = target.addMenu(
                        section.get("menu_title", section["title"]))
                    submenus[section["number"]] = submenu
                    if not section.get("is_menu"):
                        self._add_action(submenu, section, label)
                        submenu.addSeparator()
                else:
                    self._add_action(target, section, label)
            # settings of this menu only (the Advanced panels and the
            # physical parameters are saved with the analysis settings)
            plain = menu_name.replace("&", "")
            if plain == "Advanced":
                continue
            word = ("preprocessing" if "reprocess" in plain else "analysis")
            menu.addSeparator()
            for text, slot in ((f"Open {word} settings…", self.load_settings),
                               (f"Save {word} settings…", self.save_settings)):
                action = QAction(text, self)
                action.triggered.connect(
                    lambda checked=False, f=slot, m=menu_name: f(m))
                menu.addAction(action)

        view_menu = bar.addMenu("&View")
        for text, shortcut, slot in (
                ("Show / hide the log", "Ctrl+L", self.toggle_log),
                ("Clear the log", None, lambda: self.log.clear()),
                ("View all variables", None, self.show_variables)):
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(slot)
            view_menu.addAction(action)

        help_menu = bar.addMenu("&Help")
        for text, html in (("Preprocessing", gui_help.PREPROCESSING_HELP),
                           ("Analysis", gui_help.ANALYSIS_HELP)):
            action = QAction(text, self)
            action.triggered.connect(
                lambda checked=False, t=text, h=html: self.show_help(t, h))
            help_menu.addAction(action)
        help_menu.addSeparator()
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(
            self, "About the DTS GUI",
            f"<b>DTS GUI</b> — version {VERSION} ({VERSION_DATE})<br><br>"
            "Preprocessing and analysis of Silixa XT-DTS records "
            "(MIRAGE 2026, Lake Geneva).<br><br>"
            "Written by Jerome Noir.<br><br>"
            "All times are UTC, except the reference local time of the "
            "clock correction."))
        help_menu.addAction(about)

    def show_help(self, title, html):
        """Help text in its own window (non-modal, scrollable)."""
        from PySide6.QtWidgets import QDialog, QTextBrowser
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Help — {title}")
        dialog.resize(820, 760)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        close = QPushButton("Close")
        close.clicked.connect(dialog.close)
        layout.addWidget(close, alignment=Qt.AlignRight)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.show()
        self.help_dialogs = getattr(self, "help_dialogs", []) + [dialog]
        return dialog

    def _build_menu_toolbar(self):
        """The drop-down menus of the menu bar, repeated at the top of the
        window (on macOS the menu bar is at the top of the screen)."""
        toolbar = QToolBar("Menus")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.toggleViewAction().setEnabled(False)
        # bigger, bold menus (menu bar and drop-down lists)
        self.menuBar().setStyleSheet(
            "QMenuBar { font-size: 15px; font-weight: bold; } "
            "QMenu { font-size: 14px; font-weight: bold; }")
        for action in self.menuBar().actions():
            if action.menu() is None:
                continue
            button = QToolButton()
            button.setText(action.text().replace("&", "") + "  ▾")
            button.setMenu(action.menu())
            button.setPopupMode(QToolButton.InstantPopup)
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            button.setStyleSheet("QToolButton { padding: 4px 12px; "
                                 "font-size: 16px; font-weight: bold; } "
                                 "QToolButton::menu-indicator { image: none; }")
            toolbar.addWidget(button)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _add_action(self, menu, section, label):
        action = QAction(label, self)
        action.setCheckable(True)
        action.setData(label)
        action.triggered.connect(
            lambda checked=False, key=section["id"]: self.show_section(key))
        menu.addAction(action)
        self.actions[section["id"]] = action

    # ---- central area -----------------------------------------------------
    def _build_central(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 4, 8, 4)
        # left column: title of the step, then its state and Previous /
        # Next, then the panel of the step
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        self.breadcrumb = QLabel()
        self.breadcrumb.setStyleSheet("font-size: 15px;")
        self.breadcrumb.setWordWrap(True)
        left_layout.addWidget(self.breadcrumb)
        row = QHBoxLayout()
        self.state_label = QLabel()
        self.previous_button = QPushButton("◀  Previous")
        self.next_button = QPushButton("Next  ▶")
        self.previous_button.clicked.connect(lambda: self.step(-1))
        self.next_button.clicked.connect(lambda: self.step(+1))
        row.addWidget(self.state_label, 1)
        row.addWidget(self.previous_button)
        row.addWidget(self.next_button)
        left_layout.addLayout(row)

        self.left_stack = QStackedWidget()
        self.left_stack.setMinimumWidth(340)
        left_layout.addWidget(self.left_stack, 1)
        self.right_stack = QStackedWidget()
        horizontal = QSplitter(Qt.Horizontal)
        self.horizontal = horizontal
        horizontal.addWidget(left)
        horizontal.addWidget(self.right_stack)
        horizontal.setStretchFactor(1, 1)
        horizontal.setSizes([420, 1080])

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.log.setMaximumBlockCount(20000)
        self.log.setMinimumHeight(40)
        vertical = QSplitter(Qt.Vertical)
        vertical.addWidget(horizontal)
        vertical.addWidget(self.log)
        vertical.setStretchFactor(0, 1)
        vertical.setSizes([760, 150])
        layout.addWidget(vertical, 1)
        self.setCentralWidget(central)

        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setMaximumWidth(160)
        self.busy.hide()
        self.statusBar().addPermanentWidget(self.busy)
        self.interrupt_button = QPushButton("■  Interrupt")
        self.interrupt_button.setToolTip(
            "Stop the running step at its next stop point (the following "
            "steps are not run)")
        self.interrupt_button.setEnabled(False)
        self.interrupt_button.clicked.connect(self.interrupt)
        self.statusBar().addPermanentWidget(self.interrupt_button)
        self.statusBar().showMessage("Ready")
        self.write_log(f"DTS GUI v{VERSION}. All times are UTC, except the "
                       f"reference local time of the clock correction.\n")
        self.write_log(f"Python {sys.version.split()[0]} ({sys.executable})\n")
        import default_paths
        self.write_log(default_paths.status() + "\n")
        for module in ("numpy", "pandas", "matplotlib", "netCDF4"):
            try:
                __import__(module)
            except ImportError:
                self.write_log(f"WARNING: the module '{module}' is missing "
                               f"in this Python: install it with  pip "
                               f"install {module}\n")

    # ---- steps and panels -------------------------------------------------
    # A panel (menu item) holds one step (its id is the panel id) or several
    # steps (section["actions"], plus the steps of its box buttons).
    def steps_of(self, section_id):
        section = self.section_by_id[section_id]
        return section.get("actions") or [section_id]

    def section_of(self, step):
        return self.panel_of_step[step]

    def step_label(self, step):
        section = self.section_by_id[self.section_of(step)]
        label = section["title"]
        names = {"pre.1.load": "Load", "pre.1.mirror": "Mirror distance",
                 "pre.1.concat": "Concatenate", "pre.1.replot": "Update plots",
                 "pre.3.replot": "Update plots",
                 "pre.2.1": "Using LeXPLORE T-Chain", "pre.2.2": "Manual",
                 "ana.0": "Load data", "ana.0.1": "Load data",
                 "ana.0.select": "Update maps",
                 "ana.3.1": "FFT of the temperature at each depth",
                 "ana.3.2": "FFT of the depth of an isotherm",
                 "ana.0.instants": "Individual profiles",
                 "ana.0.replot": "Update plot",
                 "ana.4.2.9": "Seismogram-like profiles",
                 "ana.4.1.1.fit": "Fit scaling"}
        if step not in names and step.endswith(".replot"):
            return label + " › Update plot"
        return label + (f" › {names[step]}" if step in names else "")

    # ---- pages ------------------------------------------------------------
    def page(self, key):
        """Panels of a menu item, created on first use (a step id gives the
        panel of its menu item)."""
        if key not in self.section_by_id and key in self.panel_of_step:
            key = self.section_of(key)
        if key not in self.pages:
            section = self.section_by_id[key]
            panel = ParameterPanel(section)
            figure_panel = self.figure_panel_for(key)
            panel.run_requested.connect(lambda k=key: self.run_panel(k))
            panel.action_requested.connect(
                lambda steps: self.on_action(steps))
            panel.toggle_changed.connect(
                lambda name, on, k=key: self.on_toggle(k, name, on))
            if key == "pre.2":
                panel.fields["TIME_WINDOWS"].changed.connect(
                    self.draw_fit_windows)
                panel.fields["Z_SURFACE"].spin.valueChanged.connect(
                    lambda *_: self.draw_surface_line())
            for source, channels in self.channel_sources.items():
                panel.set_channel_choices(source, channels)
            panel.set_window_choices(self.window_items)
            panel.set_layer_choices(self.layer_items)
            panel.set_profile_choices(self.shared_profiles or [])
            if "TIME_WINDOW" in panel.fields:
                panel.fields["TIME_WINDOW"].currentTextChanged.connect(
                    self.draw_analysis_windows)

            if key in self.PROFILE_TABLES:      # one shared list of profiles
                table = panel.fields[self.PROFILE_TABLES[key]]
                if self.shared_profiles is not None:
                    self._syncing_profiles = True
                    try:
                        table.set_value(list(self.shared_profiles))
                    finally:
                        self._syncing_profiles = False
                table.changed.connect(
                    lambda k=key: self.sync_profiles(k))
            if key == "ana.0":
                figure_panel.sublist_requested.connect(
                    self.on_profile_sublist)
                panel.fields["PROFILE_TIMES"].changed.connect(
                    self.update_profile_sublist)
                panel.fields["WINDOWS"].changed.connect(
                    self.on_windows_changed)
            if section.get("click_to_set"):
                field, axis, click_step = section["click_to_set"]
                figure_panel.clicked.connect(
                    lambda owner, x, y, k=key, f=field, a=axis, c=click_step:
                    owner == c and self.on_figure_click(
                        k, f, x if a == "x" else y, c))
            self.left_stack.addWidget(panel)
            if self.right_stack.indexOf(figure_panel) < 0:
                self.right_stack.addWidget(figure_panel)
            self.pages[key] = (panel, figure_panel)
            if key == "ana.0":
                self.update_profile_sublist()
            for step in self.steps_of(key):
                if step in self.session.figures and \
                        step not in figure_panel.results:
                    figure_panel.set_figures(step, self.session.figures[step])
            panel.set_running(self.busy_running())
        return self.pages[key]

    # menus whose steps share one result area (all their tabs stay open)
    SHARED_FIGURE_MENUS = ("Preprocessing", "Data analysis", "Advanced")

    def figure_panel_for(self, key):
        """The result area of a panel: shared by all the panels of a menu
        (Preprocessing, Data analysis), so that the tabs of every step stay
        open while moving through the steps."""
        menu = self.menu_of[key]
        if menu not in self.SHARED_FIGURE_MENUS:
            section = self.section_by_id[key]
            return FigurePanel(section, section.get("figures", ()),
                               {s: self.step_label(s)
                                for s in self.steps_of(key)})
        if menu not in self.shared_panels:
            menu_sections = [section for m, section in self.sections
                             if m == menu]
            steps = [step for section in menu_sections
                     for step in self.steps_of(section["id"])]
            catalogue = [entry for section in menu_sections
                         for entry in section.get("figures", ())]
            panel = FigurePanel(dict(id=menu, actions=steps, description=""),
                                catalogue,
                                {s: self.step_label(s) for s in steps},
                                display=(menu == "Preprocessing"))
            panel.clicked.connect(self.on_shared_click)
            if menu in ("Data analysis", "Advanced"):
                panel.clicked.connect(self.on_profile_click)
            if menu == "Preprocessing":
                panel.display_requested.connect(self.on_display_update)
            self.shared_panels[menu] = panel
        return self.shared_panels[menu]

    def show_section(self, key):
        if key not in self.section_by_id and key in self.panel_of_step:
            key = self.section_of(key)          # a step: its menu item
        panel, figure_panel = self.page(key)
        self.left_stack.setCurrentWidget(panel)
        self.fit_left_panel(panel)
        self.current = key
        self.draw_analysis_windows()
        self.right_stack.setCurrentWidget(figure_panel)
        if figure_panel in self.shared_panels.values():
            section = self.section_by_id[key]
            figure_panel.set_description(section.get("description", ""))
            focus = [section["focus_owner"]] if section.get(
                "focus_owner") else []
            figure_panel.select_owner(focus + self.steps_of(key))
            for step in self.steps_of(key):
                self.focus_figure(figure_panel, step)
        # the map selection only works on its own panel
        for other in ("pre.2", "ana.0", "ana.4.1.1"):
            if key != other and other in self.pages:
                for toggle in self.pages[other][0].toggles.values():
                    if toggle.isChecked():
                        toggle.setChecked(False)
        for action_key, action in self.actions.items():
            action.setChecked(action_key == key)
        self.current = key
        section = self.section_by_id[key]
        self.update_breadcrumb()
        self._update_state_label()
        keys = [s["id"] for _, s in self.sections]
        position = keys.index(key)
        self.previous_button.setEnabled(position > 0)
        self.next_button.setEnabled(position < len(keys) - 1)

    @staticmethod
    def focus_figure(figure_panel, owner):
        """Bring forward the main figure of a step (e.g. the spectrum of
        3.2 rather than its first figure)."""
        title = dts_steps.FOCUS_FIGURE.get(owner)
        page = figure_panel.pages.get((owner, title)) if title else None
        if page is not None and figure_panel.tabs.indexOf(page) >= 0:
            figure_panel.tabs.setCurrentWidget(page)

    def on_action(self, steps):
        """A button of a panel: steps to run, or a command ('@...')."""
        if steps == "@sound_all":               # Load and plot
            keys = ["ana.6.stc"]
            if "A_T" in self.session.data:
                keys.append("ana.6")
            else:
                self.write_log("\nSound-speed map not drawn: load data in "
                               "Data analysis › Load preprocessed data to "
                               "get it\n")
            self.run_steps(keys)
            return
        if steps == "@update_sound":            # Resampling and display
            done = [key for key in ("ana.6.stc", "ana.6")
                    if key in self.session.figures]
            if not done:
                QMessageBox.information(
                    self, "Update", "Nothing to update yet: press Load and "
                    "plot first.")
                return
            self.run_steps([key + ".replot" for key in done])
            return
        if steps == "@run_saved_analysis":
            self.run_saved_analysis()
            return
        if steps.startswith("@open_settings:"):
            self.load_settings(steps.split(":", 1)[1])
            return
        if steps.startswith("@save_settings_to:"):
            self.save_settings_to_panel(steps.split(":", 1)[1])
            return
        if steps.startswith("@save_settings:"):
            self.save_settings(steps.split(":", 1)[1])
            return
        self.run_steps(steps.split("|"))

    def reset_all(self):
        """File › Reset all: every loaded, preprocessed and analysis
        variable deleted, every figure closed, every panel back to its
        default values (channel, window, layer and profile lists empty)."""
        if self.busy_running():
            QMessageBox.warning(self, "Reset all",
                                "A step is running: interrupt it first.")
            return
        if QMessageBox.question(
                self, "Reset all",
                "Delete all the loaded, preprocessed and analysis variables, "
                "close every figure and put every panel back to its default "
                "values (channel, window, layer and profile lists empty), "
                "and the physical parameters back to their defaults?\n"
                "Files on disk are not touched.") != QMessageBox.Yes:
            return
        for name in ("detach_map_selection", "detach_window_selection"):
            try:
                getattr(self, name)()
            except Exception:                  # noqa: BLE001
                pass
        for dialog in (getattr(self, "_variables_dialog", None),):
            if dialog is not None:
                dialog.close()
        self._variables_dialog = None
        # panels and figure areas are rebuilt with their defaults on demand
        for panel, figure_panel in list(self.pages.values()):
            self.left_stack.removeWidget(panel)
            panel.deleteLater()
            if self.right_stack.indexOf(figure_panel) >= 0:
                self.right_stack.removeWidget(figure_panel)
            figure_panel.deleteLater()
        for figure_panel in self.shared_panels.values():
            if self.right_stack.indexOf(figure_panel) >= 0:
                self.right_stack.removeWidget(figure_panel)
            figure_panel.deleteLater()
        import matplotlib.pyplot as plt
        plt.close("all")
        self.pages, self.shared_panels = {}, {}
        self.session = dts_steps.Session()
        self.map_selectors, self.window_selectors = [], []
        self.surface_selection = False
        self.done, self.outdated = set(), set()
        self.channel_sources = {"pre": [], "files": [], "analysis": []}
        self.window_items = [dts_steps.WHOLE_RECORD]
        self.layer_items = [dts_steps.WHOLE_COLUMN]
        self.queue, self.analysis_runs, self.saved_runs = [], {}, []
        self.shared_profiles = None
        self.saved_ticks = []
        self._auto_output = None
        self.show_section(self.current or "pre.1")
        self._update_marks()
        dts_steps.core.set_physics(dts_steps.core.PHYSICS_DEFAULTS)
        if getattr(self, "_physics_dialog", None) is not None:
            self._physics_dialog.load(dts_steps.core.PHYSICS)
        self.log.clear()
        self.write_log("Reset all: every variable deleted, every panel and "
                       "the physical parameters back to their default "
                       "values.\n")
        self.statusBar().showMessage("Reset")

    def chain_variables_help(self):
        """Text added to the (?) of 'Include the LéXPLORE chain': every
        variable of the LeXPLORE data loaded."""
        data = self.session.data
        chain = (data.get("A_LEXPLORE") or data.get("A_CHAIN_ALL")
                 or data.get("DATA_LEXPLORE") or {})
        if not chain:
            return ("Variables of the LeXPLORE data: none loaded yet (load "
                    "the data with the chain first).")
        return ("Variables of the LeXPLORE data loaded (name [units] "
                "description (dimensions: size)):\n"
                + dts_steps.chain_variables_text(chain))

    def step_origin_label(self, step):
        """'Menu › step' of the step that first made a variable."""
        try:
            section = self.section_of(step)
            return f"{self.menu_of[section].replace('&', '')} › " \
                   f"{self.step_label(step)}"
        except (KeyError, AttributeError):
            return step

    def show_variables(self):
        """View › View all variables: the variables in memory."""
        import gui_variables
        dialog = gui_variables.VariablesDialog(self.session, self,
                                               self.step_origin_label)
        dialog.setModal(False)
        dialog.show()
        self._variables_dialog = dialog          # keep it alive

    # ---- (?) of the folders of Sound speed maps: the native resolution of
    #      the data sets found, computed when the (?) is clicked
    def _sound_folder(self, name):
        if "ana.6" not in self.pages:
            return ""
        return self.pages["ana.6"][0].fields[name].value()

    def stc_resolution_help(self):
        core = dts_steps.core
        folder = self._sound_folder("STC_FOLDER")
        lines = []
        for name, _ in core.stc_profile_files(folder):
            try:
                profile = core.read_stc_csv(os.path.join(folder, name))
            except Exception:                      # noqa: BLE001
                continue
            median, low, high = core.depth_resolution(profile["depth"])
            seconds = ((profile["end"] - profile["start"])
                       / np.timedelta64(1, "ms")) / 1000.0
            lines.append(f"  {name}: Δz ≈ {median:.2f} m (from {low:.2f} to "
                         f"{high:.2f} m), {profile['depth'].size} samples "
                         f"in {seconds:.0f} s, down to "
                         f"{np.nanmax(profile['depth']):.0f} m")
        return ("Native resolution of the STC profiles of the folder:\n"
                + "\n".join(lines)) if lines else \
            "No STC profile in the folder."

    def dts_resolution_help(self):
        core = dts_steps.core
        lines = []
        for path, configuration in core.find_dts_products(
                self._sound_folder("DTS_FOLDER")):
            info = core.dts_combined_times(path)
            if info is None:
                continue
            channel, times = info
            depth, _ = core.read_dts_profile(path, 0, channel)
            median, low, high = core.depth_resolution(depth)
            period = (np.median(np.diff(times)) / np.timedelta64(1, "s")
                      if times.size > 1 else float("nan"))
            lines.append(
                f"  {configuration} ({os.path.basename(path)}): Δz = "
                f"{median:.3f} m, {depth.size} depths, 0–{np.nanmax(depth):.1f}"
                f" m; one profile every {period:.0f} s, {times.size} "
                f"profiles, {str(times[0])[:16]} → {str(times[-1])[:16]} UTC")
        return ("Native resolution of the DTS records (Combined channel):\n"
                + "\n".join(lines)) if lines else \
            "No preprocessed DTS file with a Combined channel in the folder."

    def chain_resolution_help(self):
        core = dts_steps.core
        folder = self._sound_folder("LEXPLORE_FOLDER")
        try:
            times, depth, _, used = core._load_lexplore_folder(folder)
        except Exception as error:                 # noqa: BLE001
            return f"No chain file read ({error})."
        if not times.size:
            return "No chain profile in the folder."
        median, low, high = core.depth_resolution(depth)
        period = (np.median(np.diff(times)) / np.timedelta64(1, "s")
                  if times.size > 1 else float("nan"))
        return (f"Native resolution of the chain ({len(used)} file(s)): "
                f"{depth.size} sensors at "
                + ", ".join(f"{z:g}" for z in depth)
                + f" m, spacing {low:g} to {high:g} m; one profile every "
                f"{period:.0f} s, {str(times[0])[:16]} → "
                f"{str(times[-1])[:16]} UTC.")

    def show_save_variables(self):
        """Advanced › Save variables: tick the variables and save them."""
        import gui_variables
        dialog = getattr(self, "_save_variables_dialog", None)
        if dialog is None:
            dialog = gui_variables.SaveVariablesDialog(self.session, self,
                                                       self.write_log)
            self._save_variables_dialog = dialog
        dialog.session = self.session          # new after Reset all
        dialog.fill()
        dialog.setModal(False)
        dialog.show()

    def show_channel_info(self, name):
        """(?) next to a channel: how the channel is built."""
        QMessageBox.information(self, f"Channel {name}",
                                dts_steps.channel_description(self.session,
                                                              name))

    def fit_left_panel(self, panel):
        """Widen the left panel when the inputs of a step need more room
        (no text cut); it is never narrowed automatically."""
        needed = panel.needed_width()
        sizes = self.horizontal.sizes()
        if sum(sizes) and sizes[0] < needed:
            total = sum(sizes)
            self.horizontal.setSizes([needed, max(total - needed, 300)])

    def configuration_name(self, menu):
        """Configuration of the data of a menu: the raw data loaded
        (Preprocessing) or the preprocessed file loaded (Data analysis)."""
        data = self.session.data
        if menu.startswith("Preprocess"):
            folder = data.get("DATA_FOLDER")
            return os.path.basename(os.path.normpath(folder)) if folder \
                else ""
        files = data.get("A_FILES") or []
        if not files:
            return ""
        configuration, _, name = files[0].partition(" / ")
        return configuration if name in ("", dts_steps.PRODUCT_FILE) \
            else f"{configuration} / {name}"

    def update_breadcrumb(self):
        key = self.current
        if not key:
            return
        menu = self.menu_of[key]
        name = self.configuration_name(menu)
        head = f"<b>{menu}</b>" + (
            f" <span style='color:#0072B2'>[{name}]</span>" if name else "")
        self.breadcrumb.setText(head + "  ›  "
                                + "  ›  ".join(self.title_path(key)))

    def title_path(self, key):
        """Titles from the top menu entry down to the panel, e.g.
        ['Depth calibration', 'Calibration against the LéXPLORE chain']."""
        menu_sections = next(sections for name, sections in MENUS
                             if name.replace("&", "") == self.menu_of[key])
        by_number = {s["number"]: s for s in menu_sections}
        section = self.section_by_id[key]
        path = [section["title"]]
        parent = section["parent"]
        while parent:
            parent_section = by_number[parent]
            path.insert(0, parent_section.get("menu_title",
                                              parent_section["title"]))
            parent = parent_section["parent"]
        return path

    def step(self, direction):
        keys = [s["id"] for _, s in self.sections]
        position = keys.index(self.current) + direction
        if 0 <= position < len(keys):
            previous = self.current
            if direction > 0:
                self.carry_channels(previous, keys[position])
            self.show_section(keys[position])

    def carry_channels(self, source, target):
        """Next: the channels ticked in the step left (and its LéXPLORE
        choice) become the selection of the next step of the same menu;
        channels that the next step does not offer are left out, and other
        channels can still be ticked before running it."""
        if self.menu_of.get(source) != self.menu_of.get(target) or \
                source not in self.pages:
            return
        panel = self.pages[source][0]
        ticked = None
        for name in ("CHANNELS", "MAP_CHANNELS"):
            if name in panel.fields and \
                    panel.specs[name]["kind"] == "channels":
                ticked = panel.fields[name].value()
                break
        if not ticked:
            return
        target_panel = self.page(target)[0]
        for name, spec in target_panel.specs.items():
            if spec["kind"] == "channels" and name in ("CHANNELS",
                                                       "MAP_CHANNELS"):
                field = target_panel.fields[name]
                kept = [c for c in ticked if c in field.boxes]
                if kept:
                    field.set_value(kept)
            elif spec["kind"] == "channel":
                field = target_panel.fields[name]
                if field.value() not in ticked:
                    choice = next((c for c in ticked
                                   if c in field.buttons), None)
                    if choice:
                        field.set_value(choice)
        if "INCLUDE_CHAIN" in panel.fields and \
                "INCLUDE_CHAIN" in target_panel.fields and \
                target_panel.fields["INCLUDE_CHAIN"].isEnabled():
            target_panel.fields["INCLUDE_CHAIN"].set_value(
                panel.fields["INCLUDE_CHAIN"].value())

    def toggle_log(self):
        self.log.setVisible(not self.log.isVisible())

    def section_state(self, key):
        steps = self.steps_of(key)
        if self.section_by_id[key].get("done_when") == "any":
            # alternative methods: one valid result is enough
            if any(step in self.done for step in steps):
                return "done"
            if any(step in self.outdated for step in steps):
                return "outdated"
            return "not run"
        if any(step in self.outdated for step in steps):
            return "outdated"
        if all(step in self.done for step in steps):
            return "done"
        if any(step in self.done for step in steps):
            return "partly done"
        return "not run"

    def _update_state_label(self):
        state = self.section_state(self.current)
        text = {"done": "<span style='color:#009E73'>● done</span>",
                "partly done": "<span style='color:#009E73'>◐ partly done"
                               "</span>",
                "outdated": "<span style='color:#B35C00'>● outdated</span>",
                "not run": "<span style='color:#999'>○ not run</span>"}[state]
        self.state_label.setText(text)

    def _update_marks(self):
        for key, action in self.actions.items():
            state = self.section_state(key)
            mark = {"done": "✓ ", "outdated": "⚠ ",
                    "partly done": "◐ "}.get(state, "")
            action.setText(mark + action.data())
        for figure_panel in {id(p): p for _, p in self.pages.values()}.values():
            figure_panel.mark_owners_outdated(self.outdated)
        self._update_state_label()

    # ---- running ----------------------------------------------------------
    def chain_for(self, key):
        """Steps to run for key: the missing prerequisites, then key."""
        order = []

        def visit(step_key, top=False):
            for required in dts_steps.STEPS[step_key][1]:
                if required not in self.done:
                    visit(required)
            if step_key not in order and (top or step_key not in self.done):
                order.append(step_key)
        visit(key, top=True)
        return order

    def run_steps(self, keys):
        if self.busy_running():
            return
        order = []
        for key in keys:
            for step_key in self.chain_for(key):
                if step_key not in order:
                    order.append(step_key)
        extra = [k for k in order if k not in keys]
        if extra:
            names = "; ".join(self.step_label(k) for k in extra)
            self.write_log(f"\n(earlier steps run first: {names})\n")
        self.start([(k, None) for k in order])

    def run_jobs(self, steps):
        """Run the given steps (and their missing earlier steps); the two
        depth calibrations are chosen by dts_steps.SKIPS."""
        if self.busy_running():
            return
        order = []
        for key in steps:
            for step_key in self.chain_for(key):
                if step_key not in order:
                    order.append(step_key)
        self.start([(k, dts_steps.SKIPS.get(k)) for k in order])

    def run_panel(self, key):
        """Run All of one panel (every step of the panel, in order)."""
        self.run_jobs(self.steps_of(key))

    def run_all(self, menu_name):
        self.run_jobs([step for m, section in self.sections
                       if m == menu_name
                       for step in self.steps_of(section["id"])])

    def start(self, jobs):
        """Run the steps one after the other; the inputs of each step are
        read just before it starts (earlier steps may change the channel
        lists)."""
        self.queue = list(jobs)
        for panel, _ in self.pages.values():
            panel.set_running(True)
        self.busy.show()
        self.interrupt_button.setEnabled(True)
        self.next_job()

    def next_job(self):
        while self.queue:
            job = self.queue.pop(0)
            key, skip = job[0], job[1]
            saved = job[2] if len(job) > 2 else None
            reason = skip(self.session) if skip else ""
            if reason:
                self.write_log(f"\n[{self.step_label(key)} skipped: "
                               f"{reason}]\n")
                continue
            self.on_step_started(key)
            panel = self.page(self.section_of(key))[0]
            if saved is not None:             # replay: the panel shows the
                panel.set_values(saved)       # inputs used (lists now full)
            params = panel.values(key)
            if saved is not None:
                params = self.adapt_saved_params(key, dict(params, **saved))
            dts_steps.core.CANCEL.clear()
            self.worker = Worker(self.session, key, params)
            self.worker.step_interrupted.connect(self.on_step_interrupted)
            self.worker.log.connect(self.write_log)
            self.worker.step_done.connect(self.on_step_done)
            self.worker.step_failed.connect(self.on_step_failed)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.start()
            return
        self.on_finished()

    def on_worker_finished(self):
        ok = self.worker.ok
        self.worker = None
        if ok:
            self.next_job()
        else:
            self.queue = []
            self.on_finished()

    def on_step_started(self, key):
        section_id = self.section_of(key)
        self.statusBar().showMessage(
            f"Running {self.menu_of[section_id]} › {self.step_label(key)} …")
        self.write_log(f"\n===== {self.menu_of[section_id]} › "
                       f"{self.step_label(key)} =====\n")

    REPLAY_EXCLUDED = ("ana.0", "ana.0.1", "ana.5")

    def record_run(self, key):
        """Analysis steps run (computations, not display updates), in the
        order of their last run, with the inputs used."""
        if not key.startswith("ana.") or key in dts_steps.DISPLAY_ONLY \
                or key.endswith((".select", ".instants")):
            return
        if key == "ana.0":                    # new data: a new analysis
            self.analysis_runs = {}
        self.analysis_runs.pop(key, None)
        self.analysis_runs[key] = dict(self.session.params_used.get(key,
                                                                    {}))

    def on_step_done(self, key, figures):
        self.record_run(key)
        dialog = getattr(self, "_save_variables_dialog", None)
        if dialog is not None and dialog.isVisible():
            dialog.fill()                    # new variables listed at once
        owner = dts_steps.FIGURE_OWNER.get(key, key)
        if key not in dts_steps.DISPLAY_ONLY:
            self.done.add(key)
            self.outdated.discard(key)
            # every step that depends on this one is now outdated
            for other in list(self.done):
                if other != key and key in self.all_requirements(other):
                    self.done.discard(other)
                    self.outdated.add(other)
        _, figure_panel = self.page(self.section_of(key))
        figure_panel.set_figures(
            owner, figures, "Done: this step makes no figure (see the log).")
        self.focus_figure(figure_panel, owner)
        if owner.startswith("pre."):          # windows on every time map
            self.draw_fit_windows()
        elif owner.startswith("ana."):
            self.draw_analysis_windows()
        if key in ("pre.1.load", "ana.0"):    # configuration in the title
            self.update_breadcrumb()
        if owner == "pre.1.concat":           # new T maps: windows, selection
            self.draw_fit_windows()
            if self.map_selectors:
                self.attach_map_selection()
        if owner == "ana.0.1":                # new maps: windows, selection
            self.draw_analysis_windows()
            if self.window_selectors:
                self.attach_window_selection()
        if owner == "pre.3":
            self.draw_fit_windows()
        if owner == "pre.1.mirror":           # new profiles: surface line
            self.draw_surface_line()
        data = self.session.data
        if key == "pre.1.load":
            self.update_channels("pre", data["CHANNELS"])
            # default output folder of Save: the configuration folder
            fields = self.page("pre.3")[0].fields
            for name in ("OUTPUT_FOLDER", "SETTINGS_FOLDER"):
                output = fields[name]
                auto = getattr(self, "_auto_output", None)
                if not output.value() or output.value() == auto:
                    output.set_value(data["DATA_FOLDER"])
            self._auto_output = data["DATA_FOLDER"]
        elif key == "pre.1.concat":           # channels + 'mean'
            self.update_channels("pre", list(data["T_MATRIX_mean"]))
        if key in ("pre.2.1", "pre.2.2"):      # options of Save
            self.page("pre.3")[0].set_choice_items(
                "CALIBRATION",
                dts_steps.SHIFT_OPTIONS[data["CALIBRATION_DONE"]])
        elif key in ("ana.0.3", "ana.0.3.replot"):   # new channels
            self.update_channels("analysis", list(data["A_T"]))
        elif key == "ana.1":                  # layers for the later steps
            self.layer_items = dts_steps.layer_choices(data.get("A_LAYERS"))
            for other in ("ana.4.2.5", "ana.4.2.6", "ana.4.2.9"):   # they use Z1, Z2
                if other in self.done:
                    self.done.discard(other)
                    self.outdated.add(other)
            for panel, _ in self.pages.values():
                panel.set_layer_choices(self.layer_items)
        elif key == "ana.0":
            self.update_channels("files", data["A_CHANNELS_AVAILABLE"])
            # every analysis step lists all the DTS channels (its own ticks)
            self.update_channels("analysis", data["A_CHANNELS_AVAILABLE"])
            self.session.data.pop("A_CHANNEL_INFO", None)
            self.page("ana.0")[0].show_groups()
            self.page("ana.0")[0].fields["INCLUDE_CHAIN"].setEnabled(
                bool(data.get("A_CHAIN_ALL")))
            if self.current == "ana.0":
                self.fit_left_panel(self.page("ana.0")[0])
            if data.get("A_RESAMPLE_WARNING"):
                QMessageBox.information(self, "Mean resampled",
                                        data["A_RESAMPLE_WARNING"])
        elif key == "ana.0.instants":           # new profiles: redo users
            for other in list(self.done):
                if other in dts_steps.USE_PROFILE_TIMES or any(
                        step in self.all_requirements(other)
                        for step in dts_steps.USE_PROFILE_TIMES):
                    self.done.discard(other)
                    self.outdated.add(other)
        self._update_marks()

    def all_requirements(self, key):
        found = set()
        stack = list(dts_steps.STEPS[key][1])
        while stack:
            item = stack.pop()
            if item not in found:
                found.add(item)
                stack.extend(dts_steps.STEPS[item][1])
        return found

    def update_channels(self, source, channels):
        self.channel_sources[source] = list(channels)
        for panel, _ in self.pages.values():
            panel.set_channel_choices(source, channels)

    def on_step_failed(self, key, message):
        section_id = self.section_of(key)
        self.write_log(f"\nERROR in {self.step_label(key)}:\n{message}\n")
        self.show_section(section_id)
        QMessageBox.warning(self, "Step failed",
                            f"{self.menu_of[section_id]} › "
                            f"{self.step_label(key)}\n\n"
                            f"{message.strip().splitlines()[-1]}\n\n"
                            "(details in the log)")

    def interrupt(self):
        """Ask the running step to stop; the queued steps are dropped."""
        if not self.busy_running():
            return
        self.queue = []
        dts_steps.core.CANCEL.set()
        self.interrupt_button.setEnabled(False)
        self.statusBar().showMessage("Interrupting …")
        self.write_log("\nInterrupt requested: the step stops at its next "
                       "stop point.\n")

    def on_step_interrupted(self, key):
        """The step stopped before its end: its results, and those of the
        steps that depend on it, can no longer be trusted."""
        self.write_log(f"\n■ {self.step_label(key)} interrupted.\n")
        for step in [key] + [other for other in dts_steps.STEPS
                             if key in self.all_requirements(other)]:
            if step in self.done:
                self.done.discard(step)
                self.outdated.add(step)
        if key in self.outdated and key not in self.session.figures:
            self.outdated.discard(key)
        self._update_marks()

    def on_finished(self):
        if getattr(self, "_apply_saved_ticks", False):
            self._apply_saved_ticks = False
            ticks = getattr(self, "saved_ticks", [])
            if ticks:
                try:
                    panel = self.figure_panel_for("ana.0")
                    for key in list(panel.checked):
                        panel.checked[key] = tuple(key) in ticks
                    panel.rebuild_list()
                    panel.refresh_tabs()
                except Exception:              # noqa: BLE001
                    pass
        dts_steps.core.CANCEL.clear()
        self.interrupt_button.setEnabled(False)
        self.busy.hide()
        for panel, _ in self.pages.values():
            panel.set_running(False)
        self.statusBar().showMessage("Ready")

    def busy_running(self):
        return self.worker is not None or bool(getattr(self, "queue", []))

    # ---- time windows of the depth calibration on the T maps --------------
    def maps_canvas(self):
        """Canvas of the T(z, time) maps of Load raw data, or None."""
        panel = self.shared_panels.get("Preprocessing")
        return panel.canvas("pre.1.concat", "T(z, time) maps") if panel \
            else None

    @staticmethod
    def map_axes(figure):
        """The maps of a figure whose x axis is the time (UTC dates)."""
        from matplotlib.collections import QuadMesh

        def date_axis(ax):
            for other in ax.get_shared_x_axes().get_siblings(ax):
                axis = other.xaxis
                converter = (axis.get_converter()
                             if hasattr(axis, "get_converter")
                             else getattr(axis, "converter", None))
                if converter is not None and \
                        "Date" in type(converter).__name__:
                    return True
            return False

        return [ax for ax in figure.axes
                if any(isinstance(c, QuadMesh) for c in ax.collections)
                and date_axis(ax)]

    def time_map_canvases(self, menu):
        """Every figure canvas of a menu that holds a time map."""
        panel = self.shared_panels.get(menu)
        if panel is None:
            return []
        out = []
        for canvas in list(panel.canvas_of.values()):
            try:
                axes = self.map_axes(canvas.figure)
            except Exception:                  # noqa: BLE001
                continue
            if axes:
                out.append((canvas, axes))
        return out

    @staticmethod
    def shade_windows(canvas, axes, windows, colour, selected=None):
        """Shade time windows [(label, t0, t1)] on map axes (labels at the
        top; the selected one darker); the previous shading is removed."""
        for artist in getattr(canvas, "window_artists", []):
            try:
                artist.remove()
            except ValueError:
                pass
        artists = []
        for label, t0, t1 in windows:
            chosen = selected is not None and label == selected
            for index, ax in enumerate(axes):
                limits = ax.get_xlim()    # a window outside the record must
                artists.append(ax.axvspan(
                    t0, t1, facecolor=colour, alpha=0.45 if chosen else 0.2,
                    edgecolor=colour, lw=2.5 if chosen else 1.2, zorder=3))
                if label and index == 0:
                    import matplotlib.dates as mdates
                    middle = mdates.date2num(t0 + (t1 - t0) / 2)
                    if limits[0] <= middle <= limits[1]:
                        artists.append(ax.text(
                            middle, 1.01, label, transform=ax.get_xaxis_transform(),
                            ha="center", va="bottom", fontsize=8,
                            color=colour,
                            fontweight="bold" if chosen else "normal"))
                ax.set_xlim(limits)       # not stretch the time axis
        canvas.window_artists = artists
        canvas.draw_idle()

    @staticmethod
    def parse_rows(rows):
        windows = []
        for row in rows:
            label, start, end = (("",) + tuple(row))[-3:]
            try:
                t0, t1 = dts_steps.utc(start), dts_steps.utc(end)
            except ValueError:
                continue
            if t0 is not None and t1 is not None and t1 > t0:
                windows.append((label, t0, t1))
        return windows

    def draw_fit_windows(self):
        """Shade the fit windows of the depth calibration on the whole-record
        maps of the preprocessing (Load raw data and Save)."""
        if "pre.2" not in self.pages:
            return
        windows = self.parse_rows(
            self.pages["pre.2"][0].fields["TIME_WINDOWS"].value())
        for canvas, axes in self.time_map_canvases("Preprocessing"):
            self.shade_windows(canvas, axes, windows, "#E69F00")

    def draw_analysis_windows(self, *_):
        """Shade the time windows W1, W2, ... of the analysis on every map
        of the analysis with time along x (the one chosen in the current
        step darker)."""
        if "ana.0" not in self.pages:
            return
        panel, figure_panel = self.pages["ana.0"]
        windows = self.parse_rows(panel.fields["WINDOWS"].value())
        selected = None
        if self.current in self.pages:
            field = self.pages[self.current][0].fields.get("TIME_WINDOW")
            if field is not None:
                parsed = field.currentText().split(":")[0]
                selected = parsed if parsed != dts_steps.WHOLE_RECORD \
                    else None
        for canvas, axes in (self.time_map_canvases("Data analysis")
                             + self.time_map_canvases("Advanced")):
            self.shade_windows(canvas, axes, windows, "#0072B2", selected)

    def on_toggle(self, key, name, on):
        if name == "MAP_SELECT":
            if on:
                self.attach_map_selection()
            else:
                self.detach_map_selection()
        elif name == "PROFILE_SELECT":
            if on:
                panel = self.page("ana.0")[1]
                if panel.show_figure("ana.0.1", "T(z, t) maps"):
                    self.statusBar().showMessage(
                        "Click on the T(z, t) map to add a profile")
                else:
                    self.write_log("No T(z, t) map yet: press Load data "
                                   "first.\n")
            else:
                self.statusBar().showMessage("Ready")
        elif name == "KZ_SELECT":
            if on:
                panel = self.page("ana.4.1.1")[1]
                if panel.show_figure("ana.4.1.1", "Time × k_z"):
                    self.statusBar().showMessage(
                        "Click on the k_z map to add a profile")
                else:
                    self.write_log("No k_z map yet: run the step first.\n")
            else:
                self.statusBar().showMessage("Ready")
        elif name == "LAYER_SELECT":
            if on:
                panel = self.page("ana.1")[1]
                if panel.show_figure("ana.1", "Layers"):
                    self.statusBar().showMessage(
                        "Click on the Layers map to add a profile")
                else:
                    self.write_log("No Layers map yet: run the step "
                                   "first.\n")
            else:
                self.statusBar().showMessage("Ready")
        elif name == "STAIRCASE_SELECT":
            if on:
                panel = self.page("ana.4.2.5")[1]
                if panel.show_figure("ana.4.2.5", "Maps"):
                    self.statusBar().showMessage(
                        "Click on the T(z, t) map to add a profile")
                else:
                    self.write_log("No T(z, t) map yet: run the step "
                                   "first.\n")
            else:
                self.statusBar().showMessage("Ready")
        elif name == "K_SELECT":
            if on:
                self.attach_k_selection()
            else:
                self.detach_k_selection()
        elif name == "GRADIENT_SELECT":
            if on:
                panel = self.page("ana.4.2.6")[1]
                if panel.show_figure("ana.4.2.6", "Maps"):
                    self.statusBar().showMessage(
                        "Click on the gradient map to add a profile")
                else:
                    self.write_log("No gradient map yet: run the step "
                                   "first.\n")
            else:
                self.statusBar().showMessage("Ready")
        elif name == "WINDOW_SELECT":
            if on:
                self.attach_window_selection()
            else:
                self.detach_window_selection()
        elif name == "SURFACE_SELECT":
            self.surface_selection = on
            if on:
                panel = self.figure_panel_for("pre.2")
                if panel.show_figure("pre.1.mirror", "Uncalibrated Profiles"):
                    self.draw_surface_line()
                    self.statusBar().showMessage(
                        "Click on the water surface in the Uncalibrated "
                        "Profiles")
                else:
                    self.write_log("No Uncalibrated Profiles yet: run Mirror "
                                   "distance in Load raw data first.\n")
            else:
                self.statusBar().showMessage("Ready")

    def update_profile_sublist(self):
        """One tickable item per row of the profile table under the figure
        'Individual profiles' (a new profile is ticked)."""
        panel, figure_panel = self.pages["ana.0"]
        names = [dts_steps.profile_item_name(label, text)
                 for label, text in panel.fields["PROFILE_TIMES"].value()
                 if str(text).strip()]
        figure_panel.set_sublist("ana.0.1", "Individual profiles", names)
        self.session.profile_selection = set(figure_panel.sublist_ticked(
            "ana.0.1", "Individual profiles"))

    def on_profile_sublist(self, owner, title, ticked):
        """Update plots with other profiles ticked: redraw the figures."""
        self.session.profile_selection = set(ticked)
        if "ana.0.1" in self.done and not self.busy_running():
            self.run_steps(["ana.0.replot"])

    # ---- analysis time windows ---------------------------------------------
    def on_windows_changed(self):
        """Table of the time windows of Load preprocessed data changed: blank labels get
        W1, W2, ... and every list 'Time window' is updated."""
        table = self.pages["ana.0"][0].fields["WINDOWS"]
        rows = [list(row) + [""] * (3 - len(row)) for row in table.value()]
        used = {row[0] for row in rows if row[0]}
        number, changed = 1, False
        for row in rows:
            if not row[0]:
                while f"W{number}" in used:
                    number += 1
                row[0] = f"W{number}"
                used.add(row[0])
                changed = True
        if changed:
            table.blockSignals(True)
            table.set_value([tuple(row) for row in rows])
            table.blockSignals(False)
        self.window_items = [dts_steps.WHOLE_RECORD] + [
            dts_steps.window_label(*row) for row in rows
            if row[1].strip() and row[2].strip()]
        for panel, _ in self.pages.values():
            panel.set_window_choices(self.window_items)
        self.draw_analysis_windows()

    def attach_window_selection(self):
        from matplotlib.widgets import SpanSelector
        self.detach_window_selection(quiet=True)
        panel = self.page("ana.0")[1]
        if not panel.show_figure("ana.0.1", "T(z, t) maps"):
            self.write_log("No T(z, t) map yet: press Load data first.\n")
            return
        canvas = panel.canvas("ana.0.1", "T(z, t) maps")
        for ax in self.map_axes(canvas.figure):
            self.window_selectors.append(SpanSelector(
                ax, self.on_window_span, "horizontal", useblit=True,
                props=dict(facecolor="#0072B2", alpha=0.3), minspan=1e-4))
        self.statusBar().showMessage(
            "Drag horizontally on the T(z, t) map to add a time window")

    def attach_k_selection(self):
        """Horizontal drag on the spectra of the individual profiles sets
        k min and k max of the wavenumber domain."""
        from matplotlib.widgets import SpanSelector
        self.detach_k_selection(quiet=True)
        panel = self.page("ana.4.1.1")[1]
        title = "FFT of the individual profiles"
        if not panel.show_figure("ana.4.1.1", title):
            self.write_log("No spectra of individual profiles yet: run the "
                           "step with individual profiles first.\n")
            return
        canvas = panel.canvas("ana.4.1.1", title)
        self.k_selectors = [
            SpanSelector(ax, self.on_k_span, "horizontal", useblit=True,
                         props=dict(facecolor="#0072B2", alpha=0.3))
            for ax in canvas.figure.axes if ax.get_visible() and ax.lines]
        self.statusBar().showMessage(
            "Drag horizontally on a spectrum to choose the wavenumber range")

    def detach_k_selection(self, quiet=False):
        for selector in getattr(self, "k_selectors", []):
            selector.set_active(False)
            selector.disconnect_events()
        self.k_selectors = []
        if not quiet:
            self.statusBar().showMessage("Ready")

    def on_k_span(self, xmin, xmax):
        if xmin <= 0 or xmax <= 0 or xmax == xmin:
            return
        panel = self.page("ana.4.1.1")[0]
        lo, hi = sorted((xmin, xmax))
        if panel.fields["VERTICAL_AXIS"].value() != "wavenumber":
            lo, hi = 1.0 / hi, 1.0 / lo           # wavelengths -> k
        panel.fields["K_MIN"].set_value(round(lo, 4))
        panel.fields["K_MAX"].set_value(round(hi, 4))
        self.write_log(f"wavenumber range: {lo:.4g} - {hi:.4g} 1/m (press "
                       f"Fit scaling)\n")

    def detach_window_selection(self, quiet=False):
        for selector in self.window_selectors:
            selector.set_active(False)
            selector.disconnect_events()
        self.window_selectors = []
        if not quiet:
            self.statusBar().showMessage("Ready")

    def on_window_span(self, xmin, xmax):
        import matplotlib.dates as mdates
        start, end = sorted((xmin, xmax))
        texts = [mdates.num2date(value).strftime("%Y-%m-%d %H:%M:%S")
                 for value in (start, end)]
        table = self.pages["ana.0"][0].fields["WINDOWS"]
        table.append_row(["", texts[0], texts[1]])   # label set W<n>
        self.write_log(f"time window added from the map: {texts[0]} -> "
                       f"{texts[1]} UTC\n")

    # owner of the map -> (panel, toggle, table of profiles)
    PROFILE_PICKERS = {"ana.0.1": ("ana.0", "PROFILE_SELECT",
                                   "PROFILE_TIMES"),
                       "ana.4.1.1": ("ana.4.1.1", "KZ_SELECT",
                                     "KZ_PROFILES"),
                       "ana.4.2.6": ("ana.4.2.6", "GRADIENT_SELECT",
                                     "GRADIENT_PROFILES"),
                       "ana.4.2.5": ("ana.4.2.5", "STAIRCASE_SELECT",
                                     "STAIRCASE_PROFILES"),
                       "ana.1": ("ana.1", "LAYER_SELECT",
                                 "LAYER_PROFILES")}
    # tables of individual profiles: one shared list, every change in one
    # table (row added, edited, removed, click on a map) is copied to the
    # others
    PROFILE_TABLES = {"ana.0": "PROFILE_TIMES",
                      "ana.4.1.1": "KZ_PROFILES",
                      "ana.4.2.6": "GRADIENT_PROFILES",
                      "ana.4.2.5": "STAIRCASE_PROFILES",
                      "ana.1": "LAYER_PROFILES"}
    shared_profiles = None
    _syncing_profiles = False

    def sync_profiles(self, source):
        """Copy the profile table of panel ``source`` to the profile tables
        of the other analysis panels."""
        if self._syncing_profiles or source not in self.pages:
            return
        rows = [tuple(r) for r in self.pages[source][0].fields[
            self.PROFILE_TABLES[source]].value()]
        self.shared_profiles = rows
        self._syncing_profiles = True
        try:
            for key, name in self.PROFILE_TABLES.items():
                if key == source or key not in self.pages:
                    continue
                table = self.pages[key][0].fields[name]
                if [tuple(r) for r in table.value()] != rows:
                    table.set_value(list(rows))
        finally:
            self._syncing_profiles = False
        for panel, _ in self.pages.values():    # lists of start times
            panel.set_profile_choices(rows)
        if source != "ana.0" and "ana.0" in self.pages:
            self.update_profile_sublist()       # figure list of Load data

    def on_profile_click(self, owner, x, y):
        """A click on the T(z, t) map of Load preprocessed data or on the k_z map adds the
        nearest profile to the table of individual profiles of that panel."""
        if owner not in self.PROFILE_PICKERS:
            return
        page, toggle_name, table_name = self.PROFILE_PICKERS[owner]
        if page not in self.pages:
            return
        panel = self.pages[page][0]
        toggle = panel.toggles.get(toggle_name)
        if toggle is None or not toggle.isChecked():
            return
        times = self.session.data.get("A_TIME")
        if not times:
            return
        import matplotlib.dates as mdates
        import numpy as np
        clicked = np.datetime64(mdates.num2date(x).replace(tzinfo=None),
                                "ms")
        time = next(iter(times.values()))
        if clicked < time[0] or clicked > time[-1]:
            return                       # outside the record (colour bar...)
        nearest = time[int(np.argmin(np.abs(time - clicked)))]
        text = str(nearest.astype("datetime64[s]")).replace("T", " ")
        table = panel.fields[table_name]
        used = {str(row[0]).strip() for row in table.value()}
        number = 1
        while f"P{number}" in used:          # first label not taken
            number += 1
        label = f"P{number}"
        table.append_row((label, text))
        self.statusBar().showMessage(
            f"profile {label} added: {text} UTC (press "
            + ("Update" if page == "ana.0" else "Run or Update plot")
            + " to use it)")

    # ---- display of the preprocessing maps (figure list) --------------------
    REPLOT_STEPS = {"pre.1.concat": "pre.1.replot", "pre.3": "pre.3.replot"}

    def on_display_update(self, values):
        """Update plots: redraw the existing maps when the display options
        changed (the data are not computed again)."""
        if values == getattr(self.session, "display", None):
            return
        self.session.display = values
        panel = self.shared_panels["Preprocessing"]
        steps = [replot for owner, replot in self.REPLOT_STEPS.items()
                 if owner in panel.results]
        if steps and not self.busy_running():
            self.start([(step, None) for step in steps])

    # ---- water surface on the Uncalibrated Profiles -------------------------
    def profiles_canvas(self):
        panel = self.shared_panels.get("Preprocessing")
        return panel.canvas("pre.1.mirror", "Uncalibrated Profiles") \
            if panel else None

    def draw_surface_line(self):
        """Orange line at Z_SURFACE on the Uncalibrated Profiles."""
        canvas = self.profiles_canvas()
        if canvas is None or "pre.2" not in self.pages:
            return
        value = self.pages["pre.2"][0].fields["Z_SURFACE"].value()
        old_line = getattr(canvas, "surface_line", None)
        if old_line is not None:
            try:
                old_line.remove()
            except ValueError:
                pass
        ax = canvas.figure.axes[0]
        canvas.surface_line = ax.axhline(value, color="#D55E00", lw=1.5,
                                         ls="--", zorder=5)
        canvas.surface_line.set_label(f"water surface {value:.2f} m")
        ax.legend(fontsize=8)
        canvas.draw_idle()

    def on_shared_click(self, owner, x, y):
        if owner == "pre.1.mirror" and self.surface_selection \
                and "pre.2" in self.pages:
            self.pages["pre.2"][0].fields["Z_SURFACE"].set_value(round(y, 2))
            self.write_log(f"water surface set to {y:.2f} m (connector "
                           f"coordinate) by a click on the Uncalibrated "
                           f"Profiles\n")
            self.draw_surface_line()

    def attach_map_selection(self):
        from matplotlib.widgets import SpanSelector
        self.detach_map_selection(quiet=True)
        canvas = self.maps_canvas()
        if canvas is None:
            self.write_log("No T(z, time) maps yet: press Concatenate in "
                           "Load raw data first; the selection starts as soon "
                           "as the maps exist.\n")
            self.map_selectors = [None]       # waiting for the maps
            return
        self.shared_panels["Preprocessing"].show_figure("pre.1.concat",
                                                        "T(z, time) maps")
        for ax in self.map_axes(canvas.figure):
            self.map_selectors.append(SpanSelector(
                ax, self.on_map_span, "horizontal", useblit=True,
                props=dict(facecolor="#D55E00", alpha=0.3),
                minspan=1e-4))
        self.statusBar().showMessage(
            "Drag horizontally on a T(z, time) map to add a time window")

    def detach_map_selection(self, quiet=False):
        for selector in self.map_selectors:
            if selector is not None:
                selector.set_active(False)
                selector.disconnect_events()
        self.map_selectors = []
        if not quiet:
            self.statusBar().showMessage("Ready")

    def on_map_span(self, xmin, xmax):
        """A span dragged on a map -> one row (UTC) of the fit windows."""
        import matplotlib.dates as mdates
        start, end = sorted((xmin, xmax))
        texts = [mdates.num2date(value).strftime("%Y-%m-%d %H:%M:%S")
                 for value in (start, end)]
        table = self.pages["pre.2"][0].fields["TIME_WINDOWS"]
        table.append_row(texts)
        self.write_log(f"time window added from the map: {texts[0]} -> "
                       f"{texts[1]} UTC\n")

    def on_figure_click(self, key, field, value, step):
        panel, _ = self.page(key)
        panel.fields[field].set_value(round(value, 3))
        self.write_log(f"{field} set to {value:.3f} by a click on the "
                       f"figure\n")
        if not self.busy_running():
            self.run_steps([step])

    def write_log(self, text):
        cursor = self.log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    # ---- settings files ---------------------------------------------------
    def settings_folder(self, word):
        """Default folder of the preprocessing settings: the configuration
        folder (loaded, else the one chosen in Load raw data)."""
        if word == "analysis":
            return self.analysis_folder()
        if word not in ("preprocessing", "all"):
            return None
        folder = self.session.data.get("DATA_FOLDER")
        if not folder and "pre.1" in self.pages:
            fields = self.pages["pre.1"][0].fields
            try:
                folder = os.path.join(
                    gui_widgets.temperature_root(fields["ROOT"].value()),
                    fields["CONFIGURATION"].currentText())
            except Exception:
                folder = None
        return folder if folder and os.path.isdir(folder) else None

    def analysis_folder(self):
        """Default folder of the analysis settings: the configuration of
        the first preprocessed file ticked in Load preprocessed data (else
        the first configuration ticked, else the folder of the data
        loaded)."""
        candidates = []
        if "ana.0" in self.section_by_id:
            fields = self.page("ana.0")[0].fields
            root = fields["PRODUCT_ROOT"].value() or ""
            for entry in fields["PREPROCESSED_FILES"].value():
                candidates.append(os.path.join(root, entry.split(" / ")[0]))
            for name in fields["CONFIGURATIONS"].value():
                candidates.append(os.path.join(root, name))
        candidates += list(self.session.data.get("A_FOLDERS") or [])
        return next((f for f in candidates if f and os.path.isdir(f)), None)

    def _settings_word(self, menu):
        if not isinstance(menu, str):
            return "all"
        if menu is None:
            return "all"
        return ("preprocessing" if "reprocess" in menu.replace("&", "")
                else "analysis")

    def save_settings(self, menu=None):
        """Save the inputs of every panel (menu None) or of the panels of
        one menu (Preprocessing or Data analysis) to a JSON file."""
        menu = menu.replace("&", "") if isinstance(menu, str) else None
        word = self._settings_word(menu)
        default = ("DTS_gui_settings.json" if menu is None
                   else f"DTS_{word}_settings.json")
        folder = self.settings_folder(word)
        if folder:
            default = os.path.join(folder, default)
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save {word} settings", default, "JSON (*.json)")
        if not path:
            return
        self.write_settings(path, menu, word)

    def save_settings_to_panel(self, menu):
        """Save button of the panel 'Preprocessing settings' (Save): the
        file named in the panel, without a file dialog."""
        menu = menu.replace("&", "")
        word = self._settings_word(menu)
        fields = self.page("pre.3")[0].fields
        folder = (fields["SETTINGS_FOLDER"].value()
                  or self.settings_folder(word))
        name = os.path.basename(fields["SETTINGS_NAME"].value().strip()
                                or f"DTS_{word}_settings.json")
        if not name.lower().endswith(".json"):
            name += ".json"
        if not folder:
            QMessageBox.warning(self, "Save settings",
                                "Set the output folder (or load the raw "
                                "data: the configuration folder is used).")
            return
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        if os.path.exists(path) and QMessageBox.question(
                self, "Save settings", f"{name} exists in this folder. "
                "Replace it?") != QMessageBox.Yes:
            return
        self.write_settings(path, menu, word)

    def write_settings(self, path, menu, word):
        """Write the inputs of the panels of one menu (None = all)."""
        keys = [section["id"] for menu_name, section in self.sections
                if menu is None or menu_name in self.settings_menus(menu)]
        settings = {"version": VERSION, "contents": word,
                    "steps": {key: self.page(key)[0].values()
                              for key in keys}}
        if word in ("all", "analysis"):
            settings["physical_parameters"] = dict(dts_steps.core.PHYSICS)
        if word in ("all", "preprocessing"):
            settings["display"] = getattr(self.session, "display", {})
        if word in ("all", "analysis"):
            settings["analysis_runs"] = [
                {"step": key, "label": self.step_label(key),
                 "inputs": inputs}
                for key, inputs in self.analysis_runs.items()]
            settings["figures_ticked"] = self.figure_ticks("ana.0")
            variables = self.save_analysis_variables(path)
            if variables:
                settings["variables_file"] = os.path.basename(variables)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, default=str)
        self.write_log(f"settings saved: {path}\n")
        if settings.get("analysis_runs"):
            self.write_log("  steps recorded: " + "; ".join(
                run["label"] for run in settings["analysis_runs"]) + "\n")

    DATA_SELECTION = ("PRODUCT_ROOT", "CONFIGURATIONS", "PREPROCESSED_FILES",
                      "LEXPLORE_ROOT")

    def run_saved_button(self):
        if "ana.0" not in self.pages:
            return None
        return next((b for b in self.pages["ana.0"][0].action_buttons
                     if b.text().startswith("Run the saved")), None)

    def run_saved_analysis(self):
        """Load the data chosen, then run every analysis step recorded in
        the settings opened, in their order, with their saved inputs."""
        if self.busy_running():
            return
        if not self.saved_runs:
            QMessageBox.information(
                self, "Run the saved analysis",
                "Open analysis settings saved after an analysis first: "
                "they hold the list of the steps run.")
            return
        if not self.page("ana.0")[0].fields["PREPROCESSED_FILES"].value():
            QMessageBox.warning(self, "Run the saved analysis",
                                "Choose a preprocessed file first.")
            return
        jobs = [("ana.0", None), ("ana.0.1", None)]
        jobs += [(key, None, inputs) for key, inputs in self.saved_runs
                 if key not in self.REPLAY_EXCLUDED]
        self.write_log("\n===== Run the saved analysis: " + "; ".join(
            self.step_label(job[0]) for job in jobs) + " =====\n")
        self._apply_saved_ticks = True
        self.start(jobs)

    def adapt_saved_params(self, key, params):
        """Saved inputs on another data set: channels that do not exist in
        the data loaded are dropped (all the channels when none remains);
        a single channel that does not exist becomes Combined (else the
        first channel)."""
        available = list(self.channel_sources.get("analysis", []))
        if not available:
            return params
        specs = self.page(self.section_of(key))[0].specs
        for name, value in list(params.items()):
            kind = specs.get(name, {}).get("kind")
            if kind == "channels" and isinstance(value, (list, tuple)):
                kept = [c for c in value if c in available]
                if len(kept) < len(value):
                    self.write_log(f"{self.step_label(key)}: channel(s) "
                                   f"{', '.join(c for c in value if c not in available)}"
                                   " not in these data\n")
                params[name] = kept or list(available)
            elif kind == "channel" and value not in available:
                params[name] = ("Combined" if "Combined" in available
                                else available[0])
        return params

    def figure_ticks(self, key):
        """Figures ticked in the figure list of a menu."""
        try:
            panel = self.figure_panel_for(key)
        except KeyError:
            return []
        return [[owner, title] for (owner, title), on in
                getattr(panel, "checked", {}).items() if on]

    def save_analysis_variables(self, path):
        """Every analysis variable (A_...) with the step that made it, in a
        pickle file next to the settings file."""
        import pickle
        data = {k: v for k, v in self.session.data.items()
                if k.startswith("A_")}
        if not data:
            return None
        target = os.path.splitext(path)[0] + "_variables.pkl"
        try:
            with open(target, "wb") as handle:
                pickle.dump({"version": VERSION, "variables": data,
                             "origin": {k: self.session.origin.get(k)
                                        for k in data}}, handle,
                            protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as error:              # noqa: BLE001
            self.write_log(f"variables not saved ({error})\n")
            return None
        size = os.path.getsize(target) / 1e6
        self.write_log(f"analysis variables saved: {target} "
                       f"({len(data)} variables, {size:.1f} MB)\n")
        return target

    def load_settings(self, menu=None):
        """Open a settings file; with a menu, only the panels of that menu
        are set (a file of another kind is read for its matching part)."""
        menu = menu.replace("&", "") if isinstance(menu, str) else None
        word = self._settings_word(menu)
        path, _ = QFileDialog.getOpenFileName(
            self, f"Open {word} settings", self.settings_folder(word) or "",
            "JSON (*.json)")
        if not path:
            return
        with open(path, encoding="utf-8") as handle:
            settings = json.load(handle)
        allowed = {section["id"] for menu_name, section in self.sections
                   if menu is None or menu_name in self.settings_menus(menu)}
        if word in ("all", "analysis") and \
                settings.get("physical_parameters"):
            changed = dts_steps.core.set_physics(
                settings["physical_parameters"])
            if getattr(self, "_physics_dialog", None) is not None:
                self._physics_dialog.load(dts_steps.core.PHYSICS)
            self.write_log("physical parameters of the settings: "
                           + (", ".join(f"{n} = {dts_steps.core.PHYSICS[n]}"
                                        for n in changed) if changed
                              else "same as now") + "\n")
        applied = 0
        kept = []
        for key, values in settings.get("steps", {}).items():
            if key in self.section_by_id and key in allowed:
                values = dict(values)
                if key == "ana.0":            # keep the data chosen here
                    fields = self.page("ana.0")[0].fields
                    if fields["PREPROCESSED_FILES"].value():
                        for name in self.DATA_SELECTION:
                            if name in values:
                                values.pop(name)
                                kept.append(name)
                self.page(key)[0].set_values(values)
                applied += 1
        if kept:
            self.write_log("the data selection of Load preprocessed data is "
                           "kept (root folder, configuration, file, chain "
                           "folder)\n")
        if word in ("all", "analysis"):
            self.saved_runs = [
                (run["step"], run.get("inputs") or {})
                for run in settings.get("analysis_runs", [])
                if run.get("step") in dts_steps.STEPS]
            self.saved_ticks = [tuple(t) for t in
                                settings.get("figures_ticked", [])]
            button = self.run_saved_button()
            if button is not None:
                button.setEnabled(bool(self.saved_runs))
            if self.saved_runs:
                self.write_log(
                    f"{len(self.saved_runs)} analysis step(s) recorded in "
                    "the settings: " + "; ".join(
                        self.step_label(k) for k, _ in self.saved_runs)
                    + "\n(Load preprocessed data › Run the saved analysis "
                    "runs them on the data chosen)\n")
        if not applied:
            QMessageBox.warning(self, "Open settings",
                                f"{os.path.basename(path)} holds no "
                                f"{word} settings.")
            return
        if settings.get("display") and word in ("all", "preprocessing"):
            self.session.display = settings["display"]
            self.figure_panel_for("pre.1").set_display_values(
                settings["display"])
        self.write_log(f"settings loaded: {path}\n")

    @staticmethod
    def settings_menus(menu):
        """Menus whose panels go in the settings of ``menu``: the Advanced
        panels are saved with the analysis settings."""
        menu = (menu or "").replace("&", "")
        return (menu, "Advanced") if menu == "Data analysis" else (menu,)

    def show_physics(self):
        """Advanced › Physical parameters: see and change the physical
        parameters of the steps (non-modal window)."""
        dialog = getattr(self, "_physics_dialog", None)
        if dialog is None:
            dialog = gui_physics.PhysicsDialog(self)
            dialog.applied.connect(self.on_physics_applied)
            self._physics_dialog = dialog
        dialog.load(dts_steps.core.PHYSICS)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def on_physics_applied(self, changed):
        if not changed:
            return
        if "ana.6" in self.pages and any(n.startswith("LEXPLORE")
                                         for n in changed):
            fields = self.pages["ana.6"][0].fields       # distances
            fields["STC_PROFILES"].refresh(fields["STC_FOLDER"].value())
        self.write_log("\nphysical parameters changed: " + ", ".join(
            f"{name} = {dts_steps.core.PHYSICS[name]}" for name in changed)
            + "\n(the steps already run keep their results: run them again "
              "to use the new values)\n")

    def closeEvent(self, event):
        if self.busy_running():
            self.queue = []
            answer = QMessageBox.question(
                self, "A step is running",
                "A computation is still running. Quit anyway?")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            if self.worker is not None:
                self.worker.terminate()
                self.worker.wait(2000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DTS GUI")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
