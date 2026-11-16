# DTS GUI — user guide

Version 3.19 (16 November 2026). Desktop application for the preprocessing
and the analysis of Silixa XT-DTS records (MIRAGE campaign, Lake Geneva).

## 1. Purpose

The application carries out, from one window, the two stages of the DTS
work that were done until now in the notebooks `DTS_preprocessing.ipynb`
and `DTS_analysis.ipynb`:

1. the **preprocessing**: the raw XML files of one configuration are read,
   the clock is corrected to UTC, the U-shaped cable is folded, the depth is
   calibrated (against the LéXPLORE chain, or by hand) and the product
   `DTS_preprocessed.nc` is written;
2. the **analysis**: one or several preprocessed products are loaded and
   studied (stratification, isotherms, frequency and wavenumber spectra,
   three-layer decomposition, staircases, reports).

The application is independent of the notebooks. It carries its own
computation library (`dts_core.py`), which was copied from `DTS_XT_lib.py`
on 13.11.2026 and now evolves with the application only. The results were
checked against the notebooks on the field data: the mirror distance, the
calibration shifts, the scatter fits, the Brunt–Väisälä maxima, the layer
interfaces and the isotherm spectra are identical.

## 2. Installation and start

The application needs Python 3.9 or newer and the modules listed in
`requirements.txt`:

```
pip install -r requirements.txt
python dts_gui.py
```

The GUI runs on macOS, Linux and Windows. The module `tzdata` provides the time-zone database used to convert the reference local time of the clock correction to UTC: macOS and Linux have it in the system, Windows does not, so it is in `requirements.txt` for every system.

All the files of this folder must stay together. The module `netCDF4` is needed to read the LéXPLORE chain and to write the product: when it is missing in the Python that runs the GUI, the log says so at start, and the chain is reported as not available.

### Default folders (`default_paths.ini`)

The folder fields of the GUI (XT temperature folder, LéXPLORE chain
folder, STC folder, DTS folder) start from the paths written in
`default_paths.ini`, next to `dts_gui.py`. This file describes your own
data structure, so it is personal: it is **not** in the git repository
(it is listed in `.gitignore`). The repository holds a blank copy,
`default_paths_template.ini`.

To set your default folders, once:

1. In the GUI folder, copy the template under the name the GUI reads:

   ```
   cp default_paths_template.ini default_paths.ini
   ```

   (on Windows: `copy default_paths_template.ini default_paths.ini`).
2. Open `default_paths.ini` in a text editor and enter, after each `=`,
   the **full path** of the folder on your computer, without quotes
   (spaces are fine, `~` stands for your home folder):

   | Key | Folder |
   |---|---|
   | `xt_temperature` | the XT temperature folder: one sub-folder per configuration of the Silixa XT (raw WITSML files), with `DTS_preprocessed.nc` in each after preprocessing; used by *Load raw data* and *Load preprocessed data* |
   | `lexplore` | the LéXPLORE thermistor-chain files (Datalakes Level-2 NetCDF, `L2_*.nc`) |
   | `stc` | the STC profiler files (SWiFT SVP `.csv` and `.vp2`) and the lake outline `Lake_Geneva_outline.geojson`; used by *Advanced › Sound speed maps* |
   | `dts` | the folder searched (sub-folders included) for the preprocessed DTS files compared with the STC profiles |

   Leave a value empty when you do not have that data.
3. Start (or restart) the GUI: the log says at start whether
   `default_paths.ini` was found. A key left empty, or a path to a folder
   that does not exist on this computer, is ignored (that field starts
   empty) and named in the log, so a typing mistake shows at once.

Without `default_paths.ini` the GUI works the same; its folder fields just
start empty, and every folder can always be chosen with the `…` button of
its field.

## 3. Time convention

**Every time entered in the application is UTC**, with one exception: the
reference time of the clock correction (Preprocessing › Load Data), which is read
on a local watch and is therefore given in local Lausanne time. Each time
field shows its time zone next to its label. All the time axes of the
figures are in UTC.

Note: in the preprocessing notebook the calibration windows `TIME_WINDOWS`
were given in local time; in the application they are in UTC (for example,
08.11 12:00 local time in winter is 08.11 11:00 UTC).

## 4. Organisation of the window

- **Menus.** The drop-down menus (`File`, `Preprocessing`, `Data
  analysis`, `View`, `Help`) are in the menu bar and, repeated, in a
  bar at the top of the window (on macOS the menu bar sits at the top of
  the screen, away from the window). `Preprocessing` and `Data analysis`
  contain one item per
  section or subsection of the former notebooks, named without number. A section with
  subsections opens a sub-menu. A tick (✓) marks the steps already run, a
  half disc (◐) a panel whose steps are only partly run, a warning sign (⚠)
  the steps whose results are outdated.
- **Left panel.** All the inputs of the current step, in boxes, with the
  **Run** button. A panel that holds several steps (Preprocessing › Load
  Data) has one button per box (*Load*, *Run*, *Concatenate*, *Update
  plot*) and a **Run All** button at the bottom, which runs its steps in
  order. *Reset* restores the default values. Channels are chosen
  with check boxes when several channels can be used, and with radio
  buttons when the step studies one channel. The channel lists follow the
  data: the channels of the preprocessing are the channel folders of the
  chosen configuration; those of the analysis are filled by *Load data*
  (Analysis › Load Data).
- **Right panel.** A short description of the step, one tab per result
  (figure or table), and on its right the **list of the figures** with tick
  boxes, grouped by step; a **green circle** on the right of a figure means it is ready to be displayed, a **red circle** that it is not available yet (its step has not run). Ticked figures are shown
  as tabs. Under the list of the preprocessing, the box **Display of the maps** holds the smooth shading (on/off and kind) and the colour map (seismic, coolwarm, RdBu_r, viridis, plasma, inferno, magma, cividis, turbo, gray); the figures are shown or hidden as soon as their boxes are ticked or unticked; **Update plots** redraws every map of the preprocessing (T(z, time) maps, calibrated maps) with these options, without computing the data again; the **x** of a tab closes it
  (and unticks it). By default the preprocessing shows only the
  Configuration, the T(z, time) maps and the First profile of the depth
  calibration; the other figures are computed all the same and can be
  ticked at any time. In the analysis, every figure is shown for now (the
  default figures will be chosen later). Each figure has the usual matplotlib tool bar (zoom,
  pan, save). Each step replaces only its own tabs. **The steps of a menu
  share one set of tabs** (one set for the preprocessing, one for the
  analysis): all the results stay open when moving from one step to
  another, in the order of the steps, the figure list groups them by step,
  and the tabs of the chosen step are brought forward. In the figure list,
  the tick box *All figures* (top) and the tick box of each step header tick
  or untick every figure below them (shown partly ticked when only some
  are). A figure is shown or hidden as soon as its box is ticked or
  unticked (no button to press). A tab whose result is
  outdated carries ⚠ in its title.
- **Bottom.** The log: every message of the computation appears here.
- **Top line.** The menu and the name of the current panel (for example
  *Preprocessing › Load Data*), its state (not run, done, outdated) and
  the *Previous* / *Next* buttons, which follow the order of the menus.

