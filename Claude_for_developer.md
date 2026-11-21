# Claude_for_developer.md

This file gives an AI assistant (Claude or another), or a person, what they need to **understand how the DTS GUI is built** and to **write Python scripts for *Advanced › Python script***. Read it whole before writing a script or changing the GUI.

- Part A describes the GUI: its files, its window, its data model and its rules.
- Part B explains how a step works, from the description of its panel to its figures.
- Part C explains how to write scripts: the names given to a script, the library functions and the examples.
- Part D explains how to change the GUI itself, and how to test.

Version of the GUI described: **3.39** (21.11.2026).

---------------------------------------------------------------------------

## A. The GUI

### A.1 What it is

The GUI is a desktop application written with **PySide6 (Qt 6) and matplotlib**. It processes records of a **Silixa XT-DTS** (distributed temperature sensing) fibre, deployed as a U-shaped cable in Lake Geneva (MIRAGE 2026). It has two parts:

- **Preprocessing.** It reads the raw WITSML XML files of the XT, folds the U-shaped cable at its mirror point, calibrates the depth (against the LéXPLORE thermistor chain, or by hand), and saves the product `DTS_preprocessed.nc`.
- **Data analysis.** It loads that product and runs the analyses: isotherms, Brunt–Väisälä frequency, multi-layer decomposition, spectra in time and in depth, 2D FFT, gradient maps, staircases, report. It also has **Advanced** tools: sound-speed maps, Python scripts, physical parameters and Save variables.

Start it with `python dts_gui.py` (conda environment `dts`: python ≥ 3.9, pyside6, numpy, pandas, matplotlib, netcdf4, scipy, h5py, tzdata).

**Time convention: every time entered or shown is UTC.** The only exception is the reference *local* time of the clock correction (Preprocessing › Load raw data).

### A.2 The files

| File | Content | Qt? |
|---|---|---|
| `dts_gui.py` | The main window: menus, panels, running of the steps in a worker thread, settings, time windows, individual profiles, scripts (`script_namespace`, `add_advanced_step`) | yes |
| `gui_sections.py` | The **description of every step**: its panel (boxes and fields), its menu, its figures (`PREPROCESSING`, `ANALYSIS`, `ADVANCED`, `MENUS`); `copy_section` | no |
| `gui_widgets.py` | The input widgets made from the field descriptions (`make_field`), the panel of a step (`ParameterPanel`), the result area (`FigurePanel`) | yes |
| `dts_steps.py` | **The steps**: one function `step(session, p)` per step, the registry `STEPS`, the session (`Session`), the helpers (time windows, layers, profiles, chain) | no |
| `dts_core.py` | **The calculation library**: reading the XT files, folding, calibration, LéXPLORE, equation of state, N, gradients, FFT and spectra, isotherms, layers, sound speed, STC profiles; the physical parameters (`PHYSICS`) | no |
| `gui_figures.py` | **The figures** of the steps: functions returning matplotlib `Figure`s | no |
| `gui_script.py` | The panel of *Advanced › Python script* (`ScriptBox`) and the template of a new script | yes |
| `gui_variables.py` | *View all variables* and *Advanced › Save variables* (grouped by step, search, details) | yes |
| `gui_export.py` | The writer of npz / NetCDF / HDF5 / txt / csv / MATLAB files (Save data, Save variables) | no |
| `gui_physics.py` | The window *Advanced › Physical parameters* | yes |
| `gui_help.py` | The texts of the Help menu | no |
| `channel_names.py` | The names of the channels (CH1, CH2, Combined, …) | no |
| `default_paths.py`, `default_paths.ini` | The default folders (data, LéXPLORE, STC, DTS); the `.ini` file is personal and not published | no |
| `Example_Scripts/` | The example scripts of Part C | — |
| `README.md`, `GUI_MAP.md` | The user documentation (with the version history) and the map of the code | — |

The code follows one rule of separation:

- **calculations** go in `dts_core.py`;
- **steps** (data in, results and figures out) go in `dts_steps.py`;
- **figures** go in `gui_figures.py`;
- **panels** are *described* in `gui_sections.py`;
- **Qt** lives only in `dts_gui.py` and the `gui_*` widget modules.

