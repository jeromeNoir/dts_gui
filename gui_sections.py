"""Description of the steps of the DTS GUI (menus and left panels).

Each step of the two menus (Preprocessing, Data analysis) is one dict:

    id           unique key, e.g. "pre.2.2" (also the key of dts_steps.STEPS)
    number       step number shown in the menu, e.g. "2.2"
    title        menu text
    menu_title   (optional) title of the sub-menu when the step has
                 children; the step itself is the first item of the sub-menu
    parent       number of the parent step (None for a top-level item)
    is_menu      True for a sub-menu heading that is not a step itself
    description  short text shown above the figures
    params       list of input groups: (group title, [field, ...])
    figures      (optional) catalogue of the figures of the panel:
                 (step id, tab title, shown by default); listed with tick
                 boxes on the right of the figures
    focus_owner  (optional) step whose tabs come forward when the panel is
                 shown (shared result area)
    done_when    (optional) "any": the panel counts as done when one of its
                 steps has run (alternative methods), instead of all
    actions      (optional) the steps of a panel that holds several steps,
                 in order; the bottom button "Run All" runs them all.  A
                 panel without actions is one step whose id is the panel id

A field is a dict with the keys
    name     name of the value passed to the step (dts_steps)
    label    text shown in the left panel
    kind     dir, dirs, text, float, int, bool, choice, configuration,
             channels (check boxes), channel (radio buttons), datetime,
             timetable (named instants), windows (start/end pairs),
             info (read-only text), heading (sub-title inside a box),
             note (short explanation), button (runs the step ``step``;
             drawn at the right of the box), toggle (on/off button that
             switches a mode of the window, e.g. selection on a map)
    default  initial value
    + optional keys: choices, unit, minimum, maximum, decimals, optional
      (float/datetime/dir may be left empty = None), zone, tip, placeholder

Channel fields whose choices are the string "pre" or "analysis" receive the
channels found in the data once step 0 (preprocessing) or 0.1 (analysis)
has run.  All times are UTC, except the reference local time of the clock
correction.
"""

import default_paths

# default folders: read from default_paths.ini (personal, not in git; see
# default_paths_template.ini and the README); '' when not set
XT_TEMPERATURE_ROOT = default_paths.get("xt_temperature")
LEXPLORE_ROOT = default_paths.get("lexplore")

PRE_CHANNELS_DEFAULT = []               # filled when the data are loaded
ANALYSIS_CHANNELS_DEFAULT = []          # filled when the data are loaded

PROFILE_TIMES = [("04.11 21:00", "2026-11-04 21:00:00"),
                 ("07.11 03:00", "2026-11-07 03:00:00"),
                 ("10.11 20:40", "2026-11-10 20:40:00")]


COLOUR_MAPS = ["default", "seismic", "coolwarm", "RdBu_r", "viridis",
               "plasma", "inferno", "magma", "cividis", "turbo", "gray"]


def display_group(step, extra=()):
    """Common 'Display' group of the steps that draw maps (same layout in
    every step): shading, colour map and Update plot (the figures of the
    step drawn again with these options; the other steps are not
    affected)."""
    return ("Display", [
        dict(name="IS_SHADING", label="Smooth shading", kind="bool",
             default=False,
             tip="Off: plain cells ('nearest'); on: the kind below"),
        dict(name="SHADING", label="Shading kind", kind="choice",
             choices=["gouraud", "nearest", "auto"], default="gouraud"),
        dict(name="CMAP", label="Colour map", kind="choice",
             choices=COLOUR_MAPS, default="default",
             tip="default: the colour map of each figure (seismic for the "
                 "temperature, viridis or turbo for N and the spectra); "
                 "seismic, coolwarm, RdBu_r: diverging; viridis ... cividis: "
                 "perceptually uniform; turbo: rainbow; gray: grey scale"),
        *extra,
        dict(name="_display_update", label="Update plot", kind="button",
             step="@update:" + step, tip=UPDATE_TIP),
    ])


UPDATE_TIP = ("Redraw the figures of this step with the current settings: "
              "channels, individual profiles, time windows (shaded on the "
              "time maps) and display options. Changing these settings "
              "does not redraw anything until this button is pressed")


def update_group(step):
    """'Display' group of the steps without display options: only the
    Update button."""
    return ("Display", [dict(name="_display_update", label="Update plot",
                             kind="button", step="@update:" + step,
                             tip=UPDATE_TIP)])


def pre_channels():
    return ("Channels", [dict(name="CHANNELS", label="Channels",
                              kind="channels", choices="pre",
                              default=PRE_CHANNELS_DEFAULT)])


WHOLE_RECORD = "Whole record"


def window_field():
    """Time window of a step: the whole record or one of the windows W1,
    W2, ... defined in Data analysis › Load preprocessed data."""
    return dict(name="TIME_WINDOW", label="Time window", kind="window",
                default=WHOLE_RECORD,
                tip="Whole record, or one of the time windows defined in "
                    "Load preprocessed data (the list follows the table)")


def all_groups(section):
    """(title, fields) of every group of a section, the groups inside tabs
    included."""
    for item in section["params"]:
        if item[0] == "__tabs__":
            for _, groups in item[1]:
                yield from groups
        else:
            yield item


WHOLE_COLUMN = "Whole column"


def layer_field():
    """Layer of a step: the whole column or one layer of the multi-layer
    decomposition."""
    return dict(name="LAYER", label="Layer", kind="layer",
                default=WHOLE_COLUMN,
                tip="Whole column, or one layer of the Multi-layer "
                    "decomposition (run it first); the step then works on "
                    "the depths between the time-mean interfaces")


CHAIN_HELP = (
    "LéXPLORE thermistor chain (LéXPLORE platform, Lake Geneva), read from "
    "the preprocessed file or from the chain folder.\n\n"
    "Sampling in depth: 27 sensors at fixed depths below the surface: "
    "0.25, 1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 21, 24, 27 and 30 m, then "
    "every 5 m from 35 to 90 m. The spacing is 1 to 2 m near the surface, "
    "3 m from 18 to 30 m and 5 m below, i.e. much coarser than the DTS "
    "(about 0.25 m along the fibre).\n\n"
    "Sampling in time: one profile every 10 minutes (600 s), against one "
    "every 60 s to a few minutes for the DTS.\n\n"
    "In the steps that need a regular depth grid (wavenumber domain, 2D "
    "FFT, gradients, staircases, ...), the chain is first interpolated "
    "linearly onto a 1 m grid between its shallowest and deepest sensors; "
    "structures thinner than the sensor spacing are not resolved.\n\n"
    "Every variable of the LeXPLORE files is kept when the chain is read "
    "(and saved with it by the preprocessing); they are listed below.")


STC_HELP = (
    "STC profiler: Valeport SWiFT SVP (S/N 83629), lowered from a boat; "
    "one CSV file per profile (export of the .vp2 file of the same name, "
    "which also holds the position, the calibration and the pressure "
    "tare).\n\n"
    "Measured: the sound speed (time-of-flight sensor: measured directly, "
    "not computed), the temperature and the pressure (converted to depth). "
    "The salinity, density and conductivity of the .vp2 file are "
    "calculated by the instrument, not measured.\n\n"
    "Sampling in time: one profile per cast, lasting about one minute "
    "(descent at about 2 m/s; see the columns Duration and Descent).\n\n"
    "Sampling in depth: the instrument samples at 32 Hz and records in "
    "'SMART PROFILE' mode, about one value every half metre of descent; "
    "the native depth resolution of the profiles of the folder is given "
    "below. In sharp gradients the temperature sensor, slower than the "
    "sound-speed sensor, can smooth the profile.")