Other menus:

- `File`: *Reset all…* (deletes every variable, closes every figure and puts every panel back to its defaults, after a confirmation) and *Quit*. *Load raw data* is the first item of the Preprocessing
  menu, *Load preprocessed data* the first item of the Data analysis menu. The
  settings are opened and saved from the Preprocessing and Data analysis
  menus (*Open / Save … settings…*): a settings file records how a result
  was obtained.
- `Help` › *Preprocessing* and *Analysis* describe every step in detail
  (what it needs, computes and shows); *About* gives the version, its date
  and the author.
- `View` › show or clear the log, *View all variables*
  (every variable in memory with a short description, its format, size and
  memory; dictionaries open per channel; filter by name or description).

## 5. How the steps depend on each other

Each step needs the results of some earlier steps (for example, the
concatenation needs the mirror distance, and analysis step 3.2 needs
the Brunt–Väisälä frequency of 0.2 and the Coriolis parameter of 3.1). When
**Run** is pressed and an earlier step has not been run yet, the
application runs it first, with the inputs of its own panel, and says so in
the log. When an earlier step is run again, every step that depends on it
is marked as outdated (⚠ in the menu and a note above its figures) until it
is run again.

The computations run in the background: the window stays usable, the Run
buttons are disabled and a busy bar is shown at the bottom right during the
computation. The **Interrupt** button, next to the busy bar, stops the
running step at its next stop point (the loops over files and profiles,
and every message written to the log, are stop points; in practice the
step stops within a fraction of a second) and cancels the steps that were
waiting to run. The interrupted step is not marked as done, and the steps
that depend on it are marked as outdated. The raw cache is written only
once all the files have been read, so an interrupted Load leaves no
incomplete cache.

## 6. The steps

### Preprocessing

The menu has four entries, without sub-menus.

| Step | Content |
|---|---|
| Load raw data | One panel; first box **Settings** (*Open preprocessing settings…*), then four boxes. **Data**: temperature folder of the XT (the log folder is taken next to it, `../log`), configuration (the sub-folders of the temperature folder), channels (the channel folders found), *Rebuild summary.csv*, *Rebuild the raw cache*, the LéXPLORE thermistor chain (*Use LeXPLORE temperature*, chain folder) and the time correction (*Correct to real UTC*, reference local time and the same instant on the XT clock); the **Load** button makes the inventory, corrects the clock, checks the chain coverage, reads the raw cache and the first profile of each channel (truncated to [0, measurement length]). Results: a **Configuration** tab (settings of each channel, number of profiles, first and last time, sampling period) and the truncation figure. **Mirror distance**: scan settings and **Run** (bottom of the U for every profile, first profile folded). **Concatenation**: **Concatenate** (every profile folded on one common grid, connector coordinate; with two channels or more, a new channel **`mean`**, the profile-by-profile mean of the channels, is built and added to the channel lists of the following steps), the maps use the display options of the figure list (right panel). The T(z, time) maps show the **LéXPLORE chain in the top panel** when its data are loaded (depth from the surface, same colour scale and time axis); the calibrated maps of Shift and save do the same. **Run All** runs Load, Mirror distance and Concatenate. |
| Depth Calibration | One panel, two boxes, one per method. **Using LeXPLORE T-Chain**: channels, offset scan and step, free temperature shift, chain depth range, time windows of the fit (UTC; *Clear* empties the table); the windows are shaded in orange on the T(z, time) maps of Load Data and on the calibrated maps of Shift and save, which come forward when this panel is opened. **Select time windows on the T maps** (toggle, orange while on): a horizontal drag on a map adds a window to the table (the zoom and pan modes of the figure tool bar must be off; the selection stops when another panel is opened). **Run** fits the vertical offset and the temperature shift onto the chain (figures: First profile, shown by default, with on its left the first fitted profile shifted by its own fitted pair against the chain at the same time and on its right the mean difference DTS − chain at every chain sensor over all the fitted profiles; Z and T shift vs time; scatter DTS vs chain). The depth range (*Chain depths from / to*) selects the chain sensors used in the fit (the sensors are at 0.25, 1, 2, 4 … 16, 18, 21, 24, 27, 30 m, then every 5 m to 90 m); at least 3 sensors are needed. The log lists the sensors used and their temperature contrast, and warns when the range is almost isothermal (mixed layer, deep water): there the offset is poorly constrained. The scatter shows only the fitted depths, and the first-profile figure shades the fitted range. **Manual**: water-surface position `Z_SURFACE` (fibre length below the connector), drawn as an orange dashed line on the *Uncalibrated Profiles* (first profile folded, Load Data); the toggle **Select the surface with the mouse** shows that figure and a click on it sets `Z_SURFACE`; **Run** applies the value. **Run All** uses the chain when its data are used and cover the DTS window, the manual calibration otherwise. The panel counts as done when one of the two methods has run. |
| Save | One box **Save** (calibration, data to save, output file: folder and *Preprocessed data file*, default `DTS_preprocessed.nc`; **Save** button) and a box **Preprocessing settings** (output file: folder and *Settings file*, default `DTS_preprocessing_settings.json`; **Save** button, asks before replacing). Both folders default to the configuration folder. Load preprocessed data lists every preprocessed file of a configuration, whatever its name. **Calibration**: the list follows the depth calibration done last. After the calibration with the LeXPLORE chain: *Shift in Z and T* or *Shift in Z only* (no temperature shift); after the manual calibration: *Shift in Z*. **Data to save**: *DTS uncalibrated (all channels)*, *DTS calibrated (all channels)*, *Configuration* (the configuration table) and *LeXPLORE data* (only when the chain was used in the calibration; saved as the channel `LeXPLORE T-chain`). The variables used during the preprocessing (inputs of every step run, mirror distances, grid, calibration method, fit depths and windows, time series of the mirror distance and of the fitted offsets) are always saved in the group `preprocessing`. **Output folder** (empty = the configuration folder). `DTS_preprocessed.nc` and its README are written; every group has the attribute `kind`; the shifts stored are those applied (0 for a shift not applied). Every channel is saved: a channel left out of the chain fit takes the shifts of `Combined` (else of the first fitted channel), noted in the log and in the attribute `shifts_taken_from`. |
| Preprocessing report | `DTS_preprocessing_report.md` (with the configuration table) and its figures, next to the product. |

**The raw cache.** Reading the XML files is the slow part of the work. At
the first Load of a configuration, every profile of every selected channel
is read once and stored in `DTS_raw_cache.npz`, in the configuration folder
(about 8 MB per 1000 profiles and channel). The following loads read this
file instead (for `Mirage14_23`: 0.1 s instead of 10 s), and the mirror
distance and the concatenation work from memory. The cache keeps the time
stamps as written by the instrument, so it does not depend on the clock
correction. It is rebuilt automatically for a channel whose files changed
(files added or removed); *Rebuild the raw cache* forces a new reading of
all the files. The temperatures are stored with 32-bit precision, which
changes the results by less than 10⁻⁶ K.

### Data analysis

