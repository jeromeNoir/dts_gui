"""gui_help.py -- texts of the Help menu of the DTS GUI (HTML).

PREPROCESSING_HELP and ANALYSIS_HELP describe every menu item: what it
needs, what it computes, its inputs and its results.  Keep them in line
with dts_steps.py and gui_sections.py when a step changes (they follow the
order of the menus).
"""

STYLE = """
<style>
 body { font-family: sans-serif; font-size: 13px; line-height: 1.35; }
 h1 { font-size: 20px; margin-bottom: 4px; }
 h2 { font-size: 16px; margin-top: 18px; border-bottom: 1px solid #bbb; }
 h3 { font-size: 14px; margin-top: 12px; }
 td, th { padding: 2px 8px; vertical-align: top; }
 .note { color: #555; }
</style>
"""

COMMON = """
<h2>Working with the GUI</h2>
<ul>
<li><b>Menus</b>: <i>File</i> (<i>Reset all…</i>: after a confirmation,
deletes every loaded, preprocessed and analysis variable, closes every
figure and puts every panel back to its default values, with empty channel,
window, layer and profile lists; files on disk are not touched; and
Quit), <i>Preprocessing</i> (Load raw data,
Depth Calibration, Save, Preprocessing report, then Open / Save preprocessing
settings), <i>Data analysis</i> (Load preprocessed data and the analysis
steps, then Open / Save analysis settings), <i>View</i> and <i>Help</i>.</li>
<li><b>Panels</b>: the left part of the window shows the title of the menu
item (with, in blue, the configuration of the data loaded in that menu), its state (run, not run, outdated) with the <b>Previous</b> /
<b>Next</b> buttons, then its inputs grouped in boxes (a short description
of the step is shown in grey below the figures); the <b>Run</b> (or <b>Save</b>, <b>Plot</b>,
<b>Update</b>) buttons sit in the box whose inputs they use. <b>Reset</b>
(bottom left) puts the inputs of the panel back to their default values.</li>
<li><b>Figures</b>: the results of all the steps of a menu are gathered in
one set of tabs. By default only the figures of the current step are shown
and all the others are hidden; any figure of the menu can still be shown,
hidden or brought forward by hand from any step (list or right click), until
another step is chosen. The <i>Configuration</i> table of Load raw data
stays shown in every step of the preprocessing. After a complete run (the saved analysis, or the
whole preprocessing from Load to Save) the GUI returns to the load step and
only its figures are shown. A figure keeps its own size: when the window is
smaller, horizontal and vertical scroll bars appear (the window itself has
no minimum size for the figures). The
list on the right selects the figures shown: <i>All figures</i>, then one
header per step, its figures and (for <i>Individual profiles</i>) one item
per profile, each check box indented with its name. A figure is shown or
hidden as soon as its box is ticked or unticked; a click on its name brings
its tab forward (showing it first if it was hidden); a header ticks or unticks
all the figures below it (partly ticked when only some are). A right click
on a figure name opens <i>Show</i> / <i>Hide</i> (tick or untick it) and
<i>Focus</i> (show it and bring its tab forward; only for a figure already
computed; on an individual profile P1, P2, …: Show / Hide that profile, and
Focus / Save data of its figure; on a header: Show all / Hide all) and <i>Save data…</i> (the data drawn on the figure — curves,
maps with their x and y, shaded areas, points, labels, axis titles, one
group per panel — written to a file whose name, folder and format are
asked: npz, NetCDF, HDF5, txt, csv or MATLAB; times in UTC: datetime64 in
npz, milliseconds since 1970 in NetCDF/HDF5, ISO text in txt/csv/MATLAB;
txt and csv write one table per curve or map plus an index file). Green circle: ready; red circle: not computed yet. Every figure has the matplotlib tool bar
(zoom, pan, save).</li>
<li><b>Outdated results</b>: running an earlier step again marks the later
results as outdated (⚠ in the menu and in the tab titles). A running step
can be stopped with <b>Interrupt</b> (bottom right).</li>
<li><b>Start</b>: the GUI opens blank (no configuration or file chosen, no
channel, no time window, no individual profile); only the default data
folders are filled in. A settings file restores a previous state.</li>
<li><b>Help buttons</b>: a <b>(?)</b> in a circle next to an input or a
channel opens a short explanation.</li>
<li><b>View</b>: <i>Show / hide the log</i> (Ctrl+L), <i>Clear the log</i>
and <i>View all variables</i>: a window listing every variable kept in
memory (preprocessing variables first, then those of the analysis, prefix
<code>A_</code>) with what it represents, the step (menu › step) that first
created it in this session (<i>Made by (first)</i>; — when it was made
outside a step), its format, its size and the memory it uses. Dictionaries
open to their entries (one per channel); a filter keeps the variables whose
name or description contains a text; <b>Refresh</b> reads them again. A
right click and <i>Show value</i> opens the value of a variable or of one
of its entries (arrays with their shape, minimum, maximum, mean, number of
NaN and a shortened listing; dictionaries entry by entry; tables in
full).</li>
</ul>
"""