DTS_HELP = (
    "DTS: Silixa XT-DTS (S/N XT13002), fibre-optic cable laid as a U from "
    "the surface to the bottom near LéXPLORE; the preprocessed files "
    "(.nc with a Combined channel) of every configuration found in the "
    "folder and its sub-folders.\n\n"
    "Used here: the Combined channel (mean of the channels), on the "
    "calibrated depths (0 at the water surface), U-shaped mean (the "
    "descending and ascending legs of the cable averaged), the profile "
    "closest in time to the start of each STC profile.\n\n"
    "Sampling in depth: the fibre is sampled at a fixed step along its "
    "length, and the folded profile is on a regular depth grid; its native "
    "depth resolution (grid spacing) is given below for every record. "
    "Each sample averages the temperature of the fibre over the spatial "
    "resolution of the instrument, so features thinner than about a metre "
    "are smoothed.\n\n"
    "Sampling in time: one profile every one to a few minutes, depending "
    "on the configuration (below).")

CHAIN_FOLDER_HELP = (
    "LéXPLORE thermistor chain (LéXPLORE platform, Lake Geneva): the "
    "Datalakes Level-2 NetCDF files of the folder. When the chain has a "
    "profile within two of its time steps (about 20 min) of the start of "
    "an STC profile, the closest chain profile is added to the STC figure "
    "(temperature and the sound speed recalculated from it).\n\n"
    "Sampling in depth: sensors at fixed depths below the surface, about "
    "1 to 2 m apart near the surface, 3 m from 18 to 30 m and 5 m below "
    "(the depths of the files are listed below); much coarser than the "
    "DTS and the STC.\n\n"
    "Sampling in time: one profile every 10 minutes (600 s).")


def chain_field(default=True, tip=None):
    """'Include the LéXPLORE chain' with a (?) on its sampling."""
    field = dict(name="INCLUDE_CHAIN", label="Include the LéXPLORE chain",
                 kind="bool", default=default, help=CHAIN_HELP)
    if tip:
        field["tip"] = tip
    return field


def analysis_channels(chain=True, layer=True):
    fields = [dict(name="CHANNELS", label="Channels", kind="channels",
                   choices="analysis", default=ANALYSIS_CHANNELS_DEFAULT)]
    if chain:
        fields.append(chain_field())
    fields.append(window_field())
    if layer:
        fields.append(layer_field())
    return ("Channels", fields)


def one_channel(name, default="Combined", chain=False):
    fields = [dict(name=name, label="Channel analysed", kind="channel",
                   choices="analysis", default=default)]
    if chain:
        fields.append(chain_field(
            default=False, tip="Also run the step on the chain (interpolated "
                               "onto a 1 m grid); its figures are added"))
    fields.append(window_field())
    fields.append(layer_field())
    return ("Channel", fields)


def resolution_option(label="Colour floor = ½ resolution"):
    return dict(name="USE_RESOLUTION", label=label, kind="bool",
                default=False,
                tip="Half the instrument resolution sets the lower bound "
                    "of the colour (or amplitude) scale")