| Step | Content |
|---|---|
| Load preprocessed data | First box **Preprocessed data**: root folder; drop-down list **Configuration** (the configurations holding a preprocessed file); drop-down list **Preprocessed file** (the preprocessed `.nc` files of that configuration, `DTS_preprocessed.nc` first); LéXPLORE chain folder (empty = the chain saved in the file); **Load data**. Second box **Settings** (*Open analysis settings…*; the dialog opens in the configuration folder of the first file ticked, also the default folder of *Save analysis settings…*). Then the other boxes appear. Every channel of the files is loaded and shown on the maps (every analysis step lists all the channels and keeps its own selection); box **Maps**: *Channels on the maps* (tick boxes, all ticked after loading; only the channels drawn on the maps and individual profiles of this panel), *Include the LéXPLORE chain*, time window and **Update maps**; default figure: T(z, t) maps of every channel. **Time windows**: table (label W1, W2, … given automatically, start and end in UTC), with a toggle to add a window by dragging on the T(z, t) map; the windows are shaded in blue with their labels on the whole-record T(z, t) maps (the window chosen in the step on screen darker); every analysis step has a list *Time window* below its channels (Whole record or one of the windows, updated as soon as a window is added) and then runs on that window only. **Select Individual profiles**: table (label, UTC time) of the profiles used by the wavenumber-domain step, empty at the start; toggle *Select profiles on the T(z, t) map* (a click adds the nearest profile); **Update** uses the table in the analyses and marks the profiles on the maps. Figure *Individual profiles* (figure list): one panel per profile T(z), three columns at most; it has a sub-list with one tickable item per profile of the table (a new profile is added to the sub-list at once, ticked); ticking or unticking a profile redraws it at once; unticking the figure unticks all its profiles (ticking it ticks them all again), and ticking one profile ticks the figure. **Display**: shading and colour map, **Update plot** (the same Display box is in every analysis step that draws maps: smooth shading, shading kind, colour map — *default* keeps the colour map of each figure — and **Update plot**, which redraws the figures of the step without marking the other steps outdated). Brunt–Väisälä: g and the equation of state come from Advanced › Physical parameters, the Run button is in the Channels box. The instrument resolution is computed from the fibre inside the XT (−20 to −5 m). Several configurations are concatenated in time (same sampling period). |
| Resampling data | Channels (whole record); *Spatial resampling* (window average over depth: size, step) and/or *Time resampling* (same time base as LeXPLORE, or window averaging in time: period, step); **Run** creates `<channel>-resampled` channels (CH1-resampled, Combined-resampled, …) offered in every following step; Display: shading, colour map, *Raw and resampled profiles*. Every channel box has a (?) explaining how the channel is built. |
| Multi-layer decomposition | Channels, chain and time window; **Layering**: One layer (nothing to do), Two layers (from the thermocline of the LeXPLORE chain — depth of the largest dT/dz — or from an isotherm) or Three layers (from a top and a bottom isotherm, or the best three-layer fit); the box of the method appears with its **Run** button and, at its top, a *Smoothing* option (window average of T over depth before the interfaces are extracted: width and step, as in Brunt–Väisälä); figure *Layers*: T maps with Z1 (solid) and Z2 (dashed). Every step after it in the menu has a list **Layer** below its time window (Whole column or one of the layers found); the step then works on the depths between the time-mean interfaces of that layer. |
| Brunt–Väisälä | N(z, t), time mean ± std, maps; option *Smooth T before N* (window average of T over depth before dT/dz and N). |
| 2 Isotherm | Depth of one isotherm vs time. |
| Frequency domain – tab *Temperature at each depth* | Frequency × depth maps, mean N overlaid, Coriolis f (latitude of the physical parameters); colour limits None / Instrument resolution / User defined; x axis frequency or period, log or linear. |
| Frequency domain – tab *Isotherm depth* | One box with the Run button; the FFT covers the time window of the step (Whole record or W1, W2, …); spectrum of the isotherm depth with f, the N band and the V1 Poincaré band (Poincaré profiles: list *Same as DTS time window* or one of the windows W1, W2, …); Display: *Use the instrument resolution* (lower bound of the amplitude axis), x axis frequency or period, log or linear, Update plot. |
| 4.1.1 / 4.1.2 | Vertical FFT of every profile; 2D FFT of the water column. |
| Gradient maps, staircases (with the seismogram-like profiles) | *Staircases detection* (at the shared individual profiles, all channels on one figure) works on the layer chosen in the list *Layer* (Whole column, or a layer of the Multi-layer decomposition with its interfaces interpolated at each snapshot instant). The four gradient steps work on the stratified layer S2 (metalimnion): Z1 and Z2 come from the Multi-layer decomposition with three layers (else the default best fit, noted in the log); *Include the LéXPLORE chain* (chain on a 1 m grid). Snapshots of the staircase step are also used by the gradient steps. |
| 5 Report | `DTS_analysis_report.md` and the figures of the analysis steps run, in the first data folder or in a chosen output folder. |

### Advanced

| Item | Content |
|---|---|
| Physical parameters… | Window listing every physical parameter used by the steps (g, Ω, latitude, lake width, LéXPLORE position, salinity, density and expansion — equation of state, parabolic or UNESCO EOS-80, or fixed values —, sound-speed formula and reference temperature); **Apply**, **Reset to defaults**; saved with the analysis settings. |
| Save variables… | Every variable in memory in four categories (preprocessing, analysis, physical parameters, STC), with tick boxes at every level (category, variable, each entry of a dictionary variable); **Save…** asks the file name, folder and format (npz, NetCDF, HDF5, txt, csv, MATLAB). |
| Sound speed maps | Box *STC profiles and sound speed*: STC folder, DTS folder (the list follows both as soon as they change), LéXPLORE folder (closest chain profile added to the STC figures when there is one within ~20 min), list of the profiles (start UTC, DTS time shift, LeXPLORE time shift, distance from LéXPLORE, duration, descent speed, DTS record, file), tick boxes T, P (= ρ̄ g z), S, and one button **Load and plot**: map *STC positions*, per profile T and c vs depth (STC measured, c recalculated from the STC T, the closest Combined DTS profile searched in all the preprocessed files of the DTS folder) and the sound-speed map of the Combined channel of the data loaded (when data are loaded). Box *Resampling and display*: depth window size and step for the STC figures, shading, colour map, one **Update** button. |

**Save data** (right click on a figure name in the figure list, every
figure): the data drawn on the figure, in the format chosen (same formats).

**Rule for future changes**: every physical constant used by a computation
is an entry of `dts_core.PHYSICAL_PARAMETERS` and is read with
`dts_core.physics(name)` — never written as a number inside a step. A new
entry appears in the Physical parameters window without other changes.

## 7. Files