The steps run without Qt, in a worker thread, so they can also run from a plain Python session.

### A.3 The window

- **Menus**: *File* (Reset all, Quit), *Preprocessing*, *Data analysis*, *Advanced* (Physical parameters…, Save variables…, Sound speed maps, Python script, then the items added by scripts), *View* (log, View all variables) and *Help*. The menus are repeated as buttons at the top of the window.
- **Left**: the panel of the step chosen in the menus. It is a `ParameterPanel` built from the step's description (`gui_sections`). Above it are the step's title, its state, and **Previous** / **Next**.
- **Right**: the result area, a `FigurePanel`. One result area is shared by all the steps of a menu (Preprocessing, Data analysis, Advanced). It has the figures as tabs, and on its right the **figure list** grouped by step, with one tick box per figure (shown or hidden) and a right-click menu (Show / Hide, Focus, Save data…). By default only the figures of the current step are shown.
- **Bottom**: the **log**. Everything a step prints goes there; `print` in a step or a script is enough.
- Figures are only redrawn by **Run**, by **Update plot**, or by the tick of an individual profile.

### A.4 The data model

All the results live in **one session**, `gui.session` (a `dts_steps.Session`):

| Attribute | Content |
|---|---|
| `session.data` | **The variables**: a dict (name → value) shared by all the steps. It is a `TrackedData`: while a step runs, the names it reads or writes are recorded |
| `session.figures` | step → `[(title, Figure)]`, the figures of the last run of each step |
| `session.params_used` | step → the inputs of its last run |
| `session.origin` | variable → the step that first created it (this sets the group in Save variables) |
| `session.variables_used` | figure owner → (variables read or written, step); used by *Save data* of a figure |

The main variables are listed below. The full list, with a description of each, is in `gui_variables.DESCRIPTIONS`, and in the GUI under *View › View all variables*.

**Preprocessing** (names without a prefix):

- `DATA_DTS_RAW`, `DATA_DTS_RAW_TRUNCATED`: the raw profiles by channel;
- `TIME`, `Z`, `T_MATRIX_down/up/mean`: the folded U-shaped record (concatenation);
- `VERTICAL_OFFSET`, `Z_SHIFT`, `T_SHIFT`: the calibration;
- `T_USHAPED_CALIBRATED`: the saved product;
- `DATA_LEXPLORE`: the chain, as `time`, `depth`, `temperature`.

**Analysis** (prefix `A_`), filled by *Load data and analysis settings* (steps `ana.0`, `ana.0.1`):

| Variable | Content |
|---|---|
| `A_TIME[channel]` | `(nt,)` numpy `datetime64[ms]`, UTC |
| `A_Z[channel]` | `(nz,)` depth below the water surface (m), increasing |
| `A_T[channel]` | `(nz, nt)` calibrated temperature (°C), NaN where missing |
| `A_LEXPLORE` | dict `time` (nt,), `depth` (nz,), `temperature` (nz, nt) of the LéXPLORE chain over the record (empty dict when none); `A_IS_LEXPLORE` True when it is there |
| `A_RESOLUTION[channel]` | instrument temperature resolution (K) |
| `A_DZ` | depth spacing (m) |
| `A_MAX_DEPTH` | deepest depth (m) |
| `A_PROFILE_TIMES` | the individual profiles `[(label, datetime64)]` (shared list) |
| `A_WINDOWS` | the time windows `[(label, start, end)]` |

The channels are named like `CH1`, `CH2` and `Combined` (the profile-by-profile mean of two channels), or by their XT names (`channel 1`, `channel 3`, `mean`), depending on the product.

Each analysis step adds its own results, for example:

- `A_N_PROFILES`, `A_N_MEAN`, `A_N_STD`, `A_N_DEPTH`, `A_N_TIME`: Brunt–Väisälä;
- `A_ISOTHERM`: isotherm depth;
- `A_LAYERS`: interfaces Z1, Z2;
- `A_FFT_DEPTH`: FFT over time at each depth;
- `A_KZ_SPECTRA`: vertical spectra;
- `A_FFT2`: 2D FFT;
- `A_GRADIENT`, `A_GRADIENT_PROFILES`: gradient maps;
- `A_STAIRCASES`, `A_SEISMOGRAM`: staircases.