# ---------------------------------------------------------------------------
# PREPROCESSING
# ---------------------------------------------------------------------------
PREPROCESSING = [
    dict(
        id="pre.1", number="1", parent=None, title="Load raw data",
        actions=["pre.1.load", "pre.1.mirror", "pre.1.concat"],
        figures=[("pre.1.load", "Configuration", True),
                 ("pre.1.load", "Truncation", False),
                 ("pre.1.mirror", "Mirror distance vs time", False),
                 ("pre.1.mirror", "Uncalibrated Profiles", False),
                 ("pre.1.concat", "T(z, time) maps", True)],
        description=(
            "Load: inventory (summary.csv), clock correction, LéXPLORE "
            "coverage, raw cache of every profile, first profile truncated "
            "to [0, measurement length]. Mirror distance: bottom of the U "
            "for every profile. Concatenate: every profile folded on one "
            "common grid (connector coordinate), plus the 'Combined' channel; "
            "the T maps show the LéXPLORE chain on top when it is loaded. "
            "Run All does the three in order."),
        params=[
            ("Settings", [
                dict(name="_open_pre_settings",
                     label="Open preprocessing settings…", kind="button",
                     step="@open_settings:Preprocessing",
                     tip="Fill the preprocessing panels from a settings file "
                         "saved before (JSON)"),
            ]),
            ("Data", [
                dict(name="ROOT", label="Temperature folder", kind="dir",
                     default=XT_TEMPERATURE_ROOT,
                     tip="The 'temperature' folder of the XT, holding the "
                         "configurations; the log folder is read next to "
                         "it (../log)"),
                dict(name="CONFIGURATION", label="Configuration",
                     kind="configuration", root_field="ROOT",
                     default="",
                     tip="Sub-folder of the temperature folder"),
                dict(name="CHANNELS", label="Channels", kind="channels",
                     choices=[], default=[],
                     tip="The channel folders of the configuration"),
                dict(name="REBUILD_SUMMARY", label="Rebuild summary.csv",
                     kind="bool", default=False,
                     tip="Re-scan all the XML files for the inventory (after "
                         "a change of the folder content or of the time "
                         "correction)"),
                dict(name="REBUILD_RAW_CACHE", label="Rebuild the raw cache",
                     kind="bool", default=False,
                     tip="Read all the XML files again and rewrite "
                         "DTS_raw_cache.npz (the cache is also rebuilt "
                         "automatically for a channel whose files changed)"),
                dict(name="_chain_heading", label="LéXPLORE thermistor chain",
                     kind="heading"),
                dict(name="USE_LEXPLORE", label="Use LeXPLORE temperature",
                     kind="bool", default=True,
                     tip="Unticked: the chain is ignored and the depth is "
                         "calibrated by hand (Depth Calibration › Manual)"),
                dict(name="LEXPLORE_ROOT", label="Chain folder", kind="dir",
                     default=LEXPLORE_ROOT),
                dict(name="_time_heading", label="Time correction",
                     kind="heading"),
                dict(name="IS_TIME_CORRECTION", label="Correct to real UTC",
                     kind="bool", default=True),
                dict(name="reference_local_time", label="Reference time",
                     kind="datetime", zone="local, Europe/Zurich",
                     default="2026-10-29 10:21:00",
                     tip="The only time of the GUI given in local time"),
                dict(name="reference_utc_time_XT13002",
                     label="Same instant on the XT clock", kind="datetime",
                     default="2011-01-10 22:05:30"),
                dict(name="_load", label="Load", kind="button",
                     step="pre.1.load"),
            ]),
            ("Mirror distance", [
                dict(name="SCAN", label="Scan range (first profile)",
                     kind="float", unit="m", optional=True, default=None,
                     tip="auto = library default"),
                dict(name="STEP", label="Scan step", kind="float", unit="m",
                     optional=True, default=None, decimals=3,
                     tip="auto = library default"),
                dict(name="HALFWIDTH", label="Tracking half-width",
                     kind="float", unit="m", default=1.0),
                dict(name="_mirror", label="Run", kind="button",
                     step="pre.1.mirror"),
            ]),
            ("Concatenation", [
                dict(name="_concat_note",
                     label="Every profile folded at the mean mirror distance "
                           "on one common grid; with two channels or more, a "
                           "channel 'Combined' (profile-by-profile mean of the "
                           "channels) is added to the list of channels. The "
                           "maps are drawn with the display options of the "
                           "figure list (right).",
                     kind="note"),
                dict(name="_concat", label="Concatenate", kind="button",
                     step="pre.1.concat"),
            ]),
        ],
    ),
    dict(
        id="pre.2", number="2", parent=None, title="Depth Calibration",
        actions=["pre.2.1", "pre.2.2"],
        figures=[("pre.2.1", "First profile", True),
                 ("pre.2.1", "Z and T shift vs time", False),
                 ("pre.2.1", "DTS vs chain scatter", False)],
        focus_owner="pre.1.concat",   # the T maps come forward on this panel
        done_when="any",          # one of the two calibrations is enough
        description=(
            "Using LeXPLORE T-Chain: joint fit, profile by profile, of the "
            "vertical offset and the temperature shift of the DTS onto the "
            "chain, on a common sampling (the longest period of all the "
            "records). Manual: the water surface is read on the "
            "Uncalibrated Profiles (sharp air-to-water transition), by hand "
            "or with the mouse. Run All uses the chain when its data are "
            "used and cover the DTS window, the manual calibration "
            "otherwise."),
        params=[
            ("Using LeXPLORE T-Chain", [
                dict(name="CHANNELS", label="Channels", kind="channels",
                     choices="pre", default=PRE_CHANNELS_DEFAULT),
                dict(name="OFFSET_SCAN", label="Offset scan (±)",
                     kind="float", unit="m", default=20.0),
                dict(name="OFFSET_STEP", label="Offset step", kind="float",
                     unit="m", default=0.02, decimals=3),
                dict(name="FIT_TEMPERATURE_SHIFT",
                     label="Free temperature shift", kind="bool",
                     default=True),
                dict(name="Z_FIT_MIN", label="Chain depths from",
                     kind="float", unit="m", optional=True, default=None),
                dict(name="Z_FIT_MAX", label="Chain depths to",
                     kind="float", unit="m", optional=True, default=None),
                dict(name="TIME_WINDOWS", label="Time windows of the fit",
                     kind="windows", zone="UTC",
                     default=[],
                     tip="No row = the whole common window. The windows "
                         "are shaded on the T(z, time) maps"),
                dict(name="MAP_SELECT",
                     label="Select windows on the T maps",
                     on_text="on: drag on a map", kind="toggle",
                     tip="While on: drag horizontally on a T(z, time) map "
                         "to add a time window to the table (zoom and pan "
                         "of the figure tool bar must be off)"),
                dict(name="_chain_run", label="Run", kind="button",
                     step="pre.2.1"),
            ]),
            ("Manual", [
                dict(name="Z_SURFACE", label="Water surface position",
                     kind="float", unit="m", default=14.07,
                     tip="Connector coordinate (0 at the XT); drawn as an "
                         "orange line on the Uncalibrated Profiles"),
                dict(name="SURFACE_SELECT",
                     label="Select the surface with the mouse",
                     on_text="on: click on the profiles", kind="toggle",
                     tip="While on: a click on the Uncalibrated Profiles "
                         "figure sets the water-surface position (zoom and "
                         "pan of the figure tool bar must be off)"),
                dict(name="_manual_run", label="Run", kind="button",
                     step="pre.2.2"),
            ]),
            update_group("pre.2"),
        ],
    ),
    dict(
        id="pre.3", number="3", parent=None, title="Save",
        hide_run=True,
        figures=[("pre.3", "Calibrated T(depth, time)", False)],
        description=(
            "The calibration is applied to the whole record (mean shifts; "
            "the options follow the depth calibration done), every channel (the 'Combined' channel of the concatenation "
            "included) is saved in DTS_preprocessed.nc."),
        params=[
            ("Save", [
                dict(kind="heading", label="Calibration"),
                dict(name="CALIBRATION", label="Calibration",
                     kind="choice",
                     choices=["Shift in Z and T", "Shift in Z only"],
                     default="Shift in Z and T",
                     tip="The list follows the depth calibration done: with "
                         "the LeXPLORE chain - shift in Z and T, or Z only; "
                         "manual - shift in Z"),
                dict(kind="heading", label="Data to save"),
                dict(name="SAVE_UNCALIBRATED", label="DTS uncalibrated "
                     "(all channels)", kind="bool", default=True,
                     tip="T(z, time) in the connector coordinate, every "
                         "channel"),
                dict(name="SAVE_CALIBRATED", label="DTS calibrated "
                     "(all channels)", kind="bool", default=True,
                     tip="T(z, time) after the depth calibration (needed by "
                         "the analysis)"),
                dict(name="SAVE_CONFIGURATION", label="Configuration",
                     kind="bool", default=True,
                     tip="The configuration table of Load raw data"),
                dict(name="SAVE_LEXPLORE", label="LeXPLORE data (if used in "
                     "the calibration)", kind="bool", default=True,
                     tip="Saved as the channel 'LeXPLORE T-chain' when the "
                         "chain was used in the depth calibration"),
                dict(kind="note", label="The variables used during the "
                     "preprocessing (settings of every step, mirror "
                     "distances, fitted offsets, ...) are always saved in "
                     "the group 'preprocessing'."),
                dict(kind="heading", label="Output file"),
                dict(name="OUTPUT_FOLDER", label="Output folder", kind="dir",
                     optional=True, default="",
                     placeholder="empty = the configuration folder",
                     tip="Set to the configuration folder when the raw data "
                         "are loaded (empty = the configuration folder)"),
                dict(name="PRODUCT_NAME", label="Preprocessed data file",
                     kind="text", default="DTS_preprocessed.nc",
                     tip="Name of the netCDF file (.nc added if missing); "
                         "Load preprocessed data lists every preprocessed "
                         "file of the configuration"),
                dict(name="_run_save", label="Save", kind="button",
                     step="pre.3",
                     tip="Apply the calibration and write the preprocessed "
                         "data file"),
            ]),
            ("Preprocessing settings", [
                dict(kind="heading", label="Output file"),
                dict(name="SETTINGS_FOLDER", label="Output folder",
                     kind="dir", optional=True, default="",
                     placeholder="empty = the configuration folder",
                     tip="Set to the configuration folder when the raw data "
                         "are loaded (empty = the configuration folder)"),
                dict(name="SETTINGS_NAME", label="Settings file",
                     kind="text", default="DTS_preprocessing_settings.json",
                     tip="Name of the JSON file (.json added if missing)"),
                dict(name="_save_pre_settings", label="Save", kind="button",
                     step="@save_settings_to:Preprocessing",
                     tip="Save the inputs of every preprocessing panel (and "
                         "the display options of the maps) in this file"),
            ]),
        ],
    ),
    dict(
        id="pre.4", number="4", parent=None, title="Preprocessing report",
        description=("Markdown report (with the configuration table) and the "
                     "figures of the steps run, next to "
                     "DTS_preprocessed.nc."),
        params=[
            ("Report", [
                dict(name="REPORT_NAME", label="Report file", kind="text",
                     default="DTS_preprocessing_report.md"),
                dict(name="FIGURES_NAME", label="Figure folder", kind="text",
                     default="DTS_preprocessing_report_figures"),
                dict(name="FIGURE_DPI", label="Figure resolution",
                     kind="int", unit="dpi", default=150, minimum=50,
                     maximum=600),
            ]),
        ],
    ),
]