| File | Role |
|---|---|
| `dts_gui.py` | Main window, menus, background running of the steps. |
| `gui_sections.py` | Description of every step: menu place, inputs, default values. Adding or changing an input starts here. |
| `gui_widgets.py` | Input widgets and figure panel. |
| `dts_steps.py` | The steps: one function per menu item (computation, then the figures). |
| `gui_figures.py` | The figures (no computation). |
| `gui_help.py` | Texts of the Help menu (description of every step). |
| `gui_variables.py` | View › View all variables: the variables in memory with their description, format and size. |
| `dts_core.py` | Computation library (reading of the XT files, of the chain and of the STC profiler, folding, calibration, NetCDF product, physical parameters, equation of state, vertical gradient and Brunt–Väisälä frequency, sound speed, FFT, three-layer fit, staircases). |
| `gui_export.py` | Save data of a figure and Save variables: reading the data back from a figure, writing npz, NetCDF, HDF5, txt, csv, MATLAB. |
| `gui_physics.py` | Advanced › Physical parameters window (built from `dts_core.PHYSICAL_PARAMETERS`). |
| `requirements.txt` | Python modules needed. |
| `default_paths.py` | Reads the default folders from `default_paths.ini`. |
| `default_paths_template.ini` | Blank template of `default_paths.ini` (see *Default folders*). |
| `default_paths.ini` | Your own default folders (personal, not in the repository). |
| `.gitignore` | Files kept out of the repository: Python caches, `.DS_Store`, saved settings (`*.json`), `default_paths.ini`. |

The folder `static_figures/` and the file `static_figures.tgz` belong to the
layout prototype and are no longer used; they can be deleted.

## 8. Known limits of version 1.0

- A computation inside a single numerical call (one FFT of a long record,
  for example) cannot be interrupted before that call ends; such calls are
  short.
- The results live in memory: closing the application loses them, except
  the files written by steps 3, 4 and 5 (and the settings file).
- Analysis › Load Data recomputes the instrument resolution from the first raw XML file
  of each channel: the channel folders must be present next to
  `DTS_preprocessed.nc` (otherwise the resolution is not available and the
  options *Colour floor = ½ resolution* have no effect).

## 9. Version history