Scripts keep theirs in `SCRIPT_RESULTS[script]` and log their runs in `SCRIPT_RUNS`.

**Physical parameters** (gravity, equation of state, latitude, lake width, …) are in `dts_core.PHYSICS`. Read one with `core.physics("GRAVITY")`. Change them only through *Advanced › Physical parameters* (or `core.set_physics`). **Every physical constant used by a calculation must be an entry of `dts_core.PHYSICAL_PARAMETERS`.**

### A.5 Coding rules

- **Simple, explicit English** in the texts, tool tips and docs, with **units** everywhere (m, K, K/m, Hz, cpm, UTC).
- **Explicit variable names**: `temperature`, `depth_grid`, `channel`; no `d`, `m`, `sw`.
- **No plotting code in `dts_core.py`.** Figures go in `gui_figures.py` (or in the script).
- **A step never changes the data of another step in place.** It writes new variables. Time windows, layers and individual profiles are applied by the wrappers of B.4, which restore the whole record afterwards.
- Errors of the user's inputs: `raise steps.StepError("clear message")`. It is shown in the log without a traceback.
- Nothing is redrawn automatically when an input changes: the user presses **Run** or **Update plot**.

---------------------------------------------------------------------------

## B. How a step works

### B.1 The description of a step (`gui_sections.py`)

A menu item (a *section*) is a dict:

```python
dict(
    id="ana.4.2.6",             # unique id (also the step run by default)
    number="4.2.6", parent=None,
    title="Temperature-gradient maps",            # menu and title
    description="...",                            # shown above the figures
    actions=["ana.4.2.6", ...],  # optional: several steps in one panel
    hide_run=True,               # no 'Run All' button at the bottom
    params=[                     # the boxes of the panel, in order
        ("Channels", [field, field, ...]),
        ("Individual profiles", [...]),
        display_group("ana.4.2.6"),               # Display box + Update plot
    ],
    figures=[("ana.4.2.6", "Maps", True)],        # (owner, title, shown)
)
```

A **field** is a dict with these keys:

- `name`: the key in the step's inputs `p`;
- `label`;
- `kind`;
- `default`;
- `tip` (tool tip) or `help` (a (?) button), optionally;
- extras that depend on the kind.

The kinds are:

| Kind | Widget | Value in `p` |
|---|---|---|
| `float`, `int` (`unit`, `optional`, `follows`) | spin box (`optional`: an *auto* box, value `None`) | number or None |
| `bool` | check box | True / False |
| `choice` (`choices`) | drop-down | the text chosen |
| `channels` (`choices="analysis"` or `"pre"`) | one tick box per channel | list of names |
| `channel` | one channel | name |
| `window` (`profiles=True`) | *Time window*: `Whole record`, `W1: start → end`, … (and `P1 @ time`) | the text |
| `layer` | *Layer*: `Whole column` or a layer of the multi-layer decomposition | the text |
| `timetable` / `windows` / `named_windows` | table of rows, each with a tick box (active or not) | list of the **active** rows (tuples of texts) |
| `dir`, `dirs`, `text`, `datetime`, `profile_time`, `radio`, … | path, text, date, … | text |
| `button` (`step` or `steps`) | a button that runs these steps; `step="@update:<id>"` = Update plot, `"@…"` = an action of the GUI | — |
| `toggle` | an on/off button (e.g. click-to-select on a map) | — |
| `note`, `heading` | text only | — |

Helpers that build common fields:

- `analysis_channels(chain, layer, profiles)`: the Channels box (channels, LéXPLORE chain, Time window, Layer);
- `window_field()` and `layer_field()`;
- `display_group(step)`: shading, colour map and **Update plot**;
- `update_group(step)`;
- `spectrum_fields(prefix)`: quantity, detrend, window, spectrum.

`copy_section(sections, source_id, new_id, title)` copies a description for a new id. It renames every step named in its buttons (`source_id` → `new_id`, `source_id.replot` → `new_id.replot`, `@update:source_id` → `@update:new_id`).

### B.2 The function of a step (`dts_steps.py`)