PREPROCESSING_HELP = STYLE + """
<h1>Preprocessing</h1>
<p>The preprocessing turns the raw XML files written by the Silixa XT into a
calibrated record of the water temperature as a function of depth and time,
saved in a netCDF file (<code>DTS_preprocessed.nc</code> by default). It has
four items in the Preprocessing menu, used in order: <b>Load raw data</b>,
<b>Depth Calibration</b>, <b>Save</b> and <b>Preprocessing report</b>. All
the times entered are UTC, except the reference local time of the clock
correction.</p>

<p>Coordinates: along the fibre, <i>x</i> = 0 at the connector of the XT. The
cable is laid as a U (down to the bottom and back up), so each profile is
<i>folded</i>: the descending and the ascending legs are averaged on a common
vertical axis <i>z</i>, still counted from the connector. The depth
calibration then moves the origin to the water surface.</p>

<p><b>Display of the maps</b> (below the figure list, preprocessing only):
smooth shading, shading kind and colour map of all the preprocessing maps,
applied by <b>Update plots</b> without computing anything again.</p>

<p><b>Settings</b>: the inputs of the four panels (and the display options
of the maps) can be kept in a JSON file: <i>Save preprocessing settings…</i>
at the bottom of the Preprocessing menu or the box <i>Preprocessing
settings</i> of Save; <i>Open preprocessing settings…</i> (menu, or first box
of Load raw data) fills the panels again. The default folder is the
configuration folder.</p>

<h2>1. Load raw data</h2>
<p>One panel, four boxes. <b>Run All</b> (bottom right) runs Load, Mirror
distance and Concatenate in order.</p>
<p><b>Settings</b> (first box): <i>Open preprocessing settings…</i>.</p>

<h3>Box Data (button Load)</h3>
<ul>
<li><b>Temperature folder</b>: the <code>temperature</code> folder of the
XT, which holds the configurations; the <code>log</code> folder of the
instrument is taken next to it (<code>../log/log.db</code>). An older
setting that points at the XT data folder itself is accepted (its
<code>temperature</code> sub-folder is used). <b>Configuration</b>: a
sub-folder of the temperature folder. <b>Channels</b>: the channel folders
found in the configuration (tick boxes).</li>
<li><b>Inventory</b>: every XML file is listed in <code>summary.csv</code>
(file, original and corrected time, channel, acquisition time, resolution),
read back when it exists; <i>Rebuild summary.csv</i> scans the files again
(needed after a change of the folder content or of the time
correction).</li>
<li><b>Raw cache</b>: every profile is read once from the XML files and
stored in <code>DTS_raw_cache.npz</code> in the configuration folder; the
next loads read this file. The cache of a channel whose files changed is
rebuilt automatically; <i>Rebuild the raw cache</i> forces a new
reading.</li>
<li><b>LéXPLORE thermistor chain</b>: with <i>Use LeXPLORE temperature</i>,
the chain files of the <i>Chain folder</i> are read over the time window of
the DTS record, with every variable they hold (temperature, surface and
bottom temperature, mixed-layer and thermocline depth, Schmidt stability,
heat content, …), all saved with the chain by Save. The Configuration tab says whether the chain is available,
or why not (folder not found, module netCDF4 missing, period not covered,
reading error).</li>
<li><b>Time correction</b>: the clock of the instrument is not set. With
<i>Correct to real UTC</i>, the reference pair (an instant read on a watch,
<i>Reference time</i>, in local time, and <i>Same instant on the XT
clock</i>) gives the offset added to every time stamp. Unticked: the stamps
are used as written by the instrument.</li>
<li><b>Results</b>: the <i>Configuration</i> table (settings of each channel,
number of profiles, first and last time, sampling period, chain status) and
the <i>Truncation</i> figure (first profile over the whole fibre and cut to
[0, measurement length]).</li>
</ul>

<h3>Box Mirror distance (button Run)</h3>
<ul>
<li>The <b>mirror distance</b> is the position along the fibre of the bottom
of the U, found for every profile as the distance that makes the two legs
most alike (smallest rms difference): a full scan (<i>Scan range</i>,
<i>Scan step</i>; <i>auto</i> = library defaults) on the first profile, then
a narrow scan (± <i>Tracking half-width</i>) for the next ones.</li>
<li><b>Results</b>: <i>Mirror distance vs time</i> (with the time mean of
each channel) and the <i>Uncalibrated Profiles</i> (first profile folded at
the mean distance: descending leg, ascending leg and their mean, connector
coordinate).</li>
</ul>

<h3>Box Concatenation (button Concatenate)</h3>
<ul>
<li>Every profile is cropped to [0, measurement length], folded at the mean
mirror distance of the channels and interpolated on one common vertical grid
(step = the sampling step along the fibre). The result is one matrix
T(z, time) per channel; the time of a profile is the centre of its
measurement period.</li>
<li>Channel names: the XT channels are called <code>CH1</code>,
<code>CH2</code>, …. With two channels or more, a channel
<b>Combined</b> is built: the profile-by-profile mean of the channels
(profiles paired by their order, time = mean of the paired times). It
appears in the channel lists of the next steps and is calibrated and saved
like the other channels. The <b>(?)</b> next to a channel explains how it is
built.</li>
<li><b>Result</b>: the <i>T(z, time) maps</i>, with the LéXPLORE chain in
the top panel when it is loaded (its depth is counted from the
surface).</li>
</ul>

<h2>2. Depth Calibration</h2>
<p>Two methods, one box each, each with its <b>Run</b> button. <b>Run
All</b> uses the chain when its data are used and cover the DTS window, the
manual method otherwise. The T(z, time) maps come forward when this panel is
opened.</p>

<h3>Box Using LeXPLORE T-Chain</h3>
<ul>
<li><b>Channels</b>: the channels fitted (all ticked after Concatenate). A
channel left unticked is still saved, with the shifts of
<code>Combined</code> (see Save).</li>
<li>The DTS and the chain are brought to one common sampling: the longest
sampling period of all the records, on the time window common to all; the
records with a shorter period are averaged onto it.</li>
<li>For every profile, the DTS profile is shifted vertically over
± <i>Offset scan</i> (step <i>Offset step</i>), evaluated at the depths of the
chain sensors and compared with the chain; the best <b>vertical offset</b>
gives the smallest rms difference. With <i>Free temperature shift</i>, a
constant <b>temperature shift</b> is fitted at the same time (the mean
difference DTS − chain is removed before the rms), so that a temperature
bias of the DTS does not bias the depth.</li>
<li><b>Chain depths from / to</b> restrict the chain sensors used (at least 3;
the sensors are at 0.25, 1, 2, 4 … 16, 18, 21, 24, 27, 30 m, then every 5 m
to 90 m). The log gives the temperature contrast over these depths and warns
when it is small (mixed layer, deep water): there the offset is poorly
constrained. Keep the thermocline in the range.</li>
<li><b>Time windows of the fit</b> (UTC; <i>Clear</i> empties the table)
restrict the profiles used; no window = the whole common window. They are
shaded in orange on every preprocessing map whose x axis is the time
(T(z, time) maps, calibrated maps of Save).
With <i>Select windows on the T maps</i> (orange while on), a horizontal
drag on a map adds a window (zoom and pan of the figure tool bar off).</li>
<li><b>Results</b>: <i>First profile</i> (left: the first fitted profile
shifted by its own offset and temperature shift, against the chain at the
same time; right: the mean difference DTS − chain at every chain sensor over
all the fitted profiles, ± one standard deviation, fitted range shaded),
<i>Z and T shift vs time</i> (means and standard deviations), <i>DTS vs chain
scatter</i> (fitted depths, least-squares line).</li>
</ul>

<h3>Box Manual</h3>
<ul>
<li>Without chain data, the depth origin is set by hand: the <b>water surface
position</b> is the length of fibre between the connector and the water
surface, read on the <i>Uncalibrated Profiles</i> as the sharp transition
between air and water, where it is drawn as an orange dashed line.
<i>Select the surface with the mouse</i> shows that figure, and a click sets
the value. <b>Run</b> applies it.</li>
</ul>

<h2>3. Save</h2>
<h3>Box Save (button Save)</h3>
<ul>
<li><b>Calibration</b>: the list follows the depth calibration done last.
With the chain: <i>Shift in Z and T</i> (the mean vertical offset is added to
the depth axis and the mean temperature shift to the temperature) or
<i>Shift in Z only</i>; with the manual method: <i>Shift in Z</i> (origin
moved to the water surface). The calibrated record is cropped to the water
column (depth ≥ 0, counted downwards from the surface).</li>
<li><b>Every channel is saved</b>, <code>Combined</code> included, each with
its own fitted shifts; a channel left out of the chain fit takes the shifts
of <code>Combined</code> (else of the first fitted channel); the log says so
and the attribute <code>shifts_taken_from</code> records it.</li>
<li><b>Data to save</b>: <i>DTS uncalibrated</i> (z from the connector),
<i>DTS calibrated</i> (depth from the surface; the analysis needs it),
<i>Configuration</i> (the configuration table of Load raw data) and
<i>LeXPLORE data</i> (only when the chain was used in the calibration; saved
as the group <code>LeXPLORE T-chain</code>). At least one of the two DTS
records must be ticked. The <b>variables of the preprocessing</b> (inputs of
every step run, data folder, clock offset, mirror distances, grid,
calibration method and option, water surface, fitted depths and windows,
time series of the mirror distance and of the fitted offsets) are always
saved in the group <code>preprocessing</code>. Every group carries the
attribute <code>kind</code>.</li>
<li><b>Output file</b>: <i>Output folder</i> (set to the configuration
folder when the raw data are loaded; empty = the configuration folder) and
<i>Preprocessed data file</i> (default <code>DTS_preprocessed.nc</code>;
<code>.nc</code> added if missing). A README named after the file is written
next to it. Load preprocessed data lists every preprocessed file of a
configuration, whatever its name.</li>
<li><b>Result</b>: <i>Calibrated T(depth, time)</i>, with the chain on top
when it is loaded.</li>
</ul>
<h3>Box Preprocessing settings (button Save)</h3>
<ul>
<li><i>Output folder</i> (default: the configuration folder) and
<i>Settings file</i> (default <code>DTS_preprocessing_settings.json</code>):
<b>Save</b> writes the inputs of every preprocessing panel in this file,
without a file dialog (it asks before replacing an existing file).</li>
</ul>

<h2>4. Preprocessing report</h2>
<ul>
<li><b>Run</b> writes the markdown report (<i>Report file</i>) and the
figures of the steps run (<i>Figure folder</i>, at <i>Figure resolution</i>)
in the output folder of Save: data set and time correction, configuration
table, truncation and folding, depth calibration (method, windows, depths,
shifts, scatter fits), saved file and the captioned figures.</li>
</ul>
""" + COMMON