| Version | Date | Changes |
|---|---|---|
| 3.19 | 16.11.2026 | `default_paths.ini`: a key left empty or a path to a folder that does not exist is ignored (the field starts empty) and named in the log at start; quotes around a path are accepted. |
| 3.18 | 16.11.2026 | Default folders moved out of the code into `default_paths.ini` (personal, ignored by git), read by the new module `default_paths.py`; the repository holds the blank `default_paths_template.ini`; README section *Default folders* explains the setup; the log says at start whether the file was found. No personal path remains in the code. |
| 3.17 | 16.11.2026 | STC figures: the DTS − chain curves removed from the RMS panels (only the differences to the STC remain). |
| 3.16 | 16.11.2026 | List of the STC profiles: new column *LeXPLORE time shift* (closest chain profile − STC start), *DTS shift* renamed *DTS time shift*; the two time shifts come right after the start; the list follows the LéXPLORE folder and its tick box too. |
| 3.15 | 16.11.2026 | Sound speed maps: tick boxes in front of *DTS folder* and *LéXPLORE folder* (include the data set or not); (?) on the STC, DTS and LéXPLORE folders (instrument and sampling, plus the native depth and time resolution of the data found in the folder, computed on click); the labels of the STC figures give the native depth resolution of each data set (STC Δz ≈ 0.5 m, DTS ≈ 0.25 m, chain 0.75–5 m). Panels: a field may carry a tick box in place of its label (`check` in `gui_sections`). |
| 3.14 | 16.11.2026 | STC figures: second row with the RMS over depth windows (new option *RMS window*, 2 m) of the temperature differences (DTS − STC, chain − STC, DTS − chain) and of the sound-speed differences (STC recalculated, DTS, chain − STC measured; DTS − chain); every DTS and chain label of all four panels gives its time shift. |
| 3.13 | 16.11.2026 | Sound speed maps: option *Only STC profiles at LéXPLORE* in the first box (only the profiles within the new physical parameter *LéXPLORE radius*, 100 m by default, are loaded; the others are listed in the log). |
| 3.12 | 16.11.2026 | Sound speed maps: *LéXPLORE folder* in the first box (default: the chain folder); when the chain has a profile within two of its time steps of an STC start, the closest chain profile and the sound speed recalculated from it are added to the STC figure (pink, markers; resampled like the other profiles). |
| 3.11 | 16.11.2026 | Sound speed maps: the two buttons of the first box replaced by one, **Load and plot** (STC positions, STC profile figures and, when data are loaded, the sound-speed map). |
| 3.10 | 16.11.2026 | Sound speed maps: new *DTS folder* (default: DTS next to STC PROFILES); the closest **Combined** DTS profile of each STC profile is searched in every preprocessed file of that folder (no data loading needed; new columns *DTS shift* and *DTS record*); the list is refreshed as soon as the STC or DTS folder changes; the DTS channel box is removed (maps: Combined channel); the sound-speed formula is merged into the STC box; Resampling and Display merged into one box with a single **Update** button. |
| 3.09 | 16.11.2026 | STC list: new columns *Duration* and *DTS shift* (closest DTS profile − STC start, filled once preprocessed data are loaded; tooltip per channel); start shown as dd.mm hh:mm:ss, *From LéXPLORE* renamed *Distance* (header tooltips). DTS profiles box: channels only — the time window, the Closest/Average choice and the Continue/Ignore window are removed; the closest DTS profile is always used. |
| 3.08 | 16.11.2026 | Sound speed maps reorganised: box *STC profiles* first (list with the new column *Descent*, the mean descent speed from the first to the deepest sample; button **Load STC profiles**), box *DTS profiles* (channels, time window, *DTS profile*: Closest or Average; when no DTS profile matches an STC profile in time, a window gives the closest DTS profile and asks Continue / Ignore / Continue for all / Ignore for all — Ignore: no DTS profile on that STC figure), box *Resampling* (depth window size and step for the STC figures), then the sound-speed formula with the button **Sound-speed maps**. |
| 3.07 | 16.11.2026 | List of the STC profiles: the column Location is replaced by *From LéXPLORE*, the distance (m) of every profile from LéXPLORE; the physical parameter *LéXPLORE radius* (3.06) is removed. |
| 3.06 | 16.11.2026 | List of the STC profiles: columns Start (UTC), Location ("at LéXPLORE" when the .vp2 position lies within the new physical parameter *LéXPLORE radius*, 100 m by default; tooltip: position and distance) and File. |
| 3.05 | 16.11.2026 | Save variables: four categories (Preprocessing variables, Analysis variables, Physical parameters, STC variables), a tick box per category (all its variables), per variable and per entry of a dictionary variable (channel, STC profile, … three levels), partly ticked states; only the entries ticked are written; the list is refreshed after every step. |
| 3.04 | 16.11.2026 | Lake outline at full resolution: `Lake_Geneva_outline.geojson` (STC folder) now holds the Lake Geneva polygon of swisstopo swissTLM3D 2026 (layer TLM_BODENBEDECKUNG, standing water; 579.8 km², French part included, 25 536 points, 86 islands), taken from `MAPS/swissTLM3D_2026_LV95_LN02.gdb` and converted to WGS84; the islands are left white on the STC position map. |
| 3.03 | 16.11.2026 | Advanced › *Save variables…* (tick list of the variables and the physical parameters, Save in npz / NetCDF / HDF5 / txt / csv / MATLAB) and *Save data…* in the right-click menu of every figure (the data drawn, read back from the figure, same formats). Sound speed: figure *STC positions* (whole lake + zoom; STC positions from the `.vp2` headers; LéXPLORE position as a physical parameter, 46.500228 N, 6.660835 E; lake outline `Lake_Geneva_outline.geojson` saved in the STC folder: FSO generalised lake boundaries 2026 from swisstopo data, via the npm package swiss-maps, converted to WGS84). STC times are UTC. New modules needed for HDF5 and MATLAB files: h5py, scipy. Six more leftovers removed (referenced only by each other, missed in 3.01): `layer_kz_maps` in `dts_steps.py`; `fft2_map`, `three_layer_examples`, `layer_N`, `layer_kz`, `kz_distributions` in `gui_figures.py`. |
| 3.02 | 16.11.2026 | New menu **Advanced**: *Physical parameters…* (window over `dts_core.PHYSICAL_PARAMETERS`; equation of state — parabolic or UNESCO EOS-80 — or fixed ρ and α; saved with the analysis settings; Reset all restores the defaults) and *Sound speed maps* (UNESCO / Medwin / Mackenzie, tick boxes T, P = ρ̄ g z, S; STC profiler panel: folder, profile list, T and c profiles against the DTS). The latitude and the lake width moved from the frequency-domain panel to the physical parameters. Computations moved to `dts_core.py`: `vertical_gradient`, `brunt_vaisala` (the option *Smooth T before N* now smooths T before dT/dz and the square root — previously N after it; the deep N floor is lower), `time_mean_std`, `smooth_matrix`/`smooth_profile`, `density`, `thermal_expansion`, `reduced_gravity`, `coriolis_frequency_Hz`, `sound_speed`. Gradient maps: option *Smooth T before dT/dz*. Results with the default parameters are unchanged otherwise. |
| 3.01 | 16.11.2026 | Removed the 18 functions that nothing called (listed in `GUI_MAP.md`): 5 in `dts_core.py` (notebook-format concatenation, mirror scan, product writer and README, per-layer 2D FFT), 7 step functions left over from removed panels in `dts_steps.py`, and 6 figure functions in `gui_figures.py`. No change in behaviour; every step was rerun on the test data. |
| 3.00 | 16.11.2026 | The saved files say they were written by the GUI: `DTS_preprocessed.nc` global attributes `history` and `source` = "DTS GUI v3.00 (GUI/dts_core.py, save_product)", README "Written by the DTS GUI v3.00 …" (`dts_core.WRITER`, set by `dts_gui.py`). New `GUI_MAP.md`: every menu item → step, panel inputs, session inputs, outputs, `dts_core` functions and figures, plus the functions never used. |
| 2.99 | 15.11.2026 | Spectral analysis – wavenumber domain: box *Wavenumber range and scaling law* (k min, k max, selection by a drag on the spectra of the individual profiles, range shaded) and button **Fit scaling** (A = a k^b fitted in log-log to every curve of every panel within the range, drawn dashed, a and b in the legend and the log). |
| 2.98 | 15.11.2026 | Seismogram-like profiles: each time label is placed just above the top of its own curve (before, at the mean position of the profile). |
| 2.97 | 15.11.2026 | Spectral analysis – wavenumber domain: a box *full spectrum* next to *Longest wavelength plotted* and *Longest wavelength for colours*; ticked, every wavenumber of the profiles is used. |
| 2.96 | 15.11.2026 | Multi-layer decomposition, individual profiles: one figure per profile with one panel per record; with *Best fit* the model drawn is the continuous three-layer fit of the profile (top and bottom lines joined through the middle layer, slopes and rms in the title), as in the notebook. |
| 2.95 | 15.11.2026 | Window steps of every smoothing (and the time step of the resampling): on auto the box shows the window size and follows it; unticking auto starts from it. **Next** carries the channels ticked (and the LéXPLORE choice) to the next step of the same menu. |
| 2.94 | 15.11.2026 | Figure list (right panel): right click on a figure name › *Show* / *Hide* and *Focus* (shows the figure and brings its tab forward). |
| 2.93 | 15.11.2026 | Time windows shaded on every map with time (UTC) along x: the analysis windows W1, W2, … on all the analysis maps, the fit windows on all the preprocessing maps (redrawn after every step). The title on the left shows the configuration loaded next to the menu name (e.g. *Data analysis [Mirage14_sub]*). |
| 2.92 | 15.11.2026 | Multi-layer decomposition: box *Individual profiles* (shared list, selection on the Layers maps, Update) and figure *Individual profiles* (two and three layers): every record's profile with the interfaces at that time as horizontal lines and the piecewise profile (straight line fitted in each layer). |
| 2.91 | 15.11.2026 | Every window-averaging smoothing (Resampling data, Brunt–Väisälä, N overlay of the frequency domain, Multi-layer decomposition two and three layers): the window step on auto equals the window width. |
| 2.90 | 15.11.2026 | *N window step* on auto (Brunt–Väisälä and the N overlay of the frequency domain) now equals the N window width instead of the native depth spacing. |
| 2.89 | 15.11.2026 | Resampling data, spatial resampling: *Window step* on auto now equals the window size (windows side by side) instead of the native depth spacing. |
| 2.88 | 15.11.2026 | Layout: the grey description of the step is shown below the figures; the title of the step, its state (run / not run / outdated) and the Previous / Next buttons are at the top of the left column, above the panel. |
| 2.87 | 15.11.2026 | The GUI opens blank: no configuration or preprocessed file chosen, no channel ticked (lists filled when the data are loaded), no time window (fit windows and analysis windows), no individual profile, no seismogram start; only the default data folders (temperature folder, chain folder, preprocessed-data root) and the clock reference pair are kept. |
| 2.86 | 15.11.2026 | `requirements.txt`: `tzdata` added (time-zone database for the clock correction; needed on Windows). |
| 2.85 | 15.11.2026 | File › *Reset all…*: after a confirmation, deletes every loaded, preprocessed and analysis variable, closes every figure, empties the channel, window, layer and profile lists and puts every panel back to its default values (files on disk untouched). |
| 2.84 | 15.11.2026 | Seismogram-like profiles: new parameter *Step* (min, auto = every profile), the time between the successive profiles plotted in the duration or the time window. |
| 2.83 | 15.11.2026 | 2D FFT of the water column: the Layer list is replaced by tick boxes *Layers* (whole column and the layers of the Multi-layer decomposition); one figure per channel with one panel per layer ticked (two columns at most, one colour scale for all). |
| 2.82 | 15.11.2026 | LéXPLORE data: every variable of the chain files is kept (surface/bottom temperature, mixed-layer and thermocline depth, Schmidt stability, heat content, …), in the preprocessing, in the saved product (group `LeXPLORE T-chain`) and in the analysis; the (?) of *Include the LéXPLORE chain* lists the variables loaded. Multi-layer, two layers *From thermocline LeXPLORE*: the interface is the chain variable `thermocline_depth`, interpolated in time onto every channel (max \|dT/dz\| only for data without it). |
| 2.81 | 15.11.2026 | Save analysis settings also records the analysis steps run (order and inputs of each) and the figures ticked, and writes every analysis variable to `<name>_variables.pkl` next to the JSON file. Load preprocessed data: opening analysis settings keeps the data chosen; new button **Run the saved analysis** loads the file chosen and runs all the recorded steps with their saved inputs (channels missing in the new data dropped). |
| 2.80 | 15.11.2026 | View menu: *Previous step* and *Next step* removed. Help › Preprocessing and Help › Analysis rewritten to match the current panels (menu order, boxes and buttons, shared individual profiles, staircases with the seismogram-like profiles, one preprocessed file per load, removed items dropped), with a common section on working with the GUI. |
| 2.79 | 15.11.2026 | View all variables: new column *Made by (first)* (the step that first created each variable, recorded while the steps run); right click › *Show value* opens the value of a variable or of one of its entries (arrays with shape, statistics and a shortened listing). |
| 2.78 | 15.11.2026 | Data analysis menu: *Smoothing of the gradients* and *Maps of the smoothed gradients* removed. Figure list (right panel): the check boxes are indented with their names (All figures › step › figure › individual profile), and a click on an indented check box ticks it. |
| 2.77 | 15.11.2026 | *Seismogram-like profiles*: *Start* is a drop-down of the shared individual profiles (updated when the list changes in any step), in which a time can still be typed. |
| 2.76 | 15.11.2026 | *Staircases detection*: (?) next to *Smoothing length* explaining the running mean applied before the gradient. |
| 2.75 | 15.11.2026 | *Staircases* figure: two columns at most; the depth axis of each panel spans the layer chosen at that profile time. |
| 2.74 | 15.11.2026 | (?) next to every *Include the LéXPLORE chain*: sampling of the chain in depth (27 sensors, 0.25 m to 90 m, spacing 1–5 m) and time (10 min), and its interpolation onto a 1 m grid in the gridded steps. |
| 2.73 | 15.11.2026 | *Seismogram-like profiles* moved into *Staircases detection* (box *Seismogram-like profiles* with its time window, start, duration, spacing and a **Plot** button; one figure per channel ticked); the menu item removed. |
| 2.72 | 15.11.2026 | *Staircases detection*: the snapshots are replaced by the shared individual profiles (table, selection on the T(z, t) map of the step, Update); one figure *Staircases* with all the channels ticked per profile (profile as a thin line, detected steps as thick vertical segments at their mean temperature, no shading), plus the T(z, t) *Maps* with the profiles marked. |
| 2.71 | 15.11.2026 | Individual profiles shared by all the analysis steps that have a profile selection (Load preprocessed data, wavenumber domain, temperature-gradient maps): a change in any table (row added, edited, removed, click on a map) is copied at once to the others; a profile picked on a map gets the first free label P<n>. |
| 2.70 | 15.11.2026 | *Staircases detection*, box Detection: two exclusive choices for the threshold of the gradient, *Threshold from the gradient factor* (with a (?) explaining the factor) or *Threshold from a maximum dT/dz* (new parameter *Max \|dT/dz\|*, K/m); only the value of the choice ticked is editable. |
| 2.69 | 15.11.2026 | *Staircases: specific dates* renamed *Staircases detection*. |
| 2.68 | 15.11.2026 | *Load raw data* moved back to the Preprocessing menu and *Load preprocessed data* to the Data analysis menu (first item of each); the File menu keeps *Quit*. |
| 2.67 | 15.11.2026 | Channel lists (tick boxes and radio buttons) of every panel: the channels are packed to the left with an even spacing (before, a long name in a second row widened its column and left a gap after the first channel). |
| 2.66 | 15.11.2026 | Load preprocessed data: the configuration and the preprocessed file are chosen in two drop-down lists (one file loaded at a time; the tick lists and the concatenation of several files are gone). |
| 2.65 | 15.11.2026 | *Temperature-gradient maps* moved before *Staircases* in the menu and no longer needs the staircase snapshots; new box *Individual profiles* (table filled from Load preprocessed data, selection by clicks on the gradient maps, Update); new figure *Individual profiles*: the gradient of every channel (and the chain) at each profile. |
| 2.64 | 15.11.2026 | View › *View all variables*: window listing every variable in memory (description, format, size, memory), dicts opened per channel, filter and Refresh (`gui_variables.py`). |
| 2.63 | 15.11.2026 | *Temperature-gradient maps*: the maps of all the channels ticked on one figure (one panel each, chain first, common colour scale). *Seismogram-like profiles*: box *Time window of the profiles* — a window W1, W2, … of Load preprocessed data, or start and duration. |
| 2.62 | 15.11.2026 | *Staircases*: Run button at the bottom of the Detection box. *Temperature-gradient maps*: channel tick boxes like the other steps (with chain, time window, layer) and the Run button in the Channels box; map and snapshot profiles for every channel ticked. |
| 2.61 | 15.11.2026 | *Staircases in S2* renamed *Staircases: specific dates*; the detection runs in the layer chosen in the list *Layer* (interfaces of the Multi-layer decomposition at each snapshot instant; Whole column = whole profile) instead of always in S2. |
| 2.60 | 15.11.2026 | File menu: *Open settings…* and *Save settings…* removed (the settings are opened and saved from the Preprocessing and Data analysis menus and panels). |
| 2.59 | 15.11.2026 | Load preprocessed data, box *Maps*: channel tick boxes *Channels on the maps* select the channels drawn by **Update maps** (the analysis steps keep their own selections). |
| 2.58 | 15.11.2026 | Load preprocessed data: the box *Settings* moved below *Preprocessed data*; open and save analysis settings default to the configuration folder of the first preprocessed file ticked. |
| 2.57 | 15.11.2026 | Load preprocessed data: new list *Preprocessed files* below the configurations (the preprocessed `.nc` files of the configurations ticked, any name); the files ticked are loaded; files covering the same period are refused. |
| 2.56 | 15.11.2026 | Save: the Run button renamed **Save**; new field *Preprocessed data file* (the README follows the name); the box *Preprocessing settings* has the same layout (output folder, *Settings file*, **Save**, no file dialog). |
| 2.55 | 15.11.2026 | Save: every channel is saved even when only some were fitted in Depth Calibration (before, the unfitted ones were dropped); they take the shifts of `Combined` (else of the first fitted channel), noted in the log and in `shifts_taken_from`. |
| 2.54 | 15.11.2026 | Load preprocessed data: no channel selection any more — every channel of the files is loaded and shown; the box *Maps* keeps the chain option and the time window (*Update maps*). |
| 2.53 | 15.11.2026 | Save: the output folder is set to the configuration folder when the raw data are loaded; the preprocessing settings files are saved to / opened from the configuration folder by default. |
| 2.52 | 15.11.2026 | *Shift and save* renamed *Save*: its three boxes combined into one with the Run button; new box *Preprocessing settings* (*Save preprocessing settings…*). |
| 2.51 | 15.11.2026 | First box *Settings* in Load raw data (*Open preprocessing settings…*) and in Load preprocessed data (*Open analysis settings…*). |
| 2.50 | 15.11.2026 | The two loading panels moved to the File menu: Preprocessing › Load Data is now *File › Load raw data…*, Analysis › Load Data is now *File › Load preprocessed data…*. |
| 2.49 | 15.11.2026 | The *Three-layer decomposition* sub-menu is removed (best fit, interfaces vs time, N in each layer, k_z in the three layers, 2D FFT in each layer). The staircase and gradient steps now take Z1 and Z2 from the Multi-layer decomposition (three layers), else from the default best fit (note in the log); re-running the decomposition marks them outdated. |
| 2.48 | 15.11.2026 | 2D FFT: *Time axis* renamed *Horizontal axis*. Analysis menu: *Staircases in S2*, *Temperature-gradient maps*, *Smoothing of the gradients*, *Maps of the smoothed gradients* and *Seismogram-like profiles* moved out of the Three-layer decomposition sub-menu, one level up. |
| 2.47 | 15.11.2026 | 2D FFT of the water column: one figure with all the channels ticked (one panel each, common colour scale); its title names the layer chosen (or the whole water column). |
| 2.46 | 15.11.2026 | (?) explanations next to *Smooth N* (frequency domain, temperature tab) and *Poincaré profiles* (isotherm tab); wavenumber domain: *Update* button in the Individual profiles box (redraws the spectra and the lines on the maps). |
| 2.45 | 15.11.2026 | Frequency-domain tabs: white titles on blue tabs (selected tab darker). |
| 2.44 | 15.11.2026 | *Spectral analysis – frequency domain* is one item: a Channels box (channels, chain, time window) and two tabs, *Temperature at each depth* (with the Layer list) and *Isotherm depth* (no layer), each with its options, Run and Display. |
| 2.43 | 15.11.2026 | Layer names: two layers *Top layer* / *Bottom layer*; three layers *Top mixed layer* / *Metalimnion* / *Bottom layer*. |
| 2.42 | 15.11.2026 | 3.2: the Poincaré profiles are chosen in a list (*Same as DTS time window*, then the time windows of Load Data) instead of from / to times. |
| 2.41 | 15.11.2026 | Spectral analysis – wavenumber domain: box *Individual profiles* (starts with, and follows, the profiles of Load Data; − / + rows; selection by a click on the k_z map); two figures: *Time × k_z* maps and *FFT of the individual profiles*. |
| 2.40 | 15.11.2026 | Analysis menu: *Spectral analysis – wavenumber domain* is now a direct item (the k_z vs time panel, former 4.1.1, no sub-menu); *2D FFT of the water column* and the *Three-layer decomposition* sub-menu follow it at the top level. |
| 2.39 | 15.11.2026 | The (?) next to the channels drawn in a circle, with more space after the channel name. |
| 2.38 | 15.11.2026 | *Open / Save preprocessing settings…* at the bottom of the Preprocessing menu and *Open / Save analysis settings…* at the bottom of the Data analysis menu (only the panels of that menu; File › Open/Save settings keeps all of them). |
| 2.37 | 15.11.2026 | Channels renamed: `channel n` → `CHn`, `mean` → `Combined` (older files renamed when loaded); a (?) next to every channel explains how it is built. New analysis step *Resampling data* (after Load Data): spatial and/or time resampling (LeXPLORE time base or window averaging) into new channels `<channel>-resampled`; the automatic *Mean resampled* channel of Load Data is replaced by it. |
| 2.36 | 15.11.2026 | Analysis menu order: Load Data, Following an isotherm, Brunt–Väisälä, Multi-layer decomposition; no *Layer* list in the steps placed before the Multi-layer decomposition. |
| 2.35 | 15.11.2026 | Analysis menu: *Following an isotherm* placed just after Load Data. |
| 2.34 | 15.11.2026 | Figure list: unticking *Individual profiles* unticks P1, P2, … (ticking it ticks them again); ticking one profile ticks the figure. |
| 2.33 | 15.11.2026 | Multi-layer decomposition: *Smoothing* option (window width and step) at the top of the Two layers and Three layers boxes, applied before the interfaces are extracted. |
| 2.32 | 15.11.2026 | List *Layer* below the time window in every later analysis step (Whole column or a layer of the Multi-layer decomposition; depths between the time-mean interfaces). |
| 2.31 | 15.11.2026 | New analysis step *Multi-layer decomposition* (after Load Data): one, two (thermocline of the LeXPLORE chain or isotherm) or three layers (two isotherms or best fit), interfaces drawn on the temperature maps. |
| 2.30 | 15.11.2026 | Figure list: figures shown or hidden as soon as their boxes are ticked or unticked; the *Update plots* button remains only in the preprocessing, for the display options of the maps. |
| 2.29 | 15.11.2026 | Figure list: tick box *All figures* at the top and a tick box on each step header to select or deselect all its figures. |
| 2.28 | 14.11.2026 | 3.2: the spectrum is brought forward after Run and Update plot. *Include the LéXPLORE chain* in every analysis step (the chain on a 1 m grid as one more channel where a regular grid is needed; one-channel steps add its figures, off by default). 4.2 *T maps with the example instants* removed (4.2 is now a sub-menu only). 4.2.1: Run button in the Fit box. |
| 2.27 | 14.11.2026 | 4.1.2: the Axes box moved to the Display box (colour floor renamed *Instrument resolution*); Run button in the Channels box. |
| 2.26 | 14.11.2026 | 4.1.1: longest wavelengths, vertical axis and colour floor (renamed *Instrument resolution*) moved to the Display box; Run button in the Channels box. |
| 2.25 | 14.11.2026 | 3.2: x axis scale log or linear in the Display box. |
| 2.24 | 14.11.2026 | 3.1: the longest periods and the colour limits moved to the Display box. |
| 2.23 | 14.11.2026 | 3.2: the amplitude floor moved to the Display box and renamed *Use the instrument resolution*. |
| 2.22 | 14.11.2026 | Brunt–Väisälä: option *Smooth N* (window average over depth, width and step, as in 3.1; the chain is not smoothed). |
| 2.21 | 14.11.2026 | Time windows shown on the whole record: the fit windows of the preprocessing on the maps of Load Data and of Shift and save; the analysis windows W1, W2, … (labelled, the one chosen in the current step darker) on the maps of Analysis › Load Data, updated at once. |
| 2.20 | 14.11.2026 | 3.2 FFT of an isotherm: one box with the Run button; the FFT window fields removed (the time window of the step sets the limits); Poincaré limits *auto*; Display box with the x axis (frequency or period) and Update plot; one spectrum figure. |
| 2.19 | 14.11.2026 | Analysis › Load Data: box *Time windows* (W1, W2, …; table or drag on the T(z, t) map); the windows are shaded in blue with their labels on the whole-record T(z, t) maps (the window chosen in the step on screen darker); every analysis step has a list *Time window* below its channels and runs on the window chosen. |
| 2.18 | 14.11.2026 | 3.1: *auto* box for the longest periods (plotted, colours): every period available. |
| 2.17 | 14.11.2026 | 3.1 FFT at each depth: channels, frequency band, N overlay and Coriolis in one box without title, with the Run button and the colour limits (None, Instrument resolution, User defined); Display: x axis frequency or period, log or linear. |
| 2.16 | 14.11.2026 | Following an isotherm: the Run button is in the Isotherm box. |
| 2.15 | 14.11.2026 | The left panel widens itself when a step needs more room, so no text is cut (it is never narrowed automatically). Analysis › Load Data: the profile table is empty at the start; the chain is chosen with *Include the LéXPLORE chain* on a line below the channels. |
| 2.14 | 14.11.2026 | Brunt–Väisälä: Physics box removed, Run button in the Channels box. Every analysis step that draws maps has the Display box of Load Data (shading, colour map, *Update plot*); 4.2.10 gained it. |
| 2.13 | 14.11.2026 | Every analysis step lists all the DTS channels of the record; the selection of a step applies to that step only (the *Select* of Load Data only changes its maps and no longer marks the other steps outdated). |
| 2.12 | 14.11.2026 | The analysis steps share one set of tabs and one figure list, as in the preprocessing: the results of every step stay open when moving through the steps, and the tabs of the chosen step are brought forward. |
| 2.11 | 14.11.2026 | Menus at the top in a bigger bold font. Analysis › Load Data: chain folder in the first box; new channel *Mean resampled* (DTS on the LeXPLORE time base by sliding-window averaging), not created (with a message) when the DTS sampling period is longer than the chain's. |
| 2.10 | 14.11.2026 | Analysis › Load Data: figure *Example instants* removed; new figure *Individual profiles* (one panel per profile, three columns at most) with a sub-list of tickable profiles in the figure list, updated as soon as a profile is added to the table. |
| 2.9 | 14.11.2026 | Analysis › Load Data: button *Select* in the Channels box; the Instrument resolution box removed (fixed range −20 to −5 m); box *Select Individual profiles* (table, selection with the mouse on the T(z, t) map, *Update* that marks the profiles on the maps); colour map and *Update plot* in the Display box. |
| 2.8 | 14.11.2026 | Preprocessing › Load Data: the root folder is now the `temperature` folder of the XT; the log folder is taken next to it (`../log`), shown in the log and in the Configuration tab, and saved with the preprocessing variables. A root pointing at the XT data folder (older settings) still works. |
| 2.7 | 14.11.2026 | Shift and save: box *Data to save* (DTS uncalibrated, DTS calibrated, configuration, LeXPLORE chain as the channel `LeXPLORE T-chain`); the variables used during the preprocessing are saved in the group `preprocessing`. Analysis menu: *Load Data* (root folder, list of the preprocessed configurations, Load data; then channels and Update plot; default map of the first channel) and *Brunt–Väisälä frequency* at the top level. |
| 2.6 | 14.11.2026 | Help menu: *Preprocessing* and *Analysis* (detailed description of every step), *About* with the author (Jerome Noir) and the date of the version. Menu *Run* removed (the panels keep their Run / Run All buttons). |
| 2.5 | 14.11.2026 | Shift and save with the chain: options reduced to *Shift in Z and T* and *Shift in Z only*. |
| 2.4 | 14.11.2026 | Shift and save: the calibration list follows the depth calibration done (chain: shift in Z and T, Z only or T only; manual: shift in Z); the former choice automatic / chain / manual removed; the report states the option applied. |
| 2.3 | 14.11.2026 | Display options of the maps (smooth shading, shading kind, colour map) moved from the Concatenation box and from Shift and save to the right panel, under the figure list; *Update plots* redraws all the preprocessing maps with them (no new computation). The LéXPLORE chain is drawn in the top panel of the T(z, time) maps and of the calibrated maps when it is loaded. |
| 2.2 | 14.11.2026 | Green / red circle on the right of every figure of the figure list (ready / not available yet). The `mean` channel is built during the concatenation (Load Data) and appears in the channel lists: it is mapped, calibrated with its own fitted shifts (before: the mean of the two channels' shifts) and saved like the other channels; the option *Add the 'mean' channel* of Shift and save removed. |
| 2.1 | 14.11.2026 | Figure list with tick boxes on the right of the figures (Update plots), close button (x) on every tab, default preprocessing figures (Configuration, T maps, First profile); *Folded first profile* renamed *Uncalibrated Profiles*; manual calibration: surface selected with the mouse on the Uncalibrated Profiles (the manual step makes no figure of its own any more); First profile of the depth calibration corrected: it is now the first profile **inside** the fit windows with its own fitted shifts (before, the first profile of the record, often days before the windows, with the shifts of another time, so the mixed layer looked mismatched), plus the mean difference DTS − chain per chain sensor. |
| 2.0 | 14.11.2026 | Depth Calibration with a chain depth range: the minimum number of depths adapts to the sensors in the range (at least 3; before, 10 were required, so a range such as 60-80 m, which holds 5 sensors, failed); clear message when the range holds too few sensors; the scatter uses only the fitted depths and the first-profile figure shades the range; warning for almost isothermal ranges; the report lists the depths used. |
| 1.9 | 14.11.2026 | LeXPLORE chain: Load writes the status of the chain and the exact reason when it is not available (folder not found, module netCDF4 missing, period not covered, reading error) in the log and in the Configuration tab; the calibration with the chain reads the chain again before failing; at start the log lists missing Python modules. |
| 1.8 | 14.11.2026 | Depth Calibration: the T(z, time) maps come forward when the panel opens; the fit windows are shaded on the maps; the toggle *Select time windows on the T maps* adds a window by a horizontal drag on a map; *Clear* button for the window table. |
| 1.7 | 14.11.2026 | Drop-down menus repeated in a bar at the top of the window; the preprocessing steps share one set of result tabs, which stay open when moving between steps; outdated tabs marked ⚠ in their title. |
| 1.6 | 14.11.2026 | *Depth Calibration* is one panel (no sub-menu) with two boxes, *Using LeXPLORE T-Chain* and *Manual*, each with its Run button; Run All chooses the method; the click that sets `Z_SURFACE` acts only on the manual figure. |
| 1.5 | 14.11.2026 | **Interrupt** button at the bottom right, next to the busy bar: stops the running step at its next stop point and cancels the queued steps. |
| 1.4 | 14.11.2026 | Colour-map choice (10 maps, grey scale included) in the Concatenation box of *Load Data*, applied by Concatenate and Update plot. |
| 1.3 | 14.11.2026 | Menu items and the top line without section numbers (*Preprocessing › Load Data*); the panel title above the inputs removed. |
| 1.2 | 14.11.2026 | The time-correction fields moved into the Data box of *Load Data*, between the chain folder and the Load button. |
| 1.1 | 14.11.2026 | Preprocessing menu reduced to four entries: *Load Data* gathers the former steps 0 (select data sets), 1.3 (mirror distance) and 2.1 (concatenation) in one panel with one button per box (Load, Run, Concatenate, Update plot) and Run All; the chain options (*Use LeXPLORE temperature*, folder) moved into the Data box; Configuration tab after Load; raw cache `DTS_raw_cache.npz` with *Rebuild the raw cache*; *Update plot* redraws without computing; calibrations renumbered 2.1 (chain) and 2.2 (manual). Results checked identical to version 1.0 (`Mirage14_23`). |
| 1.0 | 13.11.2026 | First working version: all the steps of the two notebooks, own library, background computation, automatic earlier steps, outdated marks, settings files, click-to-set `Z_SURFACE`. All times UTC except the clock reference. |
| 0.1 | 13.11.2026 | Layout prototype with static figures. |