```python
def ana_4_2_6(session, p):
    """Raw dT/dz maps and the individual profiles of the gradient."""
    S = session.data
    ...                                   # read S["A_T"], p["CHANNELS"], ...
    S["A_GRADIENT"] = {...}               # write the results
    return [("Maps", figure), ("Individual profiles", figure2)]
```

- `p` holds the values of the panel's fields (B.1). `session.data` holds the variables (A.4).
- The function returns the figures as `[(tab title, matplotlib Figure)]`. The titles must match the `figures` of the section (B.1).
- `print` writes to the log. Every printed line is also a stop point for the **Interrupt** button.
- Helpers:
  - `_records(session, p)` returns `[(name, time, depth, T)]` of the channels ticked, plus the chain when `p["INCLUDE_CHAIN"]`;
  - `selected(p, available)`;
  - `instants(rows)` turns table rows into `[(label, datetime64)]`;
  - `utc(text)`, `stamp(t)`;
  - `shading(p)`.

### B.3 The registry (`dts_steps.STEPS`)

```python
STEPS = {"ana.4.2.6": (ana_4_2_6, ["ana.0.1"]), ...}  # key: (function, requires)
```

- `requires` lists the steps that must have run before. **Run** first runs the missing ones.
- Each analysis step `k` also gets an *Update plot* step `k.replot`: the same function, marked display only (`DISPLAY_ONLY`), so the later steps are not marked outdated.
- `FIGURE_OWNER[k.replot] = k`: the figures of a replot replace those of `k`.
- `register_step(key, function, requires)` does all this for a new step (used by `add_advanced_step`).

### B.4 The wrappers (time window, layer, individual profile, chain, colour map)

At import, the analysis steps are wrapped in this order:

1. **`_with_chain(function, key)`**, for the steps of `CHAIN_AS_CHANNEL` (`ana.4.1.2`, `ana.4.2.5`, `ana.4.2.6`, `ana.4.2.9`). When the chain is ticked, it is interpolated onto a uniform 1 m depth grid (`chain_on_grid`) and added as one more channel, `"LeXPLORE chain"`.
2. **`_with_colour_map(function)`**, for every analysis step:
   - it reads `p["TIME_WINDOW"]`:
     - `W1: start → end` cuts `A_TIME`, `A_Z`, `A_T` and `A_LEXPLORE` to the window (`windowed_data`);
     - `P1 @ time` keeps only the profile closest in time (`profile_data`);
   - it reads `p["LAYER"]` and cuts them to the rows of the layer (`layered_data`);
   - it runs the step on these data, then **restores the whole record**;
   - it adds the window to the figure titles and applies the colour map `p["CMAP"]`.

So `steps.STEPS["ana.4.2.6"][0]` is the **complete** step, exactly as the GUI runs it. The bare function `steps.ana_4_2_6` lacks the window, layer and chain handling.

### B.5 How the GUI runs a step

1. **Run** (or Update plot) calls `gui.run_steps([...])`. It adds the missing required steps and starts `start(jobs)`.
2. For each job, the inputs are read from the panel (`ParameterPanel.values(step)`), and a `Worker` (`QThread`) runs `STEPS[key][0](session, p)`. The output of `print` goes to the log. The variables read and written are recorded.
3. **At the end**, `on_step_done` runs:
   - the step is marked done, and the steps that depend on it are marked outdated;
   - the figures go to the result area (`FigurePanel.set_figures(owner, figures)`);
   - the time windows are shaded on the time maps;
   - the lists of the panels (channels, layers, windows) are updated.

### B.6 Sessions

`gui.journal` holds every analysis step and every script run, in the order of their last run, each step with its inputs (`record_run`, `record_script`; Load data clears the steps). *Data analysis › Save session…* (`session_state`) writes it to JSON with the inputs of every analysis and Advanced panel and the physical parameters. *Load session…* (`SessionDialog`, `execute_session`) performs the journal again, one entry at a time: a step through the normal queue (its saved inputs), a script through `script_box.execute`, after which the inputs of the items it added are applied.

### B.7 Shared lists