# ---------------------------------------------------------------------------
# DATA ANALYSIS
# ---------------------------------------------------------------------------
ANALYSIS = [
    dict(
        id="ana.0", number="0", parent=None,
        title="Load preprocessed data",
        actions=["ana.0", "ana.0.1"],
        hidden_groups=["Maps", "Time windows",
                       "Select Individual profiles", "Display"],
        figures=[("ana.0", "Configuration", True),
                 ("ana.0.1", "T(z, t) maps", True),
                 ("ana.0.1", "Individual profiles", False)],
        description=(
            "Choose the root folder of the preprocessed data, the "
            "configuration and the preprocessed file, and press Load data. "
            "Then tick the channels of the maps, choose the individual "
            "profiles (table or clicks on the map) and press Update."),
        params=[
            ("Preprocessed data", [
                dict(name="PRODUCT_ROOT", label="Root folder", kind="dir",
                     default=XT_TEMPERATURE_ROOT,
                     tip="Folder whose sub-folders (configurations) hold "
                         "preprocessed files (.nc)"),
                dict(name="CONFIGURATIONS", label="Configuration",
                     kind="products",
                     tip="Sub-folders of the root folder that hold a "
                         "preprocessed file (.nc)",
                     root_field="PRODUCT_ROOT",
                     default=[]),
                dict(name="PREPROCESSED_FILES", label="Preprocessed file",
                     kind="product_files", root_field="PRODUCT_ROOT",
                     configurations_field="CONFIGURATIONS",
                     default=[],
                     tip="The preprocessed .nc files of the configuration "
                         "chosen (DTS_preprocessed.nc first)"),
                dict(name="LEXPLORE_ROOT", label="LéXPLORE chain folder",
                     kind="dir", optional=True, default="",
                     placeholder="empty = the chain saved in the file",
                     tip="Empty: the chain saved in DTS_preprocessed.nc (or "
                         "the chain folder stored in it)"),
                dict(name="_load", label="Load data", kind="button",
                     steps=["ana.0", "ana.0.1"]),
            ]),
            ("Settings", [
                dict(name="_open_ana_settings",
                     label="Open analysis settings…", kind="button",
                     step="@open_settings:Data analysis",
                     tip="Fill the analysis panels from a settings file "
                         "saved before (JSON); the data chosen above are "
                         "kept"),
                dict(name="_run_saved", label="Run the saved analysis",
                     kind="button", step="@run_saved_analysis",
                     tip="Load the file chosen above, then run every "
                         "analysis step recorded in the settings opened, "
                         "in their order, with their saved inputs"),
            ]),
            ("Maps", [
                dict(name="MAP_CHANNELS", label="Channels on the maps",
                     kind="channels", choices="analysis", default=[],
                     tip="Channels drawn on the T(z, t) maps and the "
                         "individual profiles of this panel; every channel "
                         "stays available to the analysis steps, each with "
                         "its own selection"),
                chain_field(tip="Adds the chain (when available) to the "
                                "maps of Load preprocessed data"),
                window_field(),
                dict(name="_update", label="Update maps", kind="button",
                     step="ana.0.select",
                     tip="Maps of the channels ticked with the chain "
                         "option and the time window chosen"),
            ]),
            ("Time windows", [
                dict(name="WINDOWS", label="Windows (label, UTC times)",
                     kind="named_windows", zone="UTC", default=[],
                     tip="Labelled W1, W2, ... ; every analysis step can be "
                         "run on one of them (list 'Time window' below the "
                         "channels)"),
                dict(name="WINDOW_SELECT",
                     label="Select windows on the T(z, t) map",
                     on_text="on: drag on the T(z, t) map", kind="toggle",
                     tip="While on: drag horizontally on the T(z, t) map to "
                         "add a window (zoom and pan of the figure tool bar "
                         "must be off)"),
            ]),
            ("Select Individual profiles", [
                dict(name="PROFILE_TIMES", label="Profiles (label, UTC time)",
                     kind="timetable", zone="UTC", default=[],
                     tip="Individual profiles used by 4.1.1, 4.2 and 4.2.1"),
                dict(name="PROFILE_SELECT",
                     label="Select profiles on the T(z, t) map",
                     on_text="on: click on the T(z, t) map", kind="toggle",
                     tip="While on: a click on the T(z, t) map adds the "
                         "nearest profile to the table (zoom and pan of the "
                         "figure tool bar must be off)"),
                dict(name="_profiles_update", label="Update", kind="button",
                     step="ana.0.instants",
                     tip="Use the profiles of the table in the analyses and "
                         "mark them on the T(z, t) maps"),
            ]),
            display_group("ana.0"),
        ],
    ),
    dict(
        id="ana.0.3", number="0.3", parent=None, title="Resampling data",
        description=("Resamples the channels ticked in space (window "
                     "average over depth) and/or in time (time base of the "
                     "LeXPLORE chain, or window average in time); each "
                     "resampled set becomes a new channel '<channel>-"
                     "resampled', available in every following step."),
        hide_run=True,
        params=[
            ("Channels", [
                dict(name="CHANNELS", label="Channels", kind="channels",
                     choices="files", default=ANALYSIS_CHANNELS_DEFAULT),
            ]),
            ("Resampling", [
                dict(name="SPATIAL", label="Spatial resampling",
                     kind="bool", default=False,
                     tip="Window average over depth"),
                dict(name="SPACE_WIDTH", label="Window size", kind="float",
                     unit="m", default=2.0),
                dict(name="SPACE_STEP", follows="SPACE_WIDTH", label="Window step", kind="float",
                     unit="m", optional=True, default=None,
                     tip="Distance between the window centres; auto = the "
                         "window size (windows side by side)"),
                dict(name="TEMPORAL", label="Time resampling", kind="bool",
                     default=False),
                dict(name="TIME_LEXPLORE", group="TIME_MODE",
                     label="Same time base as LeXPLORE", kind="radio",
                     default=True,
                     tip="Average over one chain sampling period centred on "
                         "every chain time stamp (the DTS must sample "
                         "faster than the chain)"),
                dict(name="TIME_AVERAGING", group="TIME_MODE",
                     label="Window averaging in time", kind="radio",
                     default=False),
                dict(name="PERIOD_MIN", label="Period", kind="float",
                     unit="min", default=10.0,
                     tip="Length of the time window"),
                dict(name="TIME_STEP_MIN", follows="PERIOD_MIN", label="Step", kind="float",
                     unit="min", optional=True, default=None,
                     tip="Time between the new profiles (auto = the "
                         "period)"),
                dict(name="_run", label="Run", kind="button",
                     step="ana.0.3"),
            ]),
            display_group("ana.0.3", extra=[
                dict(name="PLOT_PROFILES",
                     label="Raw and resampled profiles", kind="bool",
                     default=False,
                     tip="Profiles of the individual profiles list (Load "
                         "Data), raw and resampled"),
            ]),
        ],
    ),
    dict(
        id="ana.2", number="2", parent=None, title="Following an isotherm",
        description=("Depth of one isotherm vs time, with the "
                     "half-grid-spacing uncertainty."),
        hide_run=True,
        params=[
            analysis_channels(layer=False),
            ("Isotherm", [dict(name="T_ISO", label="Isotherm", kind="float",
                               unit="°C", default=10.0),
                          dict(name="_run", label="Run", kind="button",
                               step="ana.2")]),
            update_group("ana.2"),
        ],
    ),
    dict(
        id="ana.0.2", number="0.2", parent=None,
        title="Brunt–Väisälä frequency",
        description=("N = √(−g α(T) dT/dz) / 2π in Hz at every depth and "
                     "time; time mean ± std and maps."),
        hide_run=True,
        params=[
            ("Channels", analysis_channels(layer=False)[1] + [
                dict(name="IS_N_SMOOTHING", label="Smooth T before N",
                     kind="bool", default=False,
                     help=("The temperature of the DTS channels is averaged "
                           "over depth windows ('window width', centred "
                           "every 'window step') BEFORE dT/dz and N are "
                           "computed, so the noise is reduced before the "
                           "square root and the deep, weakly stratified "
                           "water no longer shows a false positive N. The "
                           "chain is not smoothed. g and the equation of "
                           "state come from Advanced › Physical "
                           "parameters.")),
                dict(name="N_SMOOTH_WIDTH", label="Window width",
                     kind="float", unit="m", default=2.0),
                dict(name="N_SMOOTH_STEP", follows="N_SMOOTH_WIDTH",
                     label="Window step",
                     kind="float", unit="m", optional=True, default=None,
                     tip="auto = the window width (windows side by "
                         "side)"),
                dict(name="_run", label="Run", kind="button",
                     step="ana.0.2")]),
            display_group("ana.0.2"),
        ],
    ),
    dict(
        id="ana.1", number="1", parent=None,
        title="Multi-layer decomposition",
        description=("Splits the water column into one, two or three "
                     "layers; the interfaces are drawn on the temperature "
                     "maps."),
        hide_run=True,
        groups_shown_by=("LAYERING", {"Two layers": ["Two layers"],
                                      "Three layers": ["Three layers"]}),
        params=[
            analysis_channels(layer=False),
            ("Individual profiles", [
                dict(name="LAYER_PROFILES",
                     label="Profiles (label, UTC time)",
                     kind="timetable", zone="UTC", default=[],
                     tip="Profiles drawn with their interfaces and the "
                         "straight line fitted in each layer (the list "
                         "shared by all the steps with individual "
                         "profiles)"),
                dict(name="LAYER_SELECT",
                     label="Select individual profiles on the map",
                     on_text="on: click on the Layers maps", kind="toggle",
                     tip="While on: a click on the Layers maps adds the "
                         "nearest profile (zoom and pan of the figure tool "
                         "bar must be off)"),
                dict(name="_layer_update", label="Update", kind="button",
                     step="ana.1.replot",
                     tip="Redraw the figures with the profiles of the "
                         "table"),
            ]),
            ("Layering", [
                dict(name="LAYERING", label="Layering", kind="choice",
                     choices=["One layer", "Two layers", "Three layers"],
                     default="One layer",
                     tip="One layer: nothing to do; two or three layers: "
                         "choose the method in the box below"),
            ]),
            ("Two layers", [
                dict(name="TWO_SMOOTHING", label="Smoothing",
                     kind="bool", default=False,
                     tip="Window average of T over depth before the "
                         "interfaces are extracted (as in Brunt–Väisälä)"),
                dict(name="TWO_SMOOTH_WIDTH", label="Window width",
                     kind="float", unit="m", default=2.0),
                dict(name="TWO_SMOOTH_STEP", follows="TWO_SMOOTH_WIDTH", label="Window step",
                     kind="float", unit="m", optional=True, default=None,
                     tip="auto = the window width (windows side by "
                         "side)"),
                dict(name="TWO_FROM_THERMOCLINE", group="TWO",
                     label="From thermocline LeXPLORE", kind="radio",
                     default=True,
                     tip="Interface = the thermocline_depth of the LeXPLORE "
                         "files, interpolated in time onto every record"),
                dict(name="TWO_FROM_ISOTHERM", group="TWO",
                     label="From isotherm", kind="radio", default=False,
                     tip="Interface = depth of the isotherm below in each "
                         "record"),
                dict(name="T_ISOTHERM", label="T isotherm", kind="float",
                     unit="°C", default=10.0),
                dict(name="_run_two", label="Run", kind="button",
                     step="ana.1"),
            ]),
            ("Three layers", [
                dict(name="THREE_SMOOTHING", label="Smoothing",
                     kind="bool", default=False,
                     tip="Window average of T over depth before the "
                         "interfaces are extracted (as in Brunt–Väisälä)"),
                dict(name="THREE_SMOOTH_WIDTH", label="Window width",
                     kind="float", unit="m", default=2.0),
                dict(name="THREE_SMOOTH_STEP", follows="THREE_SMOOTH_WIDTH", label="Window step",
                     kind="float", unit="m", optional=True, default=None,
                     tip="auto = the window width (windows side by "
                         "side)"),
                dict(name="THREE_FROM_ISOTHERMS", group="THREE",
                     label="From isotherms", kind="radio", default=True,
                     tip="Z1 = depth of the top isotherm, Z2 = depth of the "
                         "bottom isotherm, in each record"),
                dict(name="T_TOP", label="Top isotherm", kind="float",
                     unit="°C", default=12.0),
                dict(name="T_BOTTOM", label="Bottom isotherm", kind="float",
                     unit="°C", default=8.0),
                dict(name="THREE_BEST_FIT", group="THREE", label="Best fit",
                     kind="radio", default=False,
                     tip="The best fit of the three-layer steps (4.2.1): "
                         "outer layers fitted from both ends"),
                dict(name="RMS_TOL", label="Line-fit tolerance",
                     kind="float", unit="K", default=0.05, decimals=3),
                dict(name="MIN_POINTS", label="Min. points per layer",
                     kind="int", default=5, minimum=2, maximum=100),
                dict(name="MIN_GAP", label="Min. interface gap",
                     kind="float", unit="m", default=2.0),
                dict(name="_run_three", label="Run", kind="button",
                     step="ana.1"),
            ]),
            display_group("ana.1"),
        ],
    ),
    dict(
        id="ana.3", number="3", parent=None,
        title="Spectral analysis – frequency domain",
        description=("Fourier transforms in time: the temperature at each "
                     "depth (tab 1) or the depth of an isotherm (tab 2)."),
        actions=["ana.3.1", "ana.3.2"],
        hide_run=True,
        params=[
            ("Channels", analysis_channels(layer=False)[1]),
            ("__tabs__", [
                ("Temperature at each depth", [
                    ("Options", [
                        dict(layer_field(), only_for=["ana.3.1"]),
                        dict(name="IS_N_SMOOTHING", label="Smooth N", kind="bool",
                             default=True,
                             help=("Smooth N applies an additional smoothing "
                                   "to the Brunt–Väisälä frequency N drawn on "
                                   "the maps: the time-average N profile "
                                   "(from the Brunt–Väisälä step) is averaged "
                                   "again over depth windows of 'N window "
                                   "width', centred every 'N window step'. "
                                   "It only changes the N curve overlaid on "
                                   "the spectra, not the FFT itself.")),
                        dict(name="N_SMOOTH_WIDTH", label="N window width",
                             kind="float", unit="m", default=2.0),
                        dict(name="N_SMOOTH_STEP", follows="N_SMOOTH_WIDTH", label="N window step",
                             kind="float", unit="m", optional=True, default=None,
                             tip="auto = the N window width (windows side "
                                 "by side)"),
                        dict(kind="note", label="Latitude of the Coriolis "
                             "frequency: Advanced › Physical parameters"),
                        dict(name="_run", label="Run", kind="button",
                             step="ana.3.1"),
                    ]),
                    display_group("ana.3.1", extra=[
                        dict(name="PERIOD_MAX_PLOT", label="Longest period plotted",
                             kind="float", unit="h", default=36.0, optional=True,
                             auto_default=False,
                             tip="auto = every period (frequency) available"),
                        dict(name="PERIOD_MAX_COLOUR",
                             label="Longest period for colours", kind="float",
                             unit="h", default=36.0, optional=True,
                             auto_default=False,
                             tip="auto = every period (frequency) available"),
                        dict(name="COLOUR_LIMITS", label="Colour limits",
                             kind="choice",
                             choices=["None", "Instrument resolution",
                                      "User defined"], default="None",
                             tip="None: automatic (50th - 99.5th percentile of the "
                                 "amplitudes); Instrument resolution: lower limit = "
                                 "half the instrument resolution; User defined: the "
                                 "two values below (auto = automatic)"),
                        dict(name="COLOUR_MIN", label="Lower colour limit",
                             kind="float", unit="K", optional=True, default=None,
                             decimals=4, minimum=0.0,
                             tip="Used with 'User defined' (auto = automatic)"),
                        dict(name="COLOUR_MAX", label="Upper colour limit",
                             kind="float", unit="K", optional=True, default=None,
                             decimals=4, minimum=0.0,
                             tip="Used with 'User defined' (auto = automatic)"),
                        dict(name="X_AXIS", label="x axis", kind="choice",
                             choices=["frequency", "period"], default="frequency",
                             tip="frequency (Hz) or period (hours)"),
                        dict(name="X_SCALE", label="x axis scale", kind="choice",
                             choices=["log", "linear"], default="log"),
                    ]),
                ]),
                ("Isotherm depth", [
                    ("Options", [
                        dict(name="T_PICK", label="Isotherm", kind="float",
                             unit="°C", default=10.0),
                        dict(name="POINCARE_WINDOW", label="Poincaré profiles",
                     help=("Select the time window used to estimate the "
                           "frequency / period of the V1 Poincaré mode. For "
                           "every profile of that window, a two-layer model "
                           "of the stratification gives a V1 Poincaré "
                           "frequency; the band between the lowest and the "
                           "highest is shaded on the spectrum. 'Same as DTS "
                           "time window' uses the profiles of the FFT; the "
                           "time windows W1, W2, ... come from Load preprocessed data."),
                             kind="window", first_item="Same as DTS time window",
                             default="Same as DTS time window",
                             tip="Profiles used for the Poincaré estimate: those of "
                                 "the time window of the step, or one of the time "
                                 "windows of Load preprocessed data (inside the DTS window)"),
                        dict(kind="note", label="Lake width, gravity and "
                             "equation of state of the Poincaré estimate: "
                             "Advanced › Physical parameters"),
                        dict(name="_run", label="Run", kind="button",
                             step="ana.3.2"),
                    ]),
                    ("Display", [
                        resolution_option("Use the instrument resolution"),
                        dict(name="SPECTRUM_AXIS", label="x axis", kind="choice",
                             choices=["frequency", "period"], default="frequency",
                             tip="Spectrum against frequency (Hz, period on the top "
                                 "axis) or period (hours)"),
                        dict(name="SPECTRUM_SCALE", label="x axis scale",
                             kind="choice", choices=["log", "linear"],
                             default="log"),
                        dict(name="_display_update", label="Update plot",
                             kind="button", step="@update:ana.3.2",
                             tip=UPDATE_TIP),
                    ]),
                ]),
            ]),
        ],
    ),
    dict(
        id="ana.4.1.1", number="4.1.1", parent=None,
        title="Spectral analysis – wavenumber domain",
        description=("Vertical FFT of every profile; maps time × k_z with "
                     "the spectra of the example instants of 0.1."),
        hide_run=True,
        params=[
            ("Channels", analysis_channels()[1] + [
                dict(name="_run", label="Run", kind="button",
                     step="ana.4.1.1")]),
            ("Individual profiles", [
                dict(name="KZ_PROFILES", label="Profiles (label, UTC time)",
                     kind="timetable", zone="UTC", default=[],
                     tip="Profiles whose vertical FFT is plotted; the "
                         "profiles of Load preprocessed data are added automatically"),
                dict(name="KZ_SELECT",
                     label="Select individual profiles on the map",
                     on_text="on: click on the k_z map", kind="toggle",
                     tip="While on: a click on the Time × k_z map adds the "
                         "nearest profile (zoom and pan of the figure tool "
                         "bar must be off)"),
                dict(name="_kz_update", label="Update", kind="button",
                     step="ana.4.1.1.replot",
                     tip="Redraw the figures with the profiles of the table: "
                         "spectra of the profiles and lines on the maps"),
            ]),
            ("Wavenumber range and scaling law", [
                dict(name="K_MIN", label="k min", kind="float",
                     unit="1/m", default=0.05, decimals=4, optional=True,
                     auto_text="none",
                     tip="Smallest wavenumber of the range (none = the "
                         "smallest of the spectrum)"),
                dict(name="K_MAX", label="k max", kind="float",
                     unit="1/m", default=1.0, decimals=4, optional=True,
                     auto_text="none",
                     tip="Largest wavenumber of the range (none = the "
                         "largest of the spectrum)"),
                dict(name="K_SELECT",
                     label="Select the range on the spectra",
                     on_text="on: drag on the FFT of the profiles",
                     kind="toggle",
                     tip="While on: a horizontal drag on the figure FFT of "
                         "the individual profiles sets k min and k max"),
                dict(name="_fit_scaling", label="Fit scaling",
                     kind="button", step="ana.4.1.1.fit",
                     tip="Fit A = a k^b (least squares in log-log) to every "
                         "curve of every panel, within the range; the laws "
                         "are drawn dashed and written in the log"),
            ]),
            display_group("ana.4.1.1", extra=[
                dict(name="WAVELENGTH_MAX_PLOT",
                     label="Longest wavelength plotted", kind="float",
                     unit="m", default=50.0, optional=True,
                     auto_default=False, auto_text="full spectrum",
                     tip="Ticked 'full spectrum': every wavenumber of the "
                         "profiles is plotted"),
                dict(name="WAVELENGTH_MAX_COLOUR",
                     label="Longest wavelength for colours", kind="float",
                     unit="m", default=50.0, optional=True,
                     auto_default=False, auto_text="full spectrum",
                     tip="Ticked 'full spectrum': the colour scale uses "
                         "every wavenumber plotted"),
                dict(name="VERTICAL_AXIS", label="Vertical axis",
                     kind="choice", choices=["wavelength", "wavenumber"],
                     default="wavelength"),
                resolution_option("Instrument resolution"),
            ]),
        ],
    ),
    dict(
        id="ana.4.1.2", number="4.1.2", parent=None,
        title="2D FFT of the water column",
        description=("2D FFT (depth × time), unsigned k_z and frequency, of "
                     "every layer ticked; one figure per channel."),
        hide_run=True,
        params=[
            ("Channels", analysis_channels(layer=False)[1] + [
                dict(name="LAYERS", label="Layers", kind="layers",
                     choices=[WHOLE_COLUMN], default=[WHOLE_COLUMN],
                     tip="Parts of the water column transformed, one panel "
                         "each: the whole column and the layers of the "
                         "Multi-layer decomposition (run it first)"),
                dict(name="_run", label="Run", kind="button",
                     step="ana.4.1.2")]),
            display_group("ana.4.1.2", extra=[
                dict(name="VERTICAL_AXIS", label="Vertical axis",
                     kind="choice", choices=["wavenumber", "wavelength"],
                     default="wavenumber"),
                dict(name="TIME_AXIS", label="Horizontal axis", kind="choice",
                     choices=["frequency", "period"], default="frequency"),
                resolution_option("Instrument resolution"),
            ]),
        ],
    ),
    dict(
        id="ana.4.2.6", number="4.2.6", parent=None,
        title="Temperature-gradient maps",
        description=("Raw dT/dz over the whole column and record, and the "
                     "gradient of the individual profiles (all channels)."),
        hide_run=True,
        params=[("Channels", analysis_channels()[1] + [
                    dict(name="IS_GRADIENT_SMOOTHING",
                         label="Smooth T before dT/dz", kind="bool",
                         default=False,
                         help=("Off: dT/dz of the raw temperature. On: the "
                               "temperature is first averaged over depth "
                               "windows ('window width', centred every "
                               "'window step') and dT/dz is taken on the "
                               "window centres, as for the Brunt–Väisälä "
                               "frequency.")),
                    dict(name="GRADIENT_SMOOTH_WIDTH", label="Window width",
                         kind="float", unit="m", default=1.0),
                    dict(name="GRADIENT_SMOOTH_STEP",
                         follows="GRADIENT_SMOOTH_WIDTH",
                         label="Window step", kind="float", unit="m",
                         optional=True, default=None,
                         tip="auto = the window width (windows side by "
                             "side)"),
                    dict(name="_run", label="Run", kind="button",
                         step="ana.4.2.6")]),
                ("Individual profiles", [
                    dict(name="GRADIENT_PROFILES",
                         label="Profiles (label, UTC time)",
                         kind="timetable", zone="UTC", default=[],
                         tip="Profiles whose gradient is plotted (all the "
                             "channels); the profiles of Load preprocessed "
                             "data are added automatically"),
                    dict(name="GRADIENT_SELECT",
                         label="Select individual profiles on the map",
                         on_text="on: click on the gradient map",
                         kind="toggle",
                         tip="While on: a click on the gradient maps adds "
                             "the nearest profile (zoom and pan of the "
                             "figure tool bar must be off)"),
                    dict(name="_grad_update", label="Update", kind="button",
                         step="ana.4.2.6.replot",
                         tip="Redraw the figures with the profiles of the "
                             "table: individual profiles and lines on the "
                             "maps"),
                ]),
                display_group("ana.4.2.6")],
    ),
    dict(
        id="ana.4.2.5", number="4.2.5", parent=None,
        title="Staircases detection",
        description=("Staircase detection at the individual profiles, "
                     "inside the layer chosen in the list 'Layer' (its "
                     "interfaces at each profile; Whole column = the whole "
                     "profile); all the channels ticked on one figure. "
                     "Seismogram-like profiles: every S2 profile "
                     "of a time window, demeaned and offset."),
        actions=["ana.4.2.5", "ana.4.2.9"],
        hide_run=True,
        params=[
            ("Channels", [
                dict(f, only_for=["ana.4.2.5"])
                if f["name"] in ("TIME_WINDOW", "LAYER") else f
                for f in analysis_channels()[1]]),
            ("Individual profiles", [
                dict(name="STAIRCASE_PROFILES",
                     label="Profiles (label, UTC time)",
                     kind="timetable", zone="UTC", default=[],
                     tip="Profiles analysed (the list shared by all the "
                         "steps with individual profiles)"),
                dict(name="STAIRCASE_SELECT",
                     label="Select individual profiles on the map",
                     on_text="on: click on the T(z, t) map", kind="toggle",
                     tip="While on: a click on the T(z, t) maps of this step "
                         "adds the nearest profile (zoom and pan of the "
                         "figure tool bar must be off)"),
                dict(name="_stair_update", label="Update", kind="button",
                     step="ana.4.2.5",
                     tip="Detect the staircases at the profiles of the "
                         "table"),
            ]),
            ("Detection", [
                dict(name="USE_GRAD_FACTOR", group="STAIR_THRESHOLD",
                     label="Threshold from the gradient factor",
                     kind="radio", default=True,
                     tip="A step is where |dT/dz| < gradient factor × the "
                         "mean |dT/dz| of the layer"),
                dict(name="GRAD_FACTOR", label="Gradient factor",
                     kind="float", default=0.3, enabled_by="USE_GRAD_FACTOR",
                     help=("A step (well-mixed tread) is a part of the "
                           "profile where the vertical gradient is weak. "
                           "The gradient factor sets how weak: after the "
                           "smoothing, every depth where |dT/dz| is smaller "
                           "than the gradient factor times the mean "
                           "gradient of the layer (temperature difference "
                           "between its top and bottom divided by its "
                           "thickness) belongs to a step, if the run of "
                           "such depths is at least 'Min. step thickness' "
                           "thick. Example: 0.3 keeps the parts whose "
                           "gradient is below 30 % of the mean gradient. A "
                           "smaller factor finds fewer, better-mixed steps; "
                           "a larger one finds more. The threshold follows "
                           "the stratification of each profile.")),
                dict(name="USE_MAX_GRADIENT", group="STAIR_THRESHOLD",
                     label="Threshold from a maximum dT/dz",
                     kind="radio", default=False,
                     tip="A step is where |dT/dz| < Max |dT/dz|, the same "
                         "value for every profile"),
                dict(name="MAX_GRADIENT", label="Max |dT/dz|",
                     kind="float", unit="K/m", default=0.02, decimals=3,
                     enabled_by="USE_MAX_GRADIENT",
                     tip="Fixed threshold of the gradient (absolute value)"),
                dict(name="MIN_THICKNESS", label="Min. step thickness",
                     kind="float", unit="m", default=1.0),
                dict(name="SMOOTH_LENGTH", label="Smoothing length",
                     kind="float", unit="m", default=0.5,
                     help=("Before the gradient is computed, each profile "
                           "is smoothed in depth by a running mean (moving "
                           "average) over this length: every sample is "
                           "replaced by the mean of the samples within "
                           "± half the length around it (the length divided "
                           "by the depth spacing, rounded to an odd number "
                           "of samples; the spacing is about 0.25 m for "
                           "the DTS and 1 m for the chain on its grid). The "
                           "smoothing removes the instrument noise, which "
                           "would otherwise make |dT/dz| jump above and "
                           "below the threshold and cut the steps into "
                           "pieces. A longer length gives cleaner, more "
                           "continuous steps but blurs the thin interfaces "
                           "between them and can merge close steps; a "
                           "shorter one keeps thin structures but leaves "
                           "more noise. It should stay smaller than 'Min. "
                           "step thickness'. 0 (or less than the depth "
                           "spacing) means no smoothing. The step means "
                           "(thick segments) are computed on the "
                           "unsmoothed profile.")),
                dict(name="_run", label="Run", kind="button",
                     step="ana.4.2.5"),
            ]),
            ("Seismogram-like profiles", [
                dict(kind="note", label="Every profile of the metalimnion "
                     "(S2, between Z1 and Z2) in a time window, demeaned and "
                     "shifted, for every channel ticked above."),
                dict(name="SEISMO_WINDOW", label="Time window",
                     kind="window", default="Start and duration below",
                     first_item="Start and duration below",
                     tip="One of the time windows W1, W2, ... of Load "
                         "preprocessed data (every profile inside it), or "
                         "the start and duration below"),
                dict(name="WATERFALL_START", label="Start",
                     kind="profile_time", zone="UTC",
                     default="",
                     tip="Choose one of the individual profiles (the list "
                         "shared by all the steps) or type a time "
                         "YYYY-MM-DD hh:mm:ss"),
                dict(name="WATERFALL_DURATION_HOURS", label="Duration",
                     kind="float", unit="h", default=1.0),
                dict(name="WATERFALL_STEP_MIN", label="Step", kind="float",
                     unit="min", optional=True, default=None,
                     tip="Time between the successive profiles plotted, in "
                         "the duration or the time window (the profile "
                         "nearest to every step); auto = every profile"),
                dict(name="WATERFALL_SPACING", label="Spacing",
                     kind="float", unit="K", default=0.5),
                dict(name="_run_seismo", label="Plot", kind="button",
                     step="ana.4.2.9",
                     tip="Seismogram-like plot of the profiles of the time "
                         "window"),
            ]),
            update_group("ana.4.2.5"),
        ],
    ),
    dict(
        id="ana.5", number="5", parent=None, title="Analysis report",
        description=("Markdown report + the figures of the analysis steps "
                     "run, next to DTS_preprocessed.nc."),
        params=[
            ("Report", [
                dict(name="REPORT_NAME", label="Report file", kind="text",
                     default="DTS_analysis_report.md"),
                dict(name="FIGURES_NAME", label="Figure folder",
                     kind="text", default="DTS_analysis_report_figures"),
                dict(name="OUTPUT_FOLDER", label="Output folder", kind="dir",
                     optional=True, default="",
                     placeholder="empty = the first data folder"),
            ]),
        ],
    ),
]