ANALYSIS_HELP = STYLE + """
<h1>Data analysis</h1>
<p>The analysis works on one preprocessed file: the <b>calibrated</b>
temperature T(depth, time) of every channel, the depth counted downwards
from the water surface. All the times entered are UTC. The items follow the
order of the Data analysis menu. A step runs the earlier steps it needs when
they have not run.</p>

<h2>Common inputs</h2>
<ul>
<li><b>Channels</b> (first box of most steps): tick boxes, one per channel
of the file (<code>CH1</code>, <code>CH3</code>, <code>Combined</code>, …,
and the <code>-resampled</code> channels made by Resampling data), each with
a (?) explaining how it is built. Ticking or unticking a channel in one
step ticks or unticks it in every step (preprocessing and analysis apart);
no figure is redrawn until <b>Update plot</b> (or <b>Run</b>) is pressed in
a step.</li>
<li><b>Include the LéXPLORE chain</b>: adds the thermistor chain as one more
record. Its (?) describes its sampling: 27 sensors at 0.25, 1, 2, 4 … 16, 18,
21, 24, 27, 30 m, then every 5 m to 90 m; one profile every 10 minutes. In
the steps that need a regular depth grid (2D FFT, gradients, staircases) it
is first interpolated onto a 1 m grid. Every variable of the LeXPLORE files
is kept (temperature, surface and bottom temperature, mixed-layer and
thermocline depth, Schmidt stability, heat content, …); the (?) lists those
of the data loaded, with their units and sizes.</li>
<li><b>Time window</b>: <i>Whole record</i> or one of the windows W1, W2, …
defined in Load preprocessed data; the step then works on the profiles of
that window only, and its figure titles carry the label.</li>
<li><b>Layer</b> (steps after the Multi-layer decomposition; tick boxes
<b>Layers</b> in the 2D FFT): <i>Whole column</i> or one of the layers of the last decomposition (two layers:
<i>Top layer</i> surface – Z1, <i>Bottom layer</i> Z1 – bottom; three
layers: <i>Top mixed layer</i> surface – Z1, <i>Metalimnion</i> Z1 – Z2,
<i>Bottom layer</i> Z2 – bottom). Unless said otherwise, the step works on
the depths between the time-mean interfaces of that layer; a channel left
out of the decomposition takes the interfaces of <code>Combined</code>.</li>
<li><b>Individual profiles</b> (Load preprocessed data, Multi-layer
decomposition, wavenumber domain, temperature-gradient maps, staircases
detection): one shared list of
profiles (label, UTC time). A profile added, edited or removed in any of
these tables (by hand, with + row / − row / Clear, or by a click on a map
with the toggle <i>Select … on the map</i>) is copied at once to the others;
a profile picked on a map takes the nearest profile time and the first free
label P1, P2, …. Each step redraws its figures with the list when it is run
or when its <b>Update</b> is pressed.</li>
<li><b>Window averaging</b>: in every smoothing by window averaging over
depth (Resampling data, Brunt–Väisälä, N overlay of the frequency domain,
Multi-layer decomposition; the time step of the time resampling likewise),
the <i>step</i> between the window centres on <i>auto</i> equals the window
width (windows side by side): the step box shows that value and follows the
width; unticking <i>auto</i> starts from it, and a smaller step gives
overlapping windows.</li>
<li><b>Display</b> (steps that draw maps): <i>Smooth shading</i>,
<i>Shading kind</i>, <i>Colour map</i> (<i>default</i> = the colour map of
each figure) and the options of the step; <b>Update plot</b> redraws the
figures of the step with the current channels, individual profiles and time
windows (shaded on the time maps) without marking the other steps as
outdated. Every step has this button (steps without display options: a
<b>Display</b> box with the button only). Adding a time window or an
individual profile, or changing the channels, redraws nothing by itself:
the figures follow at the next <b>Update plot</b>, so that editing stays
fast after a complete processing (exceptions: ticking an individual profile
in the figure list redraws its figure at once, and a figure shown again
gets its time windows at once).</li>
<li><b>Settings</b>: <i>Save analysis settings…</i> (bottom of the Data
analysis menu) writes a JSON file with the inputs of every analysis panel
(tick boxes, choices, tables, time windows, individual profiles), the list
of the <b>analysis steps run</b> since the data were loaded, in the order of
their last run and with the inputs each one used, and the figures ticked;
all the analysis variables (<code>A_…</code>, with the step that made each)
are written next to it in <code>&lt;name&gt;_variables.pkl</code> (Python
pickle). Default folder: the configuration of the file loaded. <i>Open
analysis settings…</i> fills the panels again; the data chosen in Load
preprocessed data are kept.</li>
</ul>

<h2>Load preprocessed data</h2>
<ul>
<li><b>Preprocessed data</b>: <i>Root folder</i> (whose sub-folders are the
configurations); drop-down <i>Configuration</i> (the configurations that hold
a preprocessed file); drop-down <i>Preprocessed file</i> (the preprocessed
<code>.nc</code> files of that configuration, <code>DTS_preprocessed.nc</code>
first); <i>LéXPLORE chain folder</i> (empty = the chain saved in the file, or
the chain folder stored in it); <b>Load data</b>. Every channel of the file is
loaded. Files written before version 2.37 (<code>channel n</code>,
<code>mean</code>) are renamed <code>CHn</code>, <code>Combined</code>.</li>
<li><b>Settings</b>: <i>Open analysis settings…</i> (the dialog opens in the
configuration folder chosen) fills every analysis panel from the file but
keeps the data chosen in the box above (root folder, configuration, file,
chain folder). <b>Run the saved analysis</b> then loads the file chosen and
runs every step recorded in the settings, in the same order and with the
same inputs, so that a whole analysis is repeated on another data set in one
click. Channels that do not exist in the new data are left out (all the
channels when none remains; a single channel becomes <code>Combined</code>);
the panels show the inputs used; at the end the GUI returns to this step
and only its figures are shown (the others are in the figure list).</li>
<li>The other boxes appear after loading. <b>Maps</b>: <i>Channels on the
maps</i> (all ticked after loading; only the maps and individual profiles of
this panel), <i>Include the LéXPLORE chain</i>, <i>Time window</i>;
<b>Update maps</b>.</li>
<li><b>Time windows</b>: table (label, start, end in UTC; labels W1, W2, …
given automatically); the toggle <i>Select windows on the T(z, t) map</i>
adds a window by a horizontal drag on the map. The windows are shaded in
blue, with their labels, on every map of the analysis whose x axis is the
time (UTC) — the T(z, t) maps, N(z, t), the gradient maps, the layers and
staircase maps, Time × k_z, … (the window chosen in the step on screen
darker), and the lists <i>Time window</i> of every step follow the table at
once.</li>
<li><b>Select Individual profiles</b>: the shared profile table; the toggle
<i>Select profiles on the T(z, t) map</i> adds the nearest profile on a
click; <b>Update</b> marks the profiles as dashed lines on the maps and
redraws the <i>Individual profiles</i> figure with every profile of the
table ticked, and brings that figure forward.</li>
<li><b>Display</b>: shading and colour map; <b>Update plot</b>.</li>
<li>The <b>instrument resolution</b> of each channel (used by the options
<i>Instrument resolution</i> of the spectral steps) is the standard
deviation of the temperature on the fibre inside the XT (x from −20 to
−5 m) in the raw files of the configuration; for <code>Combined</code>,
√(r₁² + r₂² + …)/n.</li>
<li><b>Results</b>: <i>Configuration</i> (first in the figure list, under
<i>Load data</i>): one column per channel with the files, the number of
profiles, first and last profile (UTC), sampling period, depths and depth
spacing, z and T shifts ± std stored in the file, time correction,
calibration kind and the LéXPLORE chain loaded; <i>T(z, t) maps</i> of the channels ticked (and the
chain), with the individual profiles marked; <i>Individual profiles</i>: one
panel per profile T(z), three columns at most, every channel at its profile
nearest in time. In the figure list, this figure has one item per profile;
ticking or unticking one (box or right click) redraws the figure at once
with the profiles ticked and brings it forward; unticking the figure
unticks all its profiles (and unticking the last profile hides the figure),
ticking one profile shows the figure. The figure is computed whenever the
table has profiles, even while hidden.</li>
</ul>

<h2>Resampling data</h2>
<ul>
<li><b>Channels</b>: the channels to resample (whole record).</li>
<li><b>Resampling</b>: <i>Spatial resampling</i> — window average over depth
(<i>Window size</i>, <i>Window step</i>, auto = the window size); <i>Time
resampling</i> — <i>Same time base as LeXPLORE</i> (average over one chain
period centred on every chain time; refused when the DTS samples more slowly
than the chain) or <i>Window averaging in time</i> (<i>Period</i>,
<i>Step</i>, auto = the period). Both can be ticked (space first). <b>Run</b>
creates one channel <code>&lt;channel&gt;-resampled</code> per channel
ticked; a new run replaces them. Their (?) gives the details.</li>
<li><b>Display</b>: shading, colour map, <i>Raw and resampled profiles</i>;
results <i>Resampled T(z, t) maps</i> and <i>Raw and resampled
profiles</i>.</li>
</ul>

<h2>Following an isotherm</h2>
<ul>
<li>Box <b>Isotherm</b>: <i>Isotherm</i> (°C) and <b>Run</b>. Depth of the
isotherm in every profile (shallowest crossing, linear interpolation), with
an uncertainty of half the local grid spacing, for the channels ticked and
the chain. Result: <i>Isotherm depth</i> vs time.</li>
</ul>

<h2>Brunt–Väisälä frequency</h2>
<ul>
<li>N = √(−g α(T) ∂T/∂z) / 2π, in Hz, at every depth and time; g and the
expansion coefficient α(T) come from <b>Advanced › Physical parameters</b>
(by default the parabolic freshwater law, α = 1.36 × 10⁻⁵ (T − 3.98) K⁻¹,
and g = 9.81 m/s²). Negative N² (unstable water) gives N = 0 on the maps;
the signed N² is kept in the variable A_N2_PROFILES and the log gives the
share of unstable points.</li>
<li><b>Smooth T before N</b> (?) (off by default): the temperature is
averaged over depth in windows of <i>Window width</i> centred every
<i>Window step</i> (auto = the width, windows side by side) <i>before</i>
∂T/∂z and N, so the noise is reduced before the square root; the chain is
not smoothed. The <b>Run</b> button is in the Channels box.</li>
<li>Results: <i>Mean N profiles</i> (time mean ± one standard deviation per
record) and <i>N(z, t) maps</i>. The mean N is used by the frequency-domain
step (overlay and N band).</li>
</ul>

<h2>Multi-layer decomposition</h2>
<ul>
<li><b>Layering</b>: <i>One layer</i> (the whole column; nothing to do),
<i>Two layers</i> or <i>Three layers</i>; the box of the method appears
below.</li>
<li><b>Smoothing</b> (top of each box, off by default): T averaged over depth
(<i>Window width</i>, <i>Window step</i>, auto = the width) before the
interfaces are found;
the maps show the unsmoothed temperature.</li>
<li><b>Two layers</b>: <i>From thermocline LeXPLORE</i> (interface = the
variable <code>thermocline_depth</code> of the LeXPLORE files, interpolated
linearly in time onto the time base of every channel selected; NaN before
the first and after the last chain value; for chain data without this
variable, the depth of the largest |dT/dz| of every chain profile) or
<i>From isotherm</i> (depth of <i>T isotherm</i> in each record);
<b>Run</b>.</li>
<li><b>Three layers</b>: <i>From isotherms</i> (Z1 = depth of the <i>Top
isotherm</i>, Z2 = depth of the <i>Bottom isotherm</i>; the top one must be
warmer) or <i>Best fit</i> (outer layers fitted as straight lines from both
ends of the profile within <i>Line-fit tolerance</i>, with at least <i>Min.
points per layer</i>, interfaces at least <i>Min. interface gap</i> apart);
<b>Run</b>.</li>
<li><b>Individual profiles</b> (two and three layers): the shared list of
profiles, the toggle <i>Select individual profiles on the map</i> (a click
on the Layers maps) and <b>Update</b>.</li>
<li>Results: <i>Layers</i>, the temperature maps with Z1 (solid) and Z2
(dashed) and the individual profiles marked; one figure <i>Individual
profile P1</i>, <i>P2</i>, … per profile, with one panel per record (two
columns at most): the temperature profile, the interfaces at that time
(dotted, labelled Z1, Z2) and the layer model (dashed). With <i>Best
fit</i>, the model is the continuous three-layer fit of the profile, as in
the notebook: straight lines fitted in the top and bottom layers, joined by
the segment between Z1 and Z2 (slopes and rms in the panel title); with the
other methods, a straight line fitted by least squares in each layer. Mean
± std of the interfaces in the log. The layers then appear in
the <i>Layer</i> lists of the following steps; running the decomposition
again marks the steps that use Z1 and Z2 as outdated.</li>
</ul>

<h2>Spectral analysis – frequency domain</h2>
<p>Box <b>Channels</b> (shared), then two tabs, each with its own options,
<b>Run</b> and <b>Display</b>.</p>
<h3>Tab Temperature at each depth</h3>
<ul>
<li><b>Options</b>: <i>Layer</i>, <i>Smooth N</i> (?) with <i>N window
width / step</i> (smoothing of the N overlay; step auto = width),
<b>Run</b>; the latitude of f is set in Advanced › Physical parameters. At every depth, the temperature anomaly is Fourier-transformed
over time (amplitude 2|X|/n). Result: <i>Frequency × depth</i> maps, with
the time-mean N profile (white) and the Coriolis frequency
f = 2Ω sin φ / 2π (dashed).</li>
<li><b>Display</b>: shading and colour map; <i>Longest period plotted</i>
and <i>Longest period for colours</i> (<i>auto</i> = every period);
<i>Colour limits</i> (<i>None</i>: 50th–99.5th percentile; <i>Instrument
resolution</i>: lower limit = half the resolution; <i>User defined</i>:
lower and upper limits); <i>x axis</i> (frequency in Hz or period in hours)
and its scale (log or linear).</li>
</ul>
<h3>Tab Isotherm depth</h3>
<ul>
<li><b>Options</b>: <i>Isotherm</i>, <i>Poincaré profiles</i> (?) (<i>Same
as DTS time window</i> or one of the windows W1, W2, …),
<b>Run</b> (lake width, g and equation of state: Advanced › Physical
parameters). The depth of the isotherm is Fourier-transformed over the time
window of the Channels box (no layer). Results: <i>Depth vs time</i> and
<i>Spectrum</i> (brought forward after Run).</li>
<li>Marks on the spectrum: f (Coriolis); the range of the time-mean N over
the depths swept by the isotherm (grey band); the DTS vertical resolution
(dotted); the <b>Poincaré V1 band</b> (pink): for every profile of the
Poincaré window, a two-layer model (interface at the largest gradient,
reduced gravity g′ = g Δρ / ρ₀ from the layer temperatures and the
equation of state) gives the wave speed c and
ω² = f² + (c π / width)².</li>
<li><b>Display</b>: <i>Use the instrument resolution</i> (half the
resolution, converted to a depth with the gradient at the isotherm, sets the
lower bound of the amplitude axis), <i>x axis</i> (frequency, with the
period on the top axis, or period in hours) and its scale.</li>
</ul>

<h2>Spectral analysis – wavenumber domain</h2>
<ul>
<li><b>Channels</b> (with <i>Layer</i> and <b>Run</b>): every profile is
Fourier-transformed along depth (anomaly, amplitude 2|X|/n). The chain is
first interpolated on a uniform grid at its median sensor spacing.</li>
<li><b>Individual profiles</b>: the shared list, the toggle <i>Select
individual profiles on the map</i> (a click on the Time × k_z map) and
<b>Update</b>.</li>
<li><b>Display</b>: shading, colour map, <i>Longest wavelength plotted</i>
and <i>for colours</i> (each with a box <i>full spectrum</i>: ticked, every
wavenumber of the profiles is used), <i>Vertical axis</i> (wavelength or wavenumber),
<i>Instrument resolution</i> (half the resolution = lower bound of the
colour scale).</li>
<li>Results: <i>Time × k_z</i> (maps, profiles as dotted lines) and <i>FFT of
the individual profiles</i> (one panel per record, one curve per
profile).</li>
<li><b>Wavenumber range and scaling law</b>: <i>k min</i> and <i>k max</i>
(1/m; <i>none</i> = the end of the spectrum) set a range, shaded in grey on
the spectra of the individual profiles; the toggle <i>Select the range on
the spectra</i> sets them by a horizontal drag on that figure (whatever the
axis, wavelength or wavenumber). <b>Fit scaling</b> fits a scaling law
A = a k<sup>b</sup> (least squares on log10 A vs log10 k) to every curve of
every panel within the range: the laws are drawn dashed, in the colour of
their curve, with a and b in the legend, and listed in the log.</li>
</ul>

<h2>2D FFT of the water column</h2>
<ul>
<li><b>Channels</b>: channels, chain, time window, <b>Layers</b> (tick boxes:
<i>Whole column</i> and the layers of the last Multi-layer decomposition;
several can be ticked) and <b>Run</b>. For every channel and every layer
ticked, 2D Fourier transform over depth and time of the depths between the
time-mean interfaces of the layer (each depth demeaned and detrended),
amplitude 2|F|/(nz nt); the +k_z and −k_z amplitudes are summed (both
vertical directions together).</li>
<li><b>Display</b>: shading, colour map, <i>Vertical axis</i> (wavenumber or
wavelength), <i>Horizontal axis</i> (frequency or period), <i>Instrument
resolution</i>.</li>
<li>Results: one figure <i>2D FFT – CH1</i>, … per channel (and the chain),
with one panel per layer ticked, two columns at most; one colour scale for
all the figures.</li>
</ul>

<h2>Temperature-gradient maps</h2>
<ul>
<li><b>Channels</b> (with <i>Layer</i> and <b>Run</b>): vertical gradient
∂T/∂z of every channel ticked; <i>Smooth T before dT/dz</i> (?) first
averages the temperature over depth windows (<i>Window width</i>, <i>Window
step</i>, auto = the width), as for the Brunt–Väisälä frequency.</li>
<li><b>Individual profiles</b>: the shared list, the toggle <i>Select
individual profiles on the map</i> (a click on the gradient maps) and
<b>Update</b>.</li>
<li>Results: <i>Maps</i> (one panel per channel, chain first, common grey
colour scale, profiles marked) and <i>Individual profiles</i> (one panel per
profile, three columns at most, the gradient of every channel, Z1 and Z2
dashed when the Multi-layer decomposition gave them).</li>
</ul>

<h2>Staircases detection</h2>
<ul>
<li><b>Channels</b>: channels and chain; its <i>Time window</i> and
<i>Layer</i> apply to the detection only. For a layer of the Multi-layer
decomposition, its interfaces are taken at each profile time (not the time
mean).</li>
<li><b>Individual profiles</b>: the shared list, the toggle <i>Select
individual profiles on the map</i> (a click on the T(z, t) maps of the step)
and <b>Update</b> (runs the detection).</li>
<li><b>Detection</b>: each profile is smoothed by a running mean over
<i>Smoothing length</i> (?); a step is a run of depths where |dT/dz| is
below a threshold, at least <i>Min. step thickness</i> thick. Threshold, one
of two choices (only the value of the choice ticked is editable):
<i>Threshold from the gradient factor</i> (|dT/dz| below <i>Gradient
factor</i> (?) × the mean gradient of the layer; follows the stratification
of each profile) or <i>Threshold from a maximum dT/dz</i> (|dT/dz| below
<i>Max |dT/dz|</i>, in K/m, the same for every profile). <b>Run</b>.</li>
<li>Results: <i>Maps</i> (T(z, t) of the channels, profiles marked) and
<i>Staircases</i>: one panel per profile, two columns at most, every channel
on the same panel (thin line: the profile; thick vertical segments: the
steps at their mean temperature; number of steps per channel in the title);
the depth axis of each panel spans the layer at that time.</li>
<li><b>Seismogram-like profiles</b> (last box, button <b>Plot</b>): every
profile of the metalimnion (between Z1 and Z2) in a time window, demeaned and
shifted by <i>Spacing</i> per profile, one figure per channel ticked (and
the chain). <i>Time window</i>: one of the windows W1, W2, … (every profile
inside it) or <i>Start and duration below</i>; <i>Start</i> is a drop-down of
the individual profiles in which a time can also be typed. <i>Step</i>
(minutes, below <i>Duration</i>; <i>auto</i> = every profile) sets the time
between the successive profiles plotted: the profile nearest to every
multiple of the step, from the first profile of the duration or of the time
window. Z1 and Z2 come
from the Multi-layer decomposition with three layers, else from the default
best three-layer fit (the log says so).</li>
</ul>

<h2>Advanced › Physical parameters…</h2>
<ul>
<li>A window (it can stay open) with every physical parameter used by the
steps, grouped: <i>Constants</i> (g, Ω), <i>Lake</i> (latitude, lake
width, position of LéXPLORE and the LéXPLORE radius within which an STC
profile counts as taken at LéXPLORE), <i>Water</i> (salinity; <i>Density and expansion</i>: <b>Equation of
state</b> — parabolic freshwater law or UNESCO EOS-80 at one atmosphere,
with ρ₀, T_md and b — or <b>Fixed values</b> of ρ and α) and <i>Sound
speed</i> (formula: UNESCO (Chen &amp; Millero 1977), Medwin (1975) or
Mackenzie (1981); temperature used when T is off). Hover a name for its
meaning and default.</li>
<li><b>Apply</b> uses the values from the next step run (the steps already
run keep their results); <b>Reset to defaults</b> shows the defaults (then
Apply). The values are saved with the analysis settings and restored when
they are opened; <i>File › Reset all</i> puts them back to the defaults.</li>
</ul>

<h2>Advanced › Save variables…</h2>
<ul>
<li>Every variable in memory, in four categories: <b>Preprocessing
variables</b> (the variables without the prefix A_), <b>Analysis
variables</b> (A_…), <b>Physical parameters</b> (one entry per parameter)
and <b>STC variables</b> (the STC profiles read: A_STC). Each line shows the
description, format, size and memory.</li>
<li>Tick boxes at every level: a category ticks all its variables, a
variable ticks all its entries, and every entry of a dictionary variable
(a channel, an STC profile, …, down to three levels) has its own box; a
partly ticked box shows that only some entries are chosen. Buttons
<i>All</i>, <i>None</i>, <i>Expand all</i>, <i>Collapse</i>,
<i>Refresh</i>; the list is updated after every step.</li>
<li><b>Save…</b> asks the file name, the folder and the format (npz,
NetCDF, HDF5, txt, csv, MATLAB) and writes the entries ticked (a
dictionary keeps only its entries ticked; the physical parameters go in
the group PHYSICAL_PARAMETERS; txt and csv: one table per array or group of
columns, plus an index file).</li>
</ul>

<h2>Advanced › Sound speed maps</h2>
<ul>
<li><b>STC profiles and sound speed</b> (first box):
<ul>
<li><i>STC folder</i> (?), <i>DTS folder</i> (?) and <i>LéXPLORE
folder</i> (?) (the chain files); their defaults come from
<i>default_paths.ini</i> (README, "Default folders"). The DTS and LéXPLORE folders
have a tick box in front of their name: unticked, that data set is left out
of the STC figures (and the DTS columns of the list are empty). Each (?)
describes the instrument and its sampling, followed by the native depth
and time resolution of the data found in the folder (computed when the (?)
is clicked). The list is updated as soon as a folder or a tick box is
changed.</li>
<li><i>Individual STC profiles</i>: one CSV file per profile of the
Valeport SWiFT SVP; columns <i>Start (UTC)</i> (dd.mm hh:mm:ss), <i>DTS
time shift</i> (time from the start of the STC profile to the closest
Combined DTS profile of the DTS folder; + = DTS after), <i>LeXPLORE time
shift</i> (the same for the closest chain profile of the LéXPLORE folder),
<i>Distance</i> from LéXPLORE (position of the .vp2 header against the
LéXPLORE position of the physical parameters), <i>Duration</i> (first to
last sample), <i>Descent</i> (mean descent speed, (z_max − z_first) /
(t(z_max) − t_first)), <i>DTS record</i> (the preprocessed record that
holds the closest DTS profile) and <i>File</i>; a time-shift column is
empty when its data set is unticked; buttons All / None.</li>
<li><i>Only STC profiles at LéXPLORE</i> (?): Load and plot uses only the
profiles ticked whose position lies within the <i>LéXPLORE radius</i> of
the physical parameters (100 m by default; see the column Distance).</li>
<li>DTS: the <b>Combined</b> channel only, the profile closest in time to
the start of each STC profile, searched in every preprocessed file (.nc
with a Combined channel) of the DTS folder and its sub-folders — no need to
load the data first.</li>
<li>Tick boxes <i>Temperature T</i> (off: the constant reference
temperature of the physical parameters), <i>Pressure P</i> (P = ρ̄ g z, ρ̄
the mean density of the profiles from the equation of state or the fixed
density; off: P = 0) and <i>Salinity S</i> (the salinity of the physical
parameters, 0 PSU by default; off: S = 0).</li>
<li><b>Load and plot</b> (one button): reads the STC profiles ticked and
their closest DTS profiles and draws every figure: <i>STC positions</i>
(the whole lake and a zoom; lake outline <i>Lake_Geneva_outline.geojson</i>
in the STC folder), one figure per profile ticked — temperature vs depth
(left) and sound speed vs depth (right): the STC (measured T and c), c
recalculated from the STC temperature (dotted) and the closest Combined DTS
profile with its recalculated sound speed (legend: record and time shift)
and, when the LéXPLORE chain has a profile within two of its time steps
(about 20 min) of the STC start, the closest chain profile (pink, with
markers) and the sound speed recalculated from it — and, below, two RMS panels: the RMS over depth windows
(<i>RMS window</i>, 2 m by default) of the temperature differences (DTS −
STC, chain − STC) and of the sound-speed differences (STC recalculated −
STC measured, DTS − STC measured, chain − STC measured); every label gives the native depth resolution (Δz) of its data set and,
for the DTS and the chain, its time shift
— and the <i>Sound speed maps</i>: c(depth, time) of the Combined channel
of the data loaded in <i>Data analysis › Load preprocessed data</i>, the
start of every STC profile ticked inside the record as a dashed line (the
map is left out, with a note in the log, when no data are loaded).</li>
</ul></li>
<li><b>Resampling and display</b>: <i>Resample over depth</i> (?) with
<i>Window size</i> and <i>Window step</i> (auto = the size: the STC and DTS
profiles of the STC figures averaged over depth windows; the maps are not
resampled), <i>RMS window</i> (?) (depth window of the RMS curves of the
STC figures), <i>Smooth shading</i>, <i>Shading kind</i>, <i>Colour map</i>
and one button <b>Update</b>, which draws again the figures already made
(STC profiles and sound-speed maps) with these options.</li>
</ul>

<h2>Analysis report</h2>
<ul>
<li><b>Run</b> writes the markdown report (<i>Report file</i>) and the
figures of the analysis steps run (<i>Figure folder</i>) in the
<i>Output folder</i> (empty = the configuration folder of the file loaded):
data set, instrument resolution, stratification, frequency-domain results
(f, Poincaré band, dominant isotherm periods) and the layer interfaces.</li>
</ul>
""" + COMMON