- **Individual profiles**: one list shared by the tables named in `gui.PROFILE_TABLES` (Load data and analysis settings, Multi-layer decomposition, wavenumber domain, gradient maps, staircases). A change in one table is copied to the others.
- **Click on a map to add a profile**: `gui.PROFILE_PICKERS` maps a figure owner to (panel, toggle, table).
- **Time windows**: the table of *Load data and analysis settings*. Only the ticked rows appear in the *Time window* lists.
- **Channels**: ticking a channel in one step ticks it in every step.

---------------------------------------------------------------------------

## C. Writing scripts for *Advanced › Python script*

### C.1 How a script is run

1. The user chooses a `.py` file in *Advanced › Python script*. The list holds the scripts of `Example_Scripts/` and those opened with **Open…**; **New…** writes a template.
2. The user presses **Execute**. The file is **read again** and executed with `exec` **inside the GUI's process**, in the main (Qt) thread, with the names of C.2.
3. `print` goes to the panel's *Output* and to the log. An exception is shown with its traceback, and the GUI goes on.
4. At the end:
   - what the script put in `results` is kept in `SCRIPT_RESULTS[<script name>]` (in *Save variables* under *Advanced › Python script*);
   - the figures made with `figure()` or `show()` appear in the result area, titled `<script>: <title>`;
   - the run is logged in `SCRIPT_RUNS`.
5. Executing the script again replaces its results and its figures.

The script runs in the GUI thread, so the GUI waits while it runs: use numpy on whole arrays, not loops over profiles in pure Python.

### C.2 The names given to a script

| Name | What |
|---|---|
| `session`, `S` | the session and its variables `S = session.data` (A.4) |
| `np` | numpy |
| `core` | `dts_core`: the calculations (C.3) |
| `steps` | `dts_steps`: the steps, `STEPS`, the helpers (B.2–B.4) |
| `figs` | `gui_figures`: the figure functions of the steps |
| `params(step)` | the **current inputs of a step's panel**, e.g. `params("ana.4.2.6")` → `{"CHANNELS": [...], "TIME_WINDOW": "Whole record", ...}` (the panel is created if needed) |
| `run_step(step, p=None)` | runs the GUI's own (wrapped) function of a step on the data in memory, with `p` or `params(step)`, and returns its figures. Its variables are written to `S` as when the step is run, but the step is not marked done |
| `records(p)` | `[(name, time, depth, T)]` of the channels ticked in `p` (+ the chain when `p["INCLUDE_CHAIN"]`), whole record |
| `results` | **a dict to fill** with what the script produces: arrays, numbers, strings, dicts of them |
| `figure(title, figsize=(10, 6))` | a new matplotlib `Figure`, shown once the script ends |
| `show(title, fig)` | show a figure made elsewhere (e.g. by `figs.gradient_maps`) |
| `log(text)` | a line in the log |
| `gui` | the main window: `gui.show_section(id)`, `gui.page(id)`, `gui.write_log(text)`, `gui.run_steps([...])`, `gui.section_by_id`, … |
| `add_advanced_step(section, step_functions, profile_table=None, profile_picker=None)` | **adds an item to the Advanced menu** (C.5) |
| `copy_section(source_id, new_id, title)` | a copy of the panel description of a step for a new id (B.1) |
| `QtWidgets`, `QtCore`, `QtGui` | Qt (PySide6) |

### C.3 Useful library functions