# ---------------------------------------------------------------------------
# ADVANCED (the item Physical parameters… of this menu is a window, added by
# dts_gui; the panels below work on the data of Load preprocessed data)
# ---------------------------------------------------------------------------
STC_ROOT = default_paths.get("stc")
DTS_ROOT = default_paths.get("dts")

ADVANCED = [
    dict(
        id="ana.6", number="A1", parent=None, title="Sound speed maps",
        description=("Speed of sound c(T, P, S) of every DTS profile "
                     "(formula of Advanced › Physical parameters), mapped "
                     "over depth and time; STC profiler profiles compared "
                     "with the DTS."),
        actions=["ana.6", "ana.6.stc"],
        hide_run=True,
        params=[
            ("STC profiles and sound speed", [
                dict(name="STC_FOLDER", label="STC folder", kind="dir",
                     default=STC_ROOT, help=STC_HELP,
                     tip="Folder of the STC profiles (SWiFT SVP CSV "
                         "exports, one file per profile; the position is "
                         "read from the .vp2 file of the same name)"),
                dict(name="DTS_FOLDER", label="DTS folder", kind="dir",
                     default=DTS_ROOT, help=DTS_HELP,
                     check=dict(name="USE_DTS_STC", default=True,
                                tip="Include the DTS (closest Combined "
                                    "profile) in the STC figures"),
                     tip="Folder searched (sub-folders included) for the "
                         "preprocessed DTS files: the closest Combined DTS "
                         "profile of each STC profile is taken from them"),
                dict(name="LEXPLORE_FOLDER", label="LéXPLORE folder",
                     kind="dir", default=LEXPLORE_ROOT,
                     help=CHAIN_FOLDER_HELP,
                     check=dict(name="USE_LEXPLORE_STC", default=True,
                                tip="Include the LéXPLORE chain (closest "
                                    "profile, when there is one at that "
                                    "time) in the STC figures"),
                     tip="Folder of the LéXPLORE thermistor-chain files"),
                dict(name="STC_PROFILES",
                     label="Individual STC profiles",
                     kind="stc_profiles", root_field="STC_FOLDER",
                     dts_field="DTS_FOLDER", chain_field="LEXPLORE_FOLDER",
                     default=None,
                     tip="Profiles compared with the DTS; their start "
                         "times are marked on the sound-speed maps"),
                dict(name="STC_AT_LEXPLORE_ONLY",
                     label="Only STC profiles at LéXPLORE", kind="bool",
                     default=False,
                     help=("When ticked, Load and plot uses only the STC "
                           "profiles ticked that were taken at LéXPLORE: "
                           "their position (.vp2 file) lies within the "
                           "'LéXPLORE radius' of Advanced › Physical "
                           "parameters (100 m by default) — see the column "
                           "Distance. The others, and the profiles without "
                           "a position, are left out (listed in the "
                           "log).")),
                dict(kind="note", label="DTS: the Combined channel, the "
                     "profile closest in time to the start of each STC "
                     "profile, searched in all the preprocessed files of "
                     "the DTS folder. LéXPLORE chain: its closest profile, "
                     "when there is one at that time."),
                dict(name="USE_T", label="Temperature T", kind="bool",
                     default=True),
                dict(kind="note", label="T: the DTS temperature (off: the "
                     "constant reference temperature of the physical "
                     "parameters)"),
                dict(name="USE_P", label="Pressure P", kind="bool",
                     default=True),
                dict(kind="note", label="P = ρ̄ g z: mean density of the "
                     "profiles (equation of state, or the fixed density) "
                     "times g times the depth"),
                dict(name="USE_S", label="Salinity S", kind="bool",
                     default=True),
                dict(kind="note", label="S: the salinity of the physical "
                     "parameters (0 PSU by default)"),
                dict(name="_run_sound", label="Load and plot",
                     kind="button", step="@sound_all",
                     tip="Read the STC profiles ticked and their closest "
                         "DTS profiles and draw every figure: map of the "
                         "positions, one figure per STC profile "
                         "(temperature and sound speed vs depth) and the "
                         "sound-speed map of the Combined channel of the "
                         "data loaded in Load preprocessed data (drawn "
                         "when data are loaded)"),
            ]),
            ("Resampling and display", [
                dict(name="IS_STC_RESAMPLING",
                     label="Resample over depth", kind="bool",
                     default=False,
                     help=("Averages the STC and DTS profiles of the STC "
                           "figures over depth windows of 'Window size', "
                           "centred every 'Window step' (auto = the window "
                           "size: windows side by side), before they are "
                           "drawn and compared. The sound-speed maps are "
                           "not resampled.")),
                dict(name="STC_WINDOW", label="Window size", kind="float",
                     unit="m", default=1.0),
                dict(name="STC_WINDOW_STEP", follows="STC_WINDOW",
                     label="Window step", kind="float", unit="m",
                     optional=True, default=None,
                     tip="auto = the window size (windows side by side)"),
                dict(name="RMS_WINDOW", label="RMS window", kind="float",
                     unit="m", default=2.0,
                     help=("Depth window of the RMS curves below each STC "
                           "figure: the difference between two profiles "
                           "(the STC measured one being the reference) is "
                           "squared, averaged over "
                           "windows of this size side by side, and its "
                           "square root plotted at the window centre.")),
                dict(name="IS_SHADING", label="Smooth shading", kind="bool",
                     default=False,
                     tip="Off: plain cells ('nearest'); on: the kind below"),
                dict(name="SHADING", label="Shading kind", kind="choice",
                     choices=["gouraud", "nearest", "auto"],
                     default="gouraud"),
                dict(name="CMAP", label="Colour map", kind="choice",
                     choices=COLOUR_MAPS, default="default"),
                dict(name="_update_sound", label="Update", kind="button",
                     step="@update_sound",
                     tip="Draw again the figures already made with these "
                         "options"),
            ]),
        ],
    ),
]

MENUS = [("&Preprocessing", PREPROCESSING), ("&Data analysis", ANALYSIS),
         ("&Advanced", ADVANCED)]