| Function | What |
|---|---|
| `core.vertical_gradient(depth, T, width=None, step=None)` | (depth grid, dT/dz (nz, nt)) by centred differences; with `width` (m), T is first averaged over depth windows centred every `step` |
| `core.brunt_vaisala(depth, T, width, step)` | (depth, N (Hz), N²) |
| `core.density(T)`, `core.thermal_expansion(T)`, `core.physics(name)` | equation of state and physical parameters |
| `core.isotherm_depth(depth, T, T_iso)` | (depth (nt,), uncertainty) |
| `core.spectrum_along(x, step, axis, detrend, window, kind)` | one-sided spectrum: FFT amplitude 2\|X\|/Σw, or PSD 2\|X\|²/(fs Σw²), after detrend (`constant`/`linear`) and window (`none`, `Hann`, `Hamming`, `Blackman`, `Tukey (25 %)`) |
| `core.fft_vertical(z, T, detrend, window, kind)` | (k (cpm), spectrum (nk, nt)) of every profile |
| `core.fft2_matrix(time, z, T, detrend=, window=, kind=)` | 2D FFT (frequency, k_z, amplitude) |
| `core.time_mean_std(M)`, `core.smooth_profile(...)` | statistics and smoothing |
| `steps.parse_window(text)`, `steps.windowed_data(S, window)` | a *Time window* text → (label, t0, t1), and the data cut to it |
| `steps.parse_profile_choice(text)`, `steps.profile_data(S, label, t)` | an individual profile `P1 @ time`, and the data reduced to it |
| `steps.layered_data(S, label, window)` | the data cut to a layer |
| `steps.chain_on_grid(chain)` | the chain on a uniform 1 m grid |
| `steps.instants(rows)`, `steps.selected(p, names)`, `steps.utc(text)`, `steps.stamp(t)` | helpers |
| `figs.gradient_maps`, `figs.gradient_profiles`, `figs.n_mean_profiles`, `figs.n_maps`, `figs.isotherm_depth`, `figs.fft_depth_maps`, `figs.vertical_fft_maps`, … | the figures of the steps (see `grep "^def " gui_figures.py`) |

To list everything: `grep -n "^def " dts_core.py dts_steps.py gui_figures.py`.

### C.4 The examples (`Example_Scripts/`)

| Script | Shows |
|---|---|
| `reproduce_temperature_gradient.py` | **reproduces the results of *Temperature-gradient maps* exactly**, step by step with the library (C.6). It reads the panel's inputs (`params`), selects the data like the wrappers (time window, individual profile, layer, chain), computes dT/dz with `core.vertical_gradient`, draws the two figures with `figs`, then runs the GUI's step (`run_step`) and prints the largest difference (0 K/m) |
| `temperature_gradient_again.py` | **adds an item *Temperature Gradient again* to the Advanced menu**: an exact copy of the window of *Temperature-gradient maps*. It uses `copy_section` + `add_advanced_step`, with the GUI's own function `steps.STEPS["ana.4.2.6"][0]` (C.5) |

### C.5 Adding an item to the Advanced menu

```python
section = copy_section("ana.4.2.6", "adv.my_step", "My step")
# or a new description: dict(id="adv.my_step", title="My step",
#   params=[("Inputs", [dict(name="T_ISO", label="Isotherm", kind="float",
#   unit="°C", default=10.0), dict(name="_run", label="Run",
#   kind="button", step="adv.my_step")]), display_group("adv.my_step")],
#   figures=[("adv.my_step", "My figure", True)])

def my_step(session, p):          # like every step (B.2)
    S = session.data
    ...
    return [("My figure", fig)]

add_advanced_step(section, {"adv.my_step": (my_step, ["ana.0.1"])},
                  profile_table=None,    # e.g. "GRADIENT_PROFILES"
                  profile_picker=None)   # e.g. ("GRADIENT_SELECT", "GRADIENT_PROFILES")
gui.show_section("adv.my_step")
```

`add_advanced_step` does the following:

- registers the steps (with their Update-plot step);
- adds the panel to the GUI;
- adds the item at the end of the Advanced menu;
- lists its figures under its title;
- with `profile_table`, makes its profile table part of the shared list of profiles;
- with `profile_picker`, lets a click on its maps add a profile.

Executing the script again replaces the item.

The new step behaves like the steps of the GUI: Run, Update plot, Interrupt, the log, the figure list, Save data, and Save variables (its variables are grouped under its title).

To keep the time-window, layer and colour-map handling of B.4 in a new function, wrap it: `steps._with_colour_map(my_step)`.

The item exists until the GUI is closed. Settings files keep its inputs, but they are applied only once the script has been executed again.

### C.6 Recipe: reproduce a step

1. Read the step's inputs: `p = params("<step>")`.
2. Select the data as B.4 does: `parse_window` / `windowed_data`, `parse_profile_choice` / `profile_data`, `layered_data`, and `chain_on_grid` for the steps of `CHAIN_AS_CHANNEL`.
3. Compute with the same `core` functions and the same inputs as the step's function in `dts_steps.py`. Read it first: `grep -n "^def ana_4_2_6" -A40 dts_steps.py`.
4. Put the arrays in `results`, and draw with the same `figs` function and `show(...)`.
5. Check: `run_step("<step>", p)`, then compare with the variable the step writes (`np.nanmax(np.abs(a - b))`, plus the same NaN).

### C.7 Good practice for scripts

- **Parameters at the top, in capitals**, each with a comment (e.g. `CHANNEL = "Combined"`, `T_ISO = 10.0  # degC`).
- **A docstring** at the top: what the script does, what must be done before (e.g. *Load data and analysis settings*), and what it produces.
- **Check the data and stop with a clear message**: `if "A_T" not in S: raise RuntimeError("load the data first: Data analysis > Load data and analysis settings")`.
- **Use the stored results** of the steps (`S["A_N_MEAN"]`, `S["A_LAYERS"]`, …) instead of computing them again.
- **Do not change** `S["A_T"]`, `S["A_TIME"]` or `S["A_Z"]` in place. Make copies, or write new names in `results`.
- **Use explicit names in `results`**, with units in the name when useful: `dTdz_CH1`, `depth_CH1`, `N_mean_Hz`.
- **One `figure(title)` per figure.** Do not call `plt.show()`, and do not use pyplot: use `Figure` objects.
- **Times are UTC**: `np.datetime64("2026-11-01T12:00", "ms")` or `steps.utc("2026-11-01 12:00:00")`.

### C.8 Helping a user with a script (for an AI assistant)

1. Find out what the user wants: which quantity, which channels, which time window or profiles, which layer, and which output (figure, numbers, file, new menu item).
2. Start from the closest example of `Example_Scripts/`, and keep its structure: docstring, parameters at the top, checks, results, figures.
3. Use only the names of C.2 and the functions of C.3. When unsure, check the names in the code (`grep -n "^def " dts_core.py dts_steps.py gui_figures.py`) and the variables in *View › View all variables*.
4. To reproduce or extend a step, read its function in `dts_steps.py` and its description in `gui_sections.py` first, and follow C.6.
5. Explain how to run it: *Advanced › Python script* → **Open…** (or put the file in `Example_Scripts/`) → **Execute**. The output, the results and the figures appear in the panel and on the right.

---------------------------------------------------------------------------

## D. Changing the GUI, and testing

### D.1 Adding a step to the GUI itself

1. **The function** in `dts_steps.py` (B.2), with its calculations in `dts_core.py` and its figures in `gui_figures.py`.
2. **The registry**: `STEPS["<id>"] = (function, [requires])`. If the step needs the chain as a channel, add it to `CHAIN_AS_CHANNEL`. The wrappers and the `.replot` step are added automatically for `ana.*` keys.
3. **The description** in `gui_sections.py` (B.1), in `PREPROCESSING`, `ANALYSIS` or `ADVANCED`, with its `figures`.
4. **The variables**: a description of each new variable in `gui_variables.DESCRIPTIONS`.
5. If needed: `PROFILE_TABLES` / `PROFILE_PICKERS` (individual profiles), `FOCUS_FIGURE` (the figure brought forward), `FIGURE_OWNER` (actions whose figures belong to another step).
6. **Docs**: the Help text (`gui_help.py`), a new row on top of the version history of `README.md`, `VERSION` in `dts_gui.py`, and `GUI_MAP.md`.

### D.2 Testing

- **Offscreen**: `QT_QPA_PLATFORM=offscreen python test.py`. A test builds `dts_gui.MainWindow()`, fills the panels (`w.page(id)[0].fields[name].set_value(...)`), runs `w.run_jobs([...])`, and processes events until `w.worker is None`. It then checks the variables (`w.session.data`), the figures (`w.shared_panels["Data analysis"].results`) and the log (no `Traceback`).
- **A script**: `w.show_section("adv.script"); w.script_box.execute(path)`, then read `w.script_box.output.toPlainText()` and `w.session.data["SCRIPT_RESULTS"]`.
- `python -m pyflakes dts_gui.py dts_steps.py dts_core.py gui_*.py`.
- **Check the numbers**. For example: a sine wave of amplitude A gives an FFT amplitude A at any window; a reproduced step gives a difference of 0.
