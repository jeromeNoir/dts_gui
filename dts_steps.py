"""dts_steps.py -- the steps of the DTS GUI (preprocessing and analysis).

Every item of the two menus is one function ``run(session, p)``:

    session  the Session object holding the results of the steps already run
             (session.data, a dictionary with the names used in the
             notebooks: TIME, Z, T_USHAPED_CALIBRATED, DATA_LEXPLORE, ...)
    p        the values of the left panel of the step (dictionary)

and returns a list of (tab title, matplotlib Figure).  The computations call
dts_core; the figures are built by gui_figures.  Printed messages go to the
log of the GUI.

Time convention: every time entered by the user is UTC, except the
reference local time of the instrument-clock correction (step pre.0).
"""

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import dts_core as core
import channel_names as cn
import gui_figures as figs


# ---------------------------------------------------------------------------
# session and small helpers
# ---------------------------------------------------------------------------
class TrackedData(dict):
    """The session variables; while a step runs, the names it reads or
    writes are recorded in ``used`` (Save data of a figure saves them)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.used = None                 # set while a step runs

    def _use(self, name):
        if self.used is not None:
            self.used.add(name)

    def __getitem__(self, name):
        self._use(name)
        return super().__getitem__(name)

    def get(self, name, default=None):
        if name in self:
            self._use(name)
        return super().get(name, default)

    def __setitem__(self, name, value):
        self._use(name)
        super().__setitem__(name, value)

    def setdefault(self, name, default=None):
        self._use(name)
        return super().setdefault(name, default)

    def update(self, *args, **kwargs):
        for name in dict(*args, **kwargs):
            self._use(name)
        super().update(*args, **kwargs)


class Session:
    """Results shared between the steps."""

    def __init__(self):
        self.data = TrackedData()
        self.variables_used = {}     # figure owner -> variables of its run
        self.figures = {}            # step id -> [(title, Figure)]
        self.three_layer_cache = {}  # (record, parameters) -> fit
        self.params_used = {}        # step id -> inputs of its last run
        self.origin = {}             # variable -> step that first made it

    def require(self, *names):
        missing = [name for name in names if name not in self.data]
        if missing:
            raise RuntimeError(f"missing results {missing}: run the "
                               f"previous steps first")
        return [self.data[name] for name in names]


class StepError(Exception):
    """Error of the user inputs, shown without a traceback."""


def utc(text):
    """'YYYY-MM-DD hh:mm:ss' (UTC) -> numpy datetime64 (ms); None/'' -> None."""
    if text in (None, ""):
        return None
    return np.datetime64(str(text).strip().replace(" ", "T"), "ms")


def stamp(value):
    return str(np.datetime64(value, "s")).replace("T", " ")


def nearest_index(times, when):
    return int(np.argmin(np.abs(times - when)))


DISPLAY_DEFAULT = dict(IS_SHADING=False, SHADING="gouraud", CMAP="seismic")


# options of Save, by the depth calibration done
SHIFT_OPTIONS = {"LeXPLORE chain": ["Shift in Z and T", "Shift in Z only"],
                 "manual": ["Shift in Z"]}


def display_of(session):
    """Display options of the preprocessing maps (set in the figure list:
    smooth shading, shading kind, colour map)."""
    options = dict(DISPLAY_DEFAULT)
    options.update(getattr(session, "display", {}) or {})
    return options


def chain_for_maps(session):
    """The LeXPLORE chain record when it is loaded, else None."""
    S = session.data
    return S.get("DATA_LEXPLORE") if S.get("IS_LEXPLORE_DATA_AVAILABLE") \
        else None


def shading(p):
    kind = p.get("SHADING", "nearest")
    return kind if p.get("IS_SHADING") else "nearest"


def instants(rows):
    """Table rows (label, UTC time) -> list of (label, datetime64)."""
    result = []
    for label, text in rows:
        if not str(text).strip():
            continue
        try:
            result.append((label or text, utc(text)))
        except ValueError:
            raise StepError(f"cannot read the time {text!r} "
                            f"(expected YYYY-MM-DD hh:mm:ss)")
    return result


def selected(p, available, key="CHANNELS"):
    """Channels ticked in the panel that exist in the data."""
    chosen = [c for c in (p.get(key) or []) if c in available]
    if not chosen:
        raise StepError(f"no channel selected (available: "
                        f"{', '.join(available)})")
    return chosen


nan_mean_rows = core.nan_mean_rows        # (moved to dts_core in 3.02)


# ===========================================================================
# PREPROCESSING
# ===========================================================================
def crop_chain(chain, keep):
    """A chain record cut in time by the boolean mask ``keep`` (every
    variable of the files included)."""
    out = {"time": chain["time"][keep], "depth": chain["depth"],
           "temperature": chain["temperature"][:, keep]}
    if chain.get("variables"):
        out["variables"] = core.crop_chain_variables(chain["variables"],
                                                     keep)
    return out


def chain_variables_text(chain):
    """One line per variable of the LeXPLORE files (name, units, long
    name, shape)."""
    if not chain:
        return ""
    lines = ["temp  [degC]  temperature  (depth × time) - used as T"]
    for name, item in (chain.get("variables") or {}).items():
        shape = " × ".join(str(n) for n in np.shape(item["data"]))
        dims = " × ".join(item["dims"])
        lines.append(f"{name}  [{item.get('units', '')}]  "
                     f"{item.get('long_name', name)}  ({dims}: {shape})")
    return "\n".join(lines)


def _chain_over(chain_root, start, end):
    """(available?, chain record, status text) of the LeXPLORE chain over
    [start, end] (UTC).  The status says why the chain is not available."""
    if not chain_root:
        status = "no chain folder given"
    elif not os.path.isdir(chain_root):
        status = f"chain folder not found: {chain_root}"
    else:
        try:
            chain_time, chain_depth, chain_T, chain_vars = \
                core.read_lexplore_matrix_fromDisk(chain_root, start, end,
                                                   with_variables=True)
        except ImportError as error:
            status = (f"cannot read NetCDF files ({error}); install the "
                      f"module with:  pip install netCDF4")
        except Exception as error:                      # noqa: BLE001
            status = f"error while reading the chain: " \
                     f"{type(error).__name__}: {error}"
        else:
            if chain_time.size:
                status = (f"available: {chain_time.size} profiles, "
                          f"{stamp(chain_time[0])} -> {stamp(chain_time[-1])}"
                          f" UTC, {chain_depth.size} depths")
                print(f"LeXPLORE chain {status}")
                print("LeXPLORE variables kept: " + ", ".join(
                    ["temp"] + list(chain_vars)))
                return True, {"time": chain_time, "depth": chain_depth,
                              "temperature": chain_T,
                              "variables": chain_vars}, status
            status = (f"the chain files do not cover the DTS window "
                      f"{stamp(start)} -> {stamp(end)} UTC")
    print(f"WARNING: LeXPLORE chain not available - {status}.\n"
          f"Download the chain data of this period from Datalakes into the "
          f"chain folder, or calibrate the depth by hand (Depth Calibration "
          f"› Manual).")
    return False, {}, status


def temperature_root(root):
    """The temperature folder of the XT (holding the configurations).  A
    root given as the XT data folder (older settings) is accepted: its
    'temperature' sub-folder is used."""
    root = os.path.normpath(root or "")
    inner = os.path.join(root, "temperature")
    if os.path.basename(root) != "temperature" and os.path.isdir(inner):
        return inner
    return root


def log_folder(root):
    """The log folder of the XT: next to the temperature folder."""
    return os.path.join(os.path.dirname(temperature_root(root)), "log")


def pre_1_load(session, p):
    """Load data: inventory, clock correction, chain, raw cache of every
    profile, first profile of each channel truncated."""
    S = session.data
    data_folder = os.path.join(temperature_root(p["ROOT"]),
                               p["CONFIGURATION"])
    log_dir = log_folder(p["ROOT"])
    log_db = os.path.join(log_dir, "log.db")
    print(f"log folder: {log_dir}"
          + ("" if os.path.isfile(log_db) else " (no log.db found)"))
    if not os.path.isdir(data_folder):
        raise StepError(f"configuration folder not found: {data_folder}")
    channels_available = sorted(
        name for name in os.listdir(data_folder)
        if os.path.isdir(os.path.join(data_folder, name))
        and not name.startswith((".", "DTS_preprocessing_report")))
    channels = [c for c in channels_available
                if cn.display_name(c) in selected(
                    p, [cn.display_name(c) for c in channels_available])]

    if p["IS_TIME_CORRECTION"]:
        reference_UTC = core.local_to_UTC(p["reference_local_time"],
                                          verbose=False)
        utc_offset = core.instrument_clock_offset(
            p["reference_utc_time_XT13002"], reference_UTC)
        print(f"clock offset: +{utc_offset / np.timedelta64(1, 'D'):.6f} "
              f"days (reference {p['reference_local_time']} local = "
              f"{stamp(reference_UTC)} UTC)")
    else:
        utc_offset = None
        print("no time correction: the time stamps are used as written by "
              "the instrument clock")

    summary = core.build_summary(data_folder, utc_offset=utc_offset,
                                 rebuild=p["REBUILD_SUMMARY"])
    summary = summary[summary["channel"].isin(channels)]
    first_last = pd.concat([files.iloc[[0, -1]].drop_duplicates()
                            for _, files in summary.groupby("channel",
                                                            sort=True)])
    print("\nfirst and last file of each channel:")
    print(first_last.to_string(index=False))

    time_column = ("time corrected (UTC)" if p["IS_TIME_CORRECTION"]
                   else "time original")
    window_start = np.datetime64(pd.to_datetime(summary[time_column]).min())
    window_end = np.datetime64(pd.to_datetime(summary[time_column]).max())
    print(f"\nDTS measurement window: {stamp(window_start)} -> "
          f"{stamp(window_end)} UTC")

    if p.get("USE_LEXPLORE", True):
        is_lexplore, data_lexplore, chain_status = _chain_over(
            p["LEXPLORE_ROOT"], window_start, window_end)
    else:
        is_lexplore, data_lexplore = False, {}
        chain_status = "not used ('Use LeXPLORE temperature' unticked)"
        print("LeXPLORE temperature not used (box unticked): the depth will "
              "be calibrated by hand (Depth Calibration › Manual)")

    raw = core.read_datasets(data_folder, utc_offset=utc_offset)
    raw = {channel: record for channel, record in raw.items()
           if channel in channels}

    print("\nraw cache (every profile of every channel):")
    raw_cache = core.build_raw_cache(data_folder, channels,
                                     rebuild=p.get("REBUILD_RAW_CACHE", False))
    # the folders 'channel n' are called 'CHn' from here on
    raw, raw_cache = cn.rename_keys(raw), cn.rename_keys(raw_cache)
    channels = [cn.display_name(c) for c in channels]
    channels_available = [cn.display_name(c) for c in channels_available]

    keys = ["configuration", "comment", "status", "double_ended",
            "forward_channel", "reverse_channel", "paired_channel",
            "sampling_interval", "measurement_length", "acquisition_time",
            "acquisition_time_cfg", "measurement_interval", "gamma",
            "diff_loss_dB_km", "diff_loss_mode", "ref_temp", "probe1_temp",
            "probe2_temp", "time_start", "time_end", "fibre_ok"]
    table = {}
    for channel, record in raw.items():
        column = {key: record.get(key) for key in keys}
        column["dx (m, from x axis)"] = \
            f"{float(np.median(np.diff(record['x']))):.4f}"
        column["samples per profile"] = int(record["x"].size)
        entry = raw_cache[channel]
        times = core.raw_mid_times(entry, utc_offset)
        column["profiles in the folder"] = int(entry["seen"].size)
        column["profiles read"] = int(entry["files"].size)
        column["first profile (UTC)" if utc_offset is not None
               else "first profile (XT clock)"] = stamp(times[0])
        column["last profile (UTC)" if utc_offset is not None
               else "last profile (XT clock)"] = stamp(times[-1])
        column["sampling period (s)"] = (
            f"{np.median(np.diff(times)) / np.timedelta64(1, 's'):.0f}"
            if times.size > 1 else "")
        table[channel] = {k: ("" if v is None else str(v))
                          for k, v in column.items()}
    configuration = pd.DataFrame(table)
    configuration.loc["LeXPLORE chain"] = chain_status
    configuration.loc["log folder"] = (
        log_dir + ("" if os.path.isfile(log_db) else " (no log.db)"))
    print("\nconfiguration of each channel: see the 'Configuration' tab")

    truncated = {}
    for channel, record in raw.items():
        length = float(record["measurement_length"])
        keep = (record["x"] >= 0.0) & (record["x"] <= length)
        cut = dict(record)
        cut["x"] = record["x"][keep]
        for curve in ("st", "ast", "rst", "rast", "tmp"):
            if record.get(curve) is not None:
                cut[curve] = record[curve][keep]
        truncated[channel] = cut
        print(f"{channel}: truncated to 0 - {length:g} m "
              f"({int(keep.sum())}/{record['x'].size} samples kept)")

    for key in [k for k in S if not k.startswith("A_")]:
        S.pop(key)                  # a new data selection starts a new run
    S.update(DATA_FOLDER=data_folder, LOG_FOLDER=log_dir, CHANNELS=channels,
             CHANNELS_AVAILABLE=channels_available, UTC_OFFSET=utc_offset,
             IS_TIME_CORRECTION=bool(p["IS_TIME_CORRECTION"]),
             REFERENCE_LOCAL_TIME=p["reference_local_time"],
             LEXPLORE_ROOT=p["LEXPLORE_ROOT"],
             IS_LEXPLORE_DATA_AVAILABLE=is_lexplore,
             DATA_LEXPLORE=data_lexplore, DATA_DTS_RAW=raw,
             DATA_DTS_RAW_TRUNCATED=truncated, RAW_CACHE=raw_cache,
             USE_LEXPLORE=bool(p.get("USE_LEXPLORE", True)),
             LEXPLORE_STATUS=chain_status,
             DTS_WINDOW=(window_start, window_end),
             CONFIGURATION_TABLE=configuration)
    return [("Configuration", configuration),
            ("Truncation", figs.truncation(raw, truncated))]


def pre_1_mirror(session, p):
    """Mirror distance of every profile (from the raw cache), fold of the
    first profile."""
    S = session.data
    truncated, raw_cache, utc_offset, channels = session.require(
        "DATA_DTS_RAW_TRUNCATED", "RAW_CACHE", "UTC_OFFSET", "CHANNELS")
    max_depth, max_depth_time, max_depth_all = {}, {}, {}
    for channel in channels:
        length = float(truncated[channel]["measurement_length"])
        entry = raw_cache[channel]
        distances = core.max_depth_from_raw(
            entry, 0.0, length, scan=p.get("SCAN"), step=p.get("STEP"),
            halfwidth=p["HALFWIDTH"])
        times = core.raw_mid_times(entry, utc_offset)
        ok = np.isfinite(distances)
        max_depth[channel] = float(np.mean(distances[ok]))
        max_depth_time[channel], max_depth_all[channel] = \
            times[ok], distances[ok]
        print(f"{channel}: mirror distance {max_depth[channel]:.3f} m "
              f"(std {np.std(distances[ok]):.3f} m, {int(ok.sum())} "
              f"profiles)")

    folded = {}
    for channel in channels:
        x, T = truncated[channel]["x"], truncated[channel]["tmp"]
        distance = max_depth[channel]
        above = x <= distance
        z, T_down = x[above], T[above]
        T_up = core.mirror(x, T, distance, z)
        both = np.isfinite(T_down) & np.isfinite(T_up)
        T_mean = np.where(both, 0.5 * (T_down + T_up),
                          np.where(np.isfinite(T_down), T_down, T_up))
        folded[channel] = (z, T_down, T_up, T_mean)

    S.update(MAX_DEPTH=max_depth, MAX_DEPTH_TIME=max_depth_time,
             MAX_DEPTH_ALL=max_depth_all, FOLDED_FIRST=folded,
             CHANNELS_FOLDED=channels)
    return [("Mirror distance vs time",
             figs.mirror_distance(max_depth_time, max_depth_all, max_depth)),
            ("Uncalibrated Profiles", figs.folded_profiles(folded))]


def pre_1_concat(session, p):
    """All the profiles of each channel folded on one common grid."""
    S = session.data
    truncated, raw_cache, utc_offset, max_depth = session.require(
        "DATA_DTS_RAW_TRUNCATED", "RAW_CACHE", "UTC_OFFSET", "MAX_DEPTH")
    channels = list(max_depth)
    max_depth_mean = float(np.mean([max_depth[c] for c in channels]))
    dz = float(np.median(np.diff(truncated[channels[0]]["x"])))
    z_common = np.arange(0.0, max_depth_mean, dz)
    print(f"common mirror distance {max_depth_mean:.3f} m, common grid: "
          f"{z_common.size} depths, dz = {dz:.4f} m")
    TIME, Z, T_mean = {}, {}, {}
    for channel in channels:
        length = float(truncated[channel]["measurement_length"])
        entry = raw_cache[channel]
        _, _, T_mean[channel] = core.fold_raw(entry, 0.0, length,
                                              max_depth_mean, z_common)
        TIME[channel] = core.raw_mid_times(entry, utc_offset)
        Z[channel] = z_common
        print(f"{channel}: {TIME[channel].size} profiles, "
              f"{stamp(TIME[channel][0])} -> {stamp(TIME[channel][-1])}")
    if len(channels) >= 2:
        # channel 'mean': profile-by-profile mean of the channels on the
        # common grid (profiles paired by index - the channels sample a few
        # minutes apart -, time stamp = mean of the paired stamps, NaN where
        # one channel is NaN)
        n_pairs = min(TIME[c].size for c in channels)
        stamps = np.stack([TIME[c][:n_pairs].astype("int64")
                           for c in channels])
        TIME[cn.COMBINED] = stamps.mean(axis=0).round().astype(
            "int64").astype(TIME[channels[0]].dtype)
        Z[cn.COMBINED] = z_common
        T_mean[cn.COMBINED] = np.mean(np.stack([T_mean[c][:, :n_pairs]
                                           for c in channels]), axis=0)
        print(f"channel '{cn.COMBINED}' = mean of {', '.join(channels)}: "
              f"{n_pairs} profiles")
    else:
        print("one channel only: no 'mean' channel")
    S.update(MAX_DEPTH_mean=max_depth_mean, dz=dz, z_common=z_common,
             TIME=TIME, Z=Z, T_MATRIX_mean=T_mean)
    return pre_1_replot(session, p)


def pre_1_replot(session, p):
    """Redraw the T(z, time) maps with the display options of the figure
    list (no computation); the LeXPLORE chain on top when loaded."""
    TIME, Z, T_mean, max_depth_mean = session.require(
        "TIME", "Z", "T_MATRIX_mean", "MAX_DEPTH_mean")
    options = display_of(session)
    return [("T(z, time) maps",
             figs.connector_maps(TIME, Z, T_mean, max_depth_mean,
                                 shading(options), options["CMAP"],
                                 chain_for_maps(session)))]


def pre_2_1(session, p):
    """Joint (Z, T) fit of the DTS onto the LeXPLORE chain."""
    S = session.data
    if not S.get("IS_LEXPLORE_DATA_AVAILABLE"):
        if not S.get("USE_LEXPLORE", True):
            raise StepError("'Use LeXPLORE temperature' is unticked in Load "
                            "Data: tick it and press Load again, or use the "
                            "manual calibration")
        # Load found no chain: try again (folder fixed, module installed..)
        print("LeXPLORE chain not loaded by Load raw data "
              f"({S.get('LEXPLORE_STATUS', 'unknown reason')}) - reading it "
              f"again from {S.get('LEXPLORE_ROOT')}")
        session.require("DTS_WINDOW")
        available, chain, status = _chain_over(S.get("LEXPLORE_ROOT"),
                                               *S["DTS_WINDOW"])
        S["LEXPLORE_STATUS"] = status
        if not available:
            raise StepError(f"LeXPLORE chain not available: {status}")
        S.update(IS_LEXPLORE_DATA_AVAILABLE=True, DATA_LEXPLORE=chain)
    TIME, Z, T_mean, chain = session.require("TIME", "Z", "T_MATRIX_mean",
                                             "DATA_LEXPLORE")
    channels = selected(p, list(T_mean))

    periods = {"LeXPLORE": np.median(np.diff(chain["time"]))}
    for channel in channels:
        periods[channel] = np.median(np.diff(TIME[channel]))
    base_name = max(periods, key=lambda name: periods[name])
    period_common = periods[base_name]
    for name, period in periods.items():
        print(f"{name}: sampling period "
              f"{period / np.timedelta64(1, 's'):.0f} s")
    print(f"common time base: {base_name}")

    window_start = max(chain["time"][0],
                       max(TIME[c][0] for c in channels))
    window_end = min(chain["time"][-1],
                     min(TIME[c][-1] for c in channels))
    base_time = chain["time"] if base_name == "LeXPLORE" else TIME[base_name]
    in_window = (base_time >= window_start) & (base_time <= window_end)
    time_common = base_time[in_window]
    if time_common.size == 0:
        raise StepError("the chain and the DTS records do not overlap")
    print(f"common window: {stamp(time_common[0])} -> "
          f"{stamp(time_common[-1])} UTC, {time_common.size} steps")

    windows = [(start, end) for start, end in p.get("TIME_WINDOWS") or []
               if str(start).strip() and str(end).strip()]
    if not windows:
        in_fit = np.ones(time_common.size, bool)
    else:
        in_fit = np.zeros(time_common.size, bool)
        for start, end in windows:
            in_fit |= (time_common >= utc(start)) & (time_common <= utc(end))
        print(f"fit restricted to {int(in_fit.sum())} of {time_common.size} "
              f"steps in {len(windows)} time window(s) (UTC)")
        if not in_fit.any():
            raise StepError("no profile of the common window falls inside "
                            "the time windows - widen them")

    if base_name == "LeXPLORE":
        chain_T = chain["temperature"][:, in_window]
    else:
        print("LeXPLORE: ", end="")
        chain_T = core.resample_time_mean(chain["time"],
                                          chain["temperature"], time_common,
                                          window=period_common)
    dts_resampled = {}
    for channel in channels:
        if base_name == channel:
            dts_resampled[channel] = T_mean[channel][:, in_window]
        else:
            print(f"{channel}: ", end="")
            dts_resampled[channel] = core.resample_time_mean(
                TIME[channel], T_mean[channel], time_common,
                window=period_common)

    time_fit = time_common[in_fit]

    # chain depths taking part in the fit, and their temperature contrast
    z_min, z_max = p.get("Z_FIT_MIN"), p.get("Z_FIT_MAX")
    fit_depths = np.ones(chain["depth"].size, bool)
    if z_min is not None:
        fit_depths &= chain["depth"] >= z_min
    if z_max is not None:
        fit_depths &= chain["depth"] <= z_max
    used = chain["depth"][fit_depths]
    print(f"chain depths used in the fit ({used.size}): "
          + ", ".join(f"{d:g}" for d in used) + " m")
    if used.size < 3:
        raise StepError(
            f"only {used.size} chain sensor(s) between "
            f"{z_min if z_min is not None else 0:g} and "
            f"{z_max if z_max is not None else chain['depth'].max():g} m; "
            f"the chain sensors are at "
            + ", ".join(f"{d:g}" for d in chain["depth"])
            + " m - choose a range holding at least 3 of them")
    contrast = np.nanmedian(np.nanmax(chain_T[fit_depths][:, in_fit], axis=0)
                            - np.nanmin(chain_T[fit_depths][:, in_fit],
                                        axis=0))
    print(f"temperature contrast over these depths: {contrast:.2f} K "
          f"(median over the fitted profiles)")
    if contrast < 1.0:
        print("WARNING: the chosen depths are almost uniform in temperature "
              "(mixed layer near the surface, or the deep water): the "
              "vertical offset is weakly constrained there, above all with a "
              "free temperature shift - include the thermocline in the range "
              "for a reliable offset")

    offsets = {}
    for channel in channels:
        print(f"{channel}: ", end="")
        try:
            offsets[channel] = core.vertical_offset_timeseries(
                time_fit, chain["depth"], chain_T[:, in_fit],
                time_fit, Z[channel], dts_resampled[channel][:, in_fit],
                offset_scan=p["OFFSET_SCAN"], offset_step=p["OFFSET_STEP"],
                fit_temperature_shift=p["FIT_TEMPERATURE_SHIFT"],
                z_min=z_min, z_max=z_max)
        except ValueError as error:
            raise StepError(f"{channel}: {error}")

    # scatter of the shifted DTS against the chain (mean shifts applied)
    scatter = {}
    for channel in channels:
        _, z_offset, _, T_offset = offsets[channel]
        z_shift = float(np.nanmean(z_offset))
        T_shift = float(np.nanmean(T_offset))
        dts_T = dts_resampled[channel][:, in_fit]
        on_chain = np.empty((chain["depth"].size, dts_T.shape[1]))
        for index in range(dts_T.shape[1]):
            core.check_cancel()
            on_chain[:, index] = np.interp(
                chain["depth"] - z_shift, Z[channel], dts_T[:, index],
                left=np.nan, right=np.nan) + T_shift
        depth_grid = np.broadcast_to(chain["depth"][:, None], on_chain.shape)
        chain_fit = chain_T[:, in_fit]
        keep = (np.isfinite(on_chain) & np.isfinite(chain_fit)
                & fit_depths[:, None])          # only the fitted depths
        x_values, y_values = chain_fit[keep], on_chain[keep]
        if x_values.size < 2:
            raise StepError(f"{channel}: no chain value overlaps the shifted "
                            f"DTS in the chosen depth range")
        slope, intercept = np.polyfit(x_values, y_values, 1)
        rms = float(np.sqrt(np.mean((y_values - x_values) ** 2)))
        scatter[channel] = dict(T_chain=x_values, T_dts=y_values,
                                depth=depth_grid[keep], slope=float(slope),
                                intercept=float(intercept), rms=rms,
                                points=int(x_values.size), z_shift=z_shift,
                                T_shift=T_shift)
        print(f"{channel}: T_DTS = {slope:.4f} T_chain {intercept:+.3f} K, "
              f"rms {rms:.3f} K ({x_values.size} points)")

    # first FITTED profile (inside the time windows), shifted by its own
    # fitted (Z, T) pair, against the chain at that same time step (the
    # chain on the common sampling); and the mean difference DTS - chain
    # at every chain sensor over all the fitted profiles
    first_profiles, residuals = {}, {}
    chain_fit_T = chain_T[:, in_fit]
    for channel in channels:
        offset_time, z_offset, _, T_offset = offsets[channel]
        valid = np.nonzero(np.isfinite(z_offset))[0]
        first = int(valid[0])
        column = int(np.searchsorted(time_fit, offset_time[first]))
        first_profiles[channel] = (
            Z[channel] + float(z_offset[first]),
            dts_resampled[channel][:, in_fit][:, column]
            + float(T_offset[first]),
            float(z_offset[first]), float(T_offset[first]),
            offset_time[first])
        difference = np.full((chain["depth"].size, valid.size), np.nan)
        dts_fit = dts_resampled[channel][:, in_fit]
        for k, j in enumerate(valid):
            core.check_cancel()
            col = int(np.searchsorted(time_fit, offset_time[j]))
            difference[:, k] = (np.interp(chain["depth"] - z_offset[j],
                                          Z[channel], dts_fit[:, col],
                                          left=np.nan, right=np.nan)
                                + T_offset[j] - chain_fit_T[:, col])
        residuals[channel] = (np.nanmean(difference, axis=1),
                              np.nanstd(difference, axis=1))
    first_fit_time = min(v[4] for v in first_profiles.values())
    first_column = int(np.searchsorted(time_fit, first_fit_time))
    chain_first = (chain["depth"], chain_fit_T[:, first_column],
                   time_fit[first_column])
    print("mean DTS - chain difference at the chain sensors (fitted "
          "profiles):")
    for channel, (mean, _) in residuals.items():
        print(f"  {channel}: " + ", ".join(
            f"{d:g} m {m:+.2f}" for d, m in zip(chain["depth"], mean)))

    S.update(CALIBRATION_DONE="LeXPLORE chain")
    S.update(VERTICAL_OFFSET=offsets, SCATTER_FIT=scatter,
             CALIBRATION_WINDOW=(time_common[0], time_common[-1],
                                 time_common.size, int(in_fit.sum())),
             CALIBRATION_BASE=(base_name, period_common),
             TIME_WINDOWS=windows, FIT_DEPTHS=used)
    return [("Z and T shift vs time", figs.shift_timeseries(offsets)),
            ("First profile", figs.first_profile_vs_chain(
                first_profiles, chain_first, residuals,
                (float(used.min()), float(used.max())))),
            ("DTS vs chain scatter", figs.scatter_vs_chain(scatter))]


def pre_2_2(session, p):
    """Manual depth calibration: the water-surface position read on the
    Uncalibrated Profiles (connector coordinate)."""
    S = session.data
    session.require("TIME", "Z", "T_MATRIX_mean")
    S["Z_SURFACE"] = float(p["Z_SURFACE"])
    S["CALIBRATION_DONE"] = "manual"
    print(f"water surface position Z_SURFACE = {p['Z_SURFACE']:g} m of fibre "
          f"below the connector: the depths will start there (Shift and "
          f"save, manual calibration)")
    return []


def pre_3(session, p):
    """Apply the calibration and save DTS_preprocessed.nc."""
    S = session.data
    TIME, Z, T_mean = session.require("TIME", "Z", "T_MATRIX_mean")
    method = S.get("CALIBRATION_DONE")
    if method is None:
        raise StepError("run Depth Calibration first (Using LeXPLORE T-Chain "
                        "or Manual)")
    option = p["CALIBRATION"]
    if option not in SHIFT_OPTIONS[method]:
        option = SHIFT_OPTIONS[method][0]
        print(f"calibration option set to '{option}' (the option list "
              f"follows the depth calibration done: {method})")
    apply_z = option in ("Shift in Z and T", "Shift in Z only", "Shift in Z")
    apply_T = option == "Shift in Z and T"
    print(f"depth calibration: {method}; applied: {option}")
    if not apply_z:
        print("NOTE: no depth shift - the depths of the 'calibrated' record "
              "stay in the connector coordinate (0 at the XT)")

    uncalibrated, calibrated = {}, {}
    z_shift, z_shift_std, T_shift, T_shift_std = {}, {}, {}, {}
    shift_source = {}             # channel -> channel whose shifts it took
    for channel in T_mean:
        uncalibrated[channel] = {"time": TIME[channel], "z": Z[channel],
                                 "temperature": T_mean[channel]}
        if method == "LeXPLORE chain":
            fitted = S["VERTICAL_OFFSET"]
            source = channel
            if channel not in fitted:
                # not ticked in Depth Calibration: saved all the same, with
                # the shifts of 'Combined' (else of the first fitted channel)
                source = (cn.COMBINED if cn.COMBINED in fitted
                          else next(iter(fitted)))
                print(f"NOTE: '{channel}' was not fitted in Depth "
                      f"Calibration: it takes the shifts of '{source}'")
                shift_source[channel] = source
            _, z_offset, _, T_offset = fitted[source]
            z_shift[channel] = float(np.nanmean(z_offset)) if apply_z else 0.0
            z_shift_std[channel] = (float(np.nanstd(z_offset)) if apply_z
                                    else 0.0)
            T_shift[channel] = float(np.nanmean(T_offset)) if apply_T else 0.0
            T_shift_std[channel] = (float(np.nanstd(T_offset)) if apply_T
                                    else 0.0)
        else:
            z_shift[channel] = -float(S["Z_SURFACE"])
            z_shift_std[channel] = T_shift[channel] = T_shift_std[channel] = 0.0
        z_calibrated = Z[channel] + z_shift[channel]
        in_water = z_calibrated >= 0.0
        calibrated[channel] = {
            "time": TIME[channel], "z": z_calibrated[in_water],
            "temperature": T_mean[channel][in_water, :] + T_shift[channel]}
        print(f"{channel}: z shift {z_shift[channel]:+.3f} m, T shift "
              f"{T_shift[channel]:+.3f} K -> calibrated depths 0 .. "
              f"{z_calibrated[in_water][-1]:.2f} m "
              f"({int(in_water.sum())} of {z_calibrated.size} levels)")

    if not calibrated:
        raise StepError("no channel was calibrated with the chain: run "
                        "Depth Calibration › Using LeXPLORE T-Chain first")
    output_folder = p.get("OUTPUT_FOLDER") or S["DATA_FOLDER"]
    os.makedirs(output_folder, exist_ok=True)
    product_name = os.path.basename((p.get("PRODUCT_NAME") or "").strip()
                                    or PRODUCT_FILE)
    if not product_name.lower().endswith(".nc"):
        product_name += ".nc"
    save_uncalibrated = p.get("SAVE_UNCALIBRATED", True)
    save_calibrated = p.get("SAVE_CALIBRATED", True)
    if not (save_uncalibrated or save_calibrated):
        raise StepError("tick at least one of 'DTS uncalibrated' and 'DTS "
                        "calibrated' in 'Data to save'")
    if not save_calibrated:
        print("NOTE: the calibrated record is not saved - the analysis "
              "needs it and will not be able to load this file")
    chain = None
    if p.get("SAVE_LEXPLORE", True):
        if method == "LeXPLORE chain" and S.get("DATA_LEXPLORE"):
            chain = S["DATA_LEXPLORE"]
        else:
            print("LeXPLORE T-chain not saved: it was not used in the "
                  "calibration")
    shifts = {c: dict(z_shift_m=z_shift[c], z_shift_std_m=z_shift_std[c],
                      T_shift_K=T_shift[c], T_shift_std_K=T_shift_std[c])
              for c in calibrated}
    utc_offset = S["UTC_OFFSET"]
    attributes = dict(
        IS_TIME_CORRECTION=S["IS_TIME_CORRECTION"],
        IS_LEXPLORE_DATA_AVAILABLE=(method == "LeXPLORE chain"),
        LEXPLORE_ROOT=(S["LEXPLORE_ROOT"] if method == "LeXPLORE chain"
                       else None),
        utc_offset_days=(float(utc_offset / np.timedelta64(1, "D"))
                         if utc_offset is not None else None),
        calibration_method=method, calibration_option=option,
        shifts_taken_from=("; ".join(f"{c} <- {src}" for c, src in
                                     shift_source.items())
                           if shift_source else None),
        configuration=os.path.basename(os.path.normpath(S["DATA_FOLDER"])))
    S.update(CALIBRATION_METHOD=method, CALIBRATION_OPTION=option)
    core.save_product(
        output_folder,
        uncalibrated if save_uncalibrated else None,
        calibrated if save_calibrated else None,
        shifts, attributes,
        configuration=(S.get("CONFIGURATION_TABLE")
                       if p.get("SAVE_CONFIGURATION", True) else None),
        chain=chain,
        preprocessing=preprocessing_variables(session, calibrated),
        filename=product_name,
        readme=f"README_{os.path.splitext(product_name)[0]}.md")
    S.update(T_USHAPED_CALIBRATED=calibrated,
             T_USHAPED_UNCALIBRATED=uncalibrated, Z_SHIFT=z_shift,
             Z_SHIFT_STD=z_shift_std, T_SHIFT=T_shift,
             T_SHIFT_STD=T_shift_std, CALIBRATION_METHOD=method,
             CALIBRATION_OPTION=option,
             OUTPUT_FOLDER=output_folder, PRODUCT_NAME=product_name)
    return pre_3_replot(session, p)


def preprocessing_variables(session, channels):
    """Every variable used by the preprocessing, for the group
    'preprocessing' of the product: the inputs of every step run (JSON),
    the scalar results and the time series (mirror distance, fitted
    offsets)."""
    import json
    S = session.data
    used = {key: value for key, value in getattr(session, "params_used",
                                                 {}).items()
            if key.startswith("pre.")}
    attributes = dict(
        settings_json=json.dumps(used, indent=1, default=str),
        data_folder=S.get("DATA_FOLDER"),
        log_folder=S.get("LOG_FOLDER"),
        channels_loaded=S.get("CHANNELS"),
        reference_local_time=S.get("REFERENCE_LOCAL_TIME"),
        utc_offset_days=(float(S["UTC_OFFSET"] / np.timedelta64(1, "D"))
                         if S.get("UTC_OFFSET") is not None else None),
        dts_window_utc=(f"{stamp(S['DTS_WINDOW'][0])} -> "
                        f"{stamp(S['DTS_WINDOW'][1])}"
                        if S.get("DTS_WINDOW") else None),
        lexplore_status=S.get("LEXPLORE_STATUS"),
        lexplore_root=S.get("LEXPLORE_ROOT"),
        mirror_distance_mean_m=S.get("MAX_DEPTH_mean"),
        vertical_step_m=S.get("dz"),
        common_grid_size=(S["z_common"].size if "z_common" in S else None),
        calibration_method=S.get("CALIBRATION_METHOD"),
        calibration_option=S.get("CALIBRATION_OPTION"),
        water_surface_m=S.get("Z_SURFACE"),
        fit_depths_m=(list(np.round(S["FIT_DEPTHS"], 3))
                      if S.get("FIT_DEPTHS") is not None else None),
        fit_time_windows_utc=("; ".join(f"{a} -> {b}" for a, b in
                                        S["TIME_WINDOWS"])
                              if S.get("TIME_WINDOWS") else None))
    for channel, distance in S.get("MAX_DEPTH", {}).items():
        attributes[f"mirror_distance_m_{channel}"] = distance
    if S.get("CALIBRATION_WINDOW"):
        start, end, n_steps, n_fit = S["CALIBRATION_WINDOW"]
        attributes["calibration_common_window_utc"] = \
            f"{stamp(start)} -> {stamp(end)}"
        attributes["calibration_profiles_fitted"] = f"{n_fit} of {n_steps}"
    if S.get("CALIBRATION_BASE"):
        base, period = S["CALIBRATION_BASE"]
        attributes["calibration_time_base"] = (
            f"{base}, {period / np.timedelta64(1, 's'):.0f} s")
    for channel, fit in S.get("SCATTER_FIT", {}).items():
        attributes[f"scatter_fit_{channel}"] = (
            f"T_DTS = {fit['slope']:.4f} T_chain {fit['intercept']:+.3f} K, "
            f"rms {fit['rms']:.3f} K, {fit['points']} points")
    series = {}
    if S.get("MAX_DEPTH_ALL"):
        series["mirror distance"] = {
            c: {"time": S["MAX_DEPTH_TIME"][c],
                "mirror_distance_m": S["MAX_DEPTH_ALL"][c]}
            for c in S["MAX_DEPTH_ALL"]}
    if S.get("VERTICAL_OFFSET") and S.get("CALIBRATION_METHOD") == \
            "LeXPLORE chain":
        series["vertical offset"] = {
            c: {"time": t, "offset_m": o, "rms_K": r, "T_shift_K": d}
            for c, (t, o, r, d) in S["VERTICAL_OFFSET"].items()}
    return {"attributes": {k: v for k, v in attributes.items()
                           if v is not None},
            "series": series}


def pre_3_replot(session, p):
    """Redraw the calibrated maps with the display options of the figure
    list (no computation)."""
    calibrated = session.require("T_USHAPED_CALIBRATED")[0]
    options = display_of(session)
    return [("Calibrated T(depth, time)",
             figs.calibrated_maps(calibrated, shading(options),
                                  options["CMAP"], chain_for_maps(session)))]


def pre_4(session, p):
    """Markdown report + figures next to DTS_preprocessed.nc."""
    S = session.data
    session.require("OUTPUT_FOLDER", "T_USHAPED_CALIBRATED")
    folder = S["OUTPUT_FOLDER"]
    figure_folder = os.path.join(folder, p["FIGURES_NAME"])
    os.makedirs(figure_folder, exist_ok=True)
    saved = _save_step_figures(session, "pre.", figure_folder,
                               p["FIGURE_DPI"])

    lines = [f"# DTS preprocessing report — "
             f"{os.path.basename(S['DATA_FOLDER'])}", "",
             f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC "
             f"by the DTS GUI. All times are UTC.", "",
             "## 1. Data set and time correction", ""]
    for channel, times in S["TIME"].items():
        period = np.median(np.diff(times)) / np.timedelta64(1, "s")
        lines.append(f"- `{channel}`: {times.size} profiles, "
                     f"{stamp(times[0])} -> {stamp(times[-1])} UTC, "
                     f"sampling period {period:.0f} s.")
    if S["IS_TIME_CORRECTION"]:
        lines.append(f"- Instrument clock corrected to UTC: offset "
                     f"+{S['UTC_OFFSET'] / np.timedelta64(1, 'D'):.6f} days "
                     f"(reference {S['REFERENCE_LOCAL_TIME']} local).")
    else:
        lines.append("- No time correction (instrument clock stamps).")
    if "CONFIGURATION_TABLE" in S:
        lines += ["", "Configuration of each channel:", ""]
        lines += markdown_table(S["CONFIGURATION_TABLE"])
    lines += ["", "## 2. Truncation and folding", ""]
    for channel, record in S["DATA_DTS_RAW_TRUNCATED"].items():
        lines.append(f"- `{channel}`: truncated to 0 - "
                     f"{float(record['measurement_length']):g} m "
                     f"(x = 0 at the connector), {record['x'].size} samples.")
    if "MAX_DEPTH" in S:
        lines.append("- Mirror distance: " + ", ".join(
            f"`{c}` {v:.3f} m" for c, v in S["MAX_DEPTH"].items())
            + f"; common grid of {S['z_common'].size} depths "
              f"(dz = {S['dz']:.4f} m).")
    lines += ["", "## 3. Depth calibration", ""]
    if S["CALIBRATION_METHOD"] == "LeXPLORE chain":
        start, end, n_steps, n_fit = S["CALIBRATION_WINDOW"]
        base, period = S["CALIBRATION_BASE"]
        lines.append(f"- Against the LeXPLORE chain, common sampling of "
                     f"{base} ({period / np.timedelta64(1, 's'):.0f} s), "
                     f"window {stamp(start)} -> {stamp(end)} UTC, "
                     f"{n_fit} of {n_steps} steps fitted.")
        if S.get("FIT_DEPTHS") is not None:
            lines.append("- Chain depths used in the fit: " + ", ".join(
                f"{d:g}" for d in S["FIT_DEPTHS"]) + " m.")
        if S.get("TIME_WINDOWS"):
            lines.append("- Fit windows (UTC): " + "; ".join(
                f"{a} -> {b}" for a, b in S["TIME_WINDOWS"]) + ".")
        for channel, fit in S.get("SCATTER_FIT", {}).items():
            lines.append(f"- Scatter `{channel}`: T_DTS = "
                         f"{fit['slope']:.4f} T_chain "
                         f"{fit['intercept']:+.3f} K, rms {fit['rms']:.3f} K "
                         f"({fit['points']} points).")
    else:
        lines.append(f"- Manual calibration: water surface at Z_SURFACE = "
                     f"{S['Z_SURFACE']:g} m of fibre; no temperature shift.")
    lines.append(f"- Applied: {S.get('CALIBRATION_OPTION', '')}.")
    for channel in S["Z_SHIFT"]:
        lines.append(f"- `{channel}`: z shift {S['Z_SHIFT'][channel]:+.3f} ± "
                     f"{S['Z_SHIFT_STD'][channel]:.3f} m, T shift "
                     f"{S['T_SHIFT'][channel]:+.3f} ± "
                     f"{S['T_SHIFT_STD'][channel]:.3f} K.")
    product = S.get("PRODUCT_NAME", PRODUCT_FILE)
    lines += ["", "## 4. Saved product", "",
              f"`{product}` and `README_{os.path.splitext(product)[0]}.md`: "
              f"{core.f_contents(os.path.join(folder, product))}."]
    for channel, record in S["T_USHAPED_CALIBRATED"].items():
        lines.append(f"- `{channel}`: calibrated depths "
                     f"{record['z'][0]:.2f} - {record['z'][-1]:.2f} m "
                     f"({record['z'].size} levels).")
    lines += ["", "## 5. Figures", ""]
    for name, caption in saved:
        lines += [f"![{name}]({p['FIGURES_NAME']}/{name}.png)", "",
                  caption, ""]
    path = os.path.join(folder, p["REPORT_NAME"])
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"report written: {path}\n{len(saved)} figures in "
          f"{p['FIGURES_NAME']}/")
    return []


STEP_NAMES = {
    "pre.1.load": "Load raw data", "pre.1.mirror": "Load raw data, mirror "
    "distance", "pre.1.concat": "Load raw data, concatenation",
    "pre.2.1": "Depth Calibration, using the LeXPLORE T-chain",
    "pre.2.2": "Depth Calibration, manual", "pre.3": "Save"}


def _save_step_figures(session, prefix, folder, dpi=150):
    """Save the figures of the steps whose id starts with prefix (tables
    are not saved as figures)."""
    import re
    from matplotlib.figure import Figure
    saved = []
    for step_id, figures in session.figures.items():
        if not step_id.startswith(prefix):
            continue
        for title, figure in figures:
            if not isinstance(figure, Figure):
                continue
            label = STEP_NAMES.get(step_id, "step " + step_id.split(".", 1)[1])
            caption = f"{title} ({label})."
            name = re.sub(r"[^A-Za-z0-9]+", "_",
                          f"{step_id}_{title}").strip("_")
            figure.savefig(os.path.join(folder, name + ".png"), dpi=dpi)
            saved.append((name, caption))
    return saved


def markdown_table(frame):
    """A pandas DataFrame as a markdown table (no extra module needed)."""
    columns = [""] + [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(columns) + " |",
             "|" + "---|" * len(columns)]
    for index, row in frame.iterrows():
        lines.append("| " + " | ".join([str(index)] + [str(v) for v in row])
                     + " |")
    return lines


# ===========================================================================
# ANALYSIS
# ===========================================================================
def _records(session, p, with_chain=True):
    """[(name, time, depth, T)] of the ticked channels (+ the chain)."""
    S = session.data
    TIME, Z, T = session.require("A_TIME", "A_Z", "A_T")
    records = [(c, TIME[c], Z[c], T[c]) for c in selected(p, list(T))]
    if with_chain and p.get("INCLUDE_CHAIN", True) \
            and S.get("A_IS_LEXPLORE"):
        chain = S["A_LEXPLORE"]
        records.append(("LeXPLORE chain", chain["time"], chain["depth"],
                        chain["temperature"]))
    return records


PRODUCT_FILE = "DTS_preprocessed.nc"     # default name of the product
CHAIN_CHANNEL = core.CHAIN_GROUP          # 'LeXPLORE T-chain'
RESOLUTION_X_RANGE = (-20.0, -5.0)       # fibre inside the XT (m)


def ana_0(session, p):
    """Load preprocessed data: list the channels of the configurations ticked."""
    import netCDF4
    root = p.get("PRODUCT_ROOT") or ""
    names = [n for n in (p.get("CONFIGURATIONS") or []) if n]
    if not names:
        raise StepError("choose a configuration (the root folder must hold "
                        "configurations with a preprocessed file)")
    separator = " / "
    entries = [e for e in (p.get("PREPROCESSED_FILES") or [])
               if separator in e and e.split(separator, 1)[0] in names]
    if not entries:
        raise StepError("choose a file in 'Preprocessed file'")
    files = [tuple(e.split(separator, 1)) for e in entries]
    folders = [os.path.join(root, name) for name, _ in files]
    filenames = [filename for _, filename in files]
    available = []
    spans = []                       # (file, first, last time) per channel
    has_chain = False
    for folder, filename in zip(folders, filenames):
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            raise StepError(f"{os.path.basename(folder)}: no {filename}")
        with netCDF4.Dataset(path) as handle:
            channels, kinds = [], []
            for name, group in handle.groups.items():
                kind = getattr(group, "kind", "channel")
                if kind == "channel" and "T_calibrated" in group.variables:
                    channels.append(cn.display_name(name))
                    if "time" in group.variables and group["time"].size:
                        times = np.asarray(group["time"][:], dtype="int64")
                        spans.append((f"{os.path.basename(folder)} / "
                                      f"{filename}", int(times.min()),
                                      int(times.max())))
                elif kind == "LeXPLORE chain":
                    has_chain = True
                    kinds.append(name)
            extra = [n for n, g in handle.groups.items()
                     if getattr(g, "kind", "channel") not in
                     ("channel", "LeXPLORE chain")]
            stored_chain = getattr(handle, "IS_LEXPLORE_DATA_AVAILABLE", 0)
        print(f"{os.path.basename(folder)} / {filename}: channels "
              f"{', '.join(channels) or 'none'}"
              + (f"; chain saved" if kinds else "")
              + (f"; also {', '.join(extra)}" if extra else ""))
        if stored_chain and not kinds:
            has_chain = True              # reloaded from the chain folder
        available += [c for c in channels if c not in available]
    if not available:
        raise StepError("no calibrated channel in the files ticked")
    record_spans = {}
    for label, first, last in spans:
        old = record_spans.get(label, (first, last))
        record_spans[label] = (min(old[0], first), max(old[1], last))
    labels = list(record_spans)
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            (a0, a1), (b0, b1) = record_spans[a], record_spans[b]
            if a0 <= b1 and b0 <= a1:
                raise StepError(f"'{a}' and '{b}' cover the same period: "
                                "tick only one of them (the files ticked "
                                "are concatenated in time)")
    for key in [k for k in session.data if k.startswith("A_")]:
        session.data.pop(key)
    session.three_layer_cache.clear()
    product = rename_product(core.load_preprocessed_netcdf_multi(
        folders, filenames))
    chain = load_chain(product, p.get("LEXPLORE_ROOT"))
    warning = None
    if not chain and has_chain:
        print("WARNING: no LeXPLORE chain data over the record (check the "
              "chain folder)")
    folders = list(dict.fromkeys(folders))       # once per folder
    session.data.update(A_FOLDERS=folders, A_FILES=entries,
                        A_CHANNELS_AVAILABLE=available,
                        A_PRODUCT=product, A_CHAIN_ALL=chain,
                        A_RESAMPLE_WARNING=warning)
    print(f"available: {', '.join(available)}")
    table = analysis_configuration(product, entries, chain)
    session.data["A_CONFIGURATION_TABLE"] = table
    return [("Configuration", table)]


def analysis_configuration(product, entries, chain):
    """Table of the data loaded (one column per channel): files, record,
    sampling, depth grid and the calibration stored in the file."""
    import pandas as pd

    def utc(value):
        return str(np.datetime64(value, "s")).replace("T", " ")

    def per_record(values):
        if isinstance(values, dict):
            return "; ".join(f"{v:+.3f}" if len(values) == 1 else
                             f"{k}: {v:+.3f}" for k, v in values.items())
        return f"{values:+.3f}" if values is not None else ""

    table = {}
    for channel, time in product["TIME"].items():
        z = np.asarray(product["Z_CALIBRATED"][channel])
        steps = np.diff(time).astype("timedelta64[ms]").astype(float) / 1e3
        column = {
            "files": "; ".join(entries),
            "profiles": int(time.size),
            "first profile (UTC)": utc(time[0]) if time.size else "",
            "last profile (UTC)": utc(time[-1]) if time.size else "",
            "sampling period (s)": (f"{np.median(steps):.0f}"
                                    if steps.size else ""),
            "depths (m)": (f"{z[0]:.2f} – {z[-1]:.2f} ({z.size} levels)"
                           if z.size else ""),
            "depth spacing (m)": (f"{np.median(np.diff(z)):.3f}"
                                  if z.size > 1 else ""),
            "z shift (m)": per_record(product["Z_SHIFT"].get(channel)),
            "z shift std (m)": per_record(
                product["Z_SHIFT_STD"].get(channel)),
            "T shift (K)": per_record(product["T_SHIFT"].get(channel)),
            "T shift std (K)": per_record(
                product["T_SHIFT_STD"].get(channel)),
        }
        table[channel] = column
    frame = pd.DataFrame(table)
    frame.loc["time correction"] = ("yes" if product.get(
        "IS_TIME_CORRECTION") else "no (instrument clock)")
    frame.loc["calibration"] = ("LeXPLORE chain" if product.get(
        "IS_LEXPLORE_DATA_AVAILABLE") else "manual (water surface)")
    frame.loc["LeXPLORE chain"] = (
        f"{len(chain['time'])} profiles loaded" if chain
        and len(chain.get("time", [])) else "not available")
    return frame


RESAMPLED_SUFFIX = "-resampled"


def series_summary(time, depth):
    """One line on the sampling of a record."""
    period = (np.median(np.diff(time)) / np.timedelta64(1, "s")
              if time.size > 1 else float("nan"))
    spacing = float(np.median(np.diff(depth))) if depth.size > 1 else 0.0
    return (f"{time.size} profiles from {stamp(time[0])} to "
            f"{stamp(time[-1])} UTC, every {period:.0f} s; {depth.size} "
            f"depths from {depth[0]:.2f} to {depth[-1]:.2f} m, every "
            f"{spacing:.3f} m")


def ana_0_3(session, p):
    """Resampling data: new channels '<channel>-resampled'."""
    S = session.data
    session.require("A_T")
    if not (p.get("SPATIAL") or p.get("TEMPORAL")):
        raise StepError("tick 'Spatial resampling' and/or 'Time "
                        "resampling'")
    # a new run replaces the resampled channels of the previous one
    for store in ("A_TIME", "A_Z", "A_T"):
        S[store] = {c: v for c, v in S[store].items()
                    if not c.endswith(RESAMPLED_SUFFIX)}
    info = {c: t for c, t in (S.get("A_CHANNEL_INFO") or {}).items()
            if not c.endswith(RESAMPLED_SUFFIX)}
    channels = selected(p, list(S["A_T"]))
    created = []
    for channel in channels:
        time, depth, T = S["A_TIME"][channel], S["A_Z"][channel], \
            S["A_T"][channel]
        lines = [f"Resampled from '{channel}' "
                 f"({series_summary(time, depth)})."]
        if p.get("SPATIAL"):
            space_step = p.get("SPACE_STEP") or p["SPACE_WIDTH"]
            depth, T = smooth_matrix(depth, T, p["SPACE_WIDTH"], space_step)
            lines.append(
                f"Spatial resampling: NaN-aware average over depth windows "
                f"of {p['SPACE_WIDTH']:g} m centred every "
                f"{np.median(np.diff(depth)):.3g} m"
                + (" (auto: step = window size)" if not p.get("SPACE_STEP")
                   else "")
                + ".")
        if p.get("TEMPORAL"):
            step_src = np.median(np.diff(time))
            if p.get("TIME_AVERAGING"):
                period = np.timedelta64(int(p["PERIOD_MIN"] * 60e3), "ms")
                step = np.timedelta64(int((p.get("TIME_STEP_MIN")
                                           or p["PERIOD_MIN"]) * 60e3), "ms")
                if period <= step_src:
                    raise StepError(
                        f"{channel}: the period ({p['PERIOD_MIN']:g} min) "
                        f"must be longer than the sampling period "
                        f"({step_src / np.timedelta64(1, 's'):.0f} s)")
                targets = np.arange(time[0] + period // 2,
                                    time[-1] - period // 2 + step // 2,
                                    step).astype("datetime64[ms]")
                text = (f"Time resampling: NaN-aware average over windows "
                        f"of {p['PERIOD_MIN']:g} min, one new profile "
                        f"every {step / np.timedelta64(60, 's'):g} min.")
            else:
                chain = S.get("A_LEXPLORE") or {}
                if not (S.get("A_IS_LEXPLORE") and chain):
                    raise StepError("no LeXPLORE chain data: 'Same time "
                                    "base as LeXPLORE' is not possible")
                step_chain = np.median(np.diff(chain["time"]))
                if step_src > step_chain:
                    raise StepError(
                        f"The DTS data of {channel} are on a sampling period "
                        f"of {step_src / np.timedelta64(1, 's'):.0f} s, "
                        f"longer than the LeXPLORE sampling period "
                        f"({step_chain / np.timedelta64(1, 's'):.0f} s): the "
                        f"time resampling on the LeXPLORE time base is "
                        f"ignored, no resampled channel is created.")
                period = step_chain
                inside = ((chain["time"] >= time[0])
                          & (chain["time"] <= time[-1]))
                targets = chain["time"][inside]
                text = (f"Time resampling: same time base as the LeXPLORE "
                        f"chain - NaN-aware average over windows of one "
                        f"chain period "
                        f"({step_chain / np.timedelta64(1, 's'):.0f} s) "
                        f"centred on every chain time stamp.")
            if targets.size < 2:
                raise StepError(f"{channel}: fewer than 2 new profiles")
            T = core.resample_time_mean(time, T, targets, window=period,
                                        verbose=False)
            time = targets
            lines.append(text)
        name = channel + RESAMPLED_SUFFIX
        S["A_TIME"][name], S["A_Z"][name], S["A_T"][name] = time, depth, T
        lines.append(f"Result: {series_summary(time, depth)}.")
        info[name] = "\n\n".join(lines)
        created.append(name)
        print(f"{name}: {series_summary(time, depth)}")
    S["A_CHANNEL_INFO"] = info
    S["A_RESAMPLED"] = created
    resolution = S.get("A_RESOLUTION") or {}
    for name in created:              # upper bound: the source resolution
        source = name[:-len(RESAMPLED_SUFFIX)]
        if source in resolution:
            resolution[name] = resolution[source]
    cmap = p.get("CMAP")
    figures = [("Resampled T(z, t) maps", figs.analysis_maps(
        {c: S["A_TIME"][c] for c in created},
        {c: S["A_Z"][c] for c in created},
        {c: S["A_T"][c] for c in created}, {}, S["A_MAX_DEPTH"], shading(p),
        "seismic" if cmap in (None, "", "default") else cmap))]
    profile_times = S.get("A_PROFILE_TIMES") or []
    if p.get("PLOT_PROFILES"):
        if profile_times:
            figures.append(("Raw and resampled profiles",
                            figs.raw_and_resampled(S, created, profile_times,
                                                   S["A_MAX_DEPTH"])))
        else:
            print("no individual profile in the list of Load preprocessed data: no "
                  "profile figure")
    return figures


def channel_description(session, name):
    """Text of the (?) button of a channel: how the channel is built."""
    S = session.data
    info = (S.get("A_CHANNEL_INFO") or {}).get(name)
    record = None
    for prefix in ("A_", ""):
        times = S.get(prefix + "TIME") or {}
        depths = S.get(prefix + "Z") or {}
        if name in times and name in depths:
            record = (times[name], depths[name])
            break
    summary = (f"\n\nNow loaded: {series_summary(*record)}."
               if record is not None else "")
    if info:
        return info + summary
    if name == cn.COMBINED:
        return ("Combined: the profile-by-profile mean of the DTS channels "
                "(e.g. CH1 and CH3), built at the concatenation of the "
                "preprocessing. The profiles of the channels are paired by "
                "index (the channels sample a few minutes apart); the time "
                "stamp is the mean of the paired stamps and the value is "
                "NaN where one channel is NaN. It is calibrated like the "
                "other channels and saved in DTS_preprocessed.nc."
                + summary)
    if name.startswith("CH"):
        product = S.get("A_PRODUCT") or {}
        shift = ""
        def scalar(value):           # {folder: value} for several files
            if isinstance(value, dict) and value:
                value = float(np.mean(list(value.values())))
            return float(value) if isinstance(value, (int, float)) else None
        z_shift = scalar((product.get("Z_SHIFT") or {}).get(name))
        T_shift = scalar((product.get("T_SHIFT") or {}).get(name))
        if isinstance(z_shift, float):
            shift = (f" Depth shift applied: {z_shift:+.3f} m"
                     + (f", temperature shift {T_shift:+.3f} K"
                        if isinstance(T_shift, float) else "") + ".")
        return (f"{name}: DTS channel {name[2:]} of the XT (folder 'channel "
                f"{name[2:]}'). Every profile is cut to the fibre between the "
                f"connector and the measurement length, folded at the "
                f"mirror distance of the U-shaped cable (the descending and "
                f"ascending legs averaged on a common depth grid) and "
                f"calibrated in depth (and temperature) against the "
                f"LeXPLORE chain or the water surface." + shift + summary)
    return name + summary


def rename_product(product):
    """Channel names of the product as shown by the GUI ('channel n' ->
    'CHn', 'mean' -> 'Combined'; files written before 2.37)."""
    for key, value in list(product.items()):
        if isinstance(value, dict) and value and all(
                isinstance(k, str) for k in value) and key != "LEXPLORE":
            product[key] = cn.rename_keys(value)
    return product


def load_chain(product, chain_root=None):
    """LeXPLORE chain over the whole DTS record: from the folder given,
    else the chain saved in the file, else the folder stored in it.
    Returns {} when there is none."""
    start = min(t[0] for t in product["TIME"].values())
    end = max(t[-1] for t in product["TIME"].values())
    if not chain_root and product.get("LEXPLORE") is not None:
        saved = product["LEXPLORE"]
        inside = (saved["time"] >= start) & (saved["time"] <= end)
        if inside.any():
            print(f"LeXPLORE T-chain: from the file ({inside.sum()} "
                  f"profiles)")
            chain = crop_chain(saved, inside)
            if chain.get("variables"):
                print("LeXPLORE variables: " + ", ".join(
                    ["temp"] + list(chain["variables"])))
            return chain
        return {}
    if not chain_root:
        chain_root = (product["LEXPLORE_ROOT"]
                      if product["IS_LEXPLORE_DATA_AVAILABLE"] else None)
    if not chain_root:
        return {}
    if not os.path.isdir(chain_root):
        print(f"WARNING: LeXPLORE folder not found ({chain_root}); set it "
              f"in this panel - the analyses run without the chain")
        return {}
    chain_time, chain_depth, chain_T, chain_vars = \
        core.read_lexplore_matrix_fromDisk(chain_root, start, end,
                                           with_variables=True)
    if not chain_time.size:
        return {}
    print(f"LeXPLORE T-chain: read from {chain_root} ({chain_time.size} "
          f"profiles); variables: {', '.join(['temp'] + list(chain_vars))}")
    return {"time": chain_time, "depth": chain_depth,
            "temperature": chain_T, "variables": chain_vars}


def ana_0_1(session, p):
    """Update plot: the channels ticked, the chain, the resolution."""
    S = session.data
    folders, available = session.require("A_FOLDERS", "A_CHANNELS_AVAILABLE")
    product = session.require("A_PRODUCT")[0]
    show_chain = bool(p.get("INCLUDE_CHAIN", True))
    channels = list(product["T_USHAPED_CALIBRATED"])   # every channel
    # every channel goes to the analyses; each step has its own selection
    TIME = dict(product["TIME"])
    Z = dict(product["Z_CALIBRATED"])
    T = dict(product["T_USHAPED_CALIBRATED"])

    resolution = dict(S.get("A_RESOLUTION_ALL") or {})
    res_min = p.get("RES_X_MIN", RESOLUTION_X_RANGE[0])
    res_max = p.get("RES_X_MAX", RESOLUTION_X_RANGE[1])
    key = (res_min, res_max)
    if S.get("A_RESOLUTION_KEY") != key or not resolution:
        resolution = {}
        for folder in folders:
            try:
                records = core.read_datasets(folder, verbose=False)
            except Exception as error:          # raw XML not next to file
                print(f"{os.path.basename(folder)}: raw files not read "
                      f"({error}) - no instrument resolution")
                continue
            for channel, record in cn.rename_keys(records).items():
                if channel in resolution:
                    continue
                inside = ((record["x"] >= res_min)
                          & (record["x"] <= res_max))
                resolution[channel] = float(np.std(record["tmp"][inside],
                                                   ddof=1))
        physical = [c for c in resolution
                    if c in product["T_USHAPED_CALIBRATED"]]
        if cn.COMBINED in product["T_USHAPED_CALIBRATED"] and physical:
            resolution[cn.COMBINED] = float(np.sqrt(sum(
                resolution[c] ** 2 for c in physical)) / len(physical))
        S.update(A_RESOLUTION_ALL=resolution, A_RESOLUTION_KEY=key)
    if resolution:
        print("instrument resolution: " + ", ".join(
            f"{c} {r:.4f} K" for c, r in resolution.items()))

    chain, is_chain = {}, False
    chain_all = S.get("A_CHAIN_ALL") or {}
    if chain_all:
        start = min(t[0] for t in TIME.values())
        end = max(t[-1] for t in TIME.values())
        inside = (chain_all["time"] >= start) & (chain_all["time"] <= end)
        if inside.any():
            chain = crop_chain(chain_all, inside)
            is_chain = True

    profile_times = instants(p["PROFILE_TIMES"])
    S.update(A_TIME=TIME, A_Z=Z, A_T=T, A_RESOLUTION=resolution,
             A_LEXPLORE=chain, A_IS_LEXPLORE=is_chain,
             A_SHOW_CHAIN=show_chain,
             A_MAX_DEPTH=float(max(z[-1] for z in Z.values())),
             A_DZ=float(np.median(np.diff(next(iter(Z.values()))))),
             A_PROFILE_TIMES=profile_times)
    S["A_LOAD_SELECTED"] = map_channels(session, p)
    session.three_layer_cache.clear()
    return load_data_figures(session, p)


def map_channels(session, p, fallback=True):
    """Channels ticked in 'Channels on the maps' (all when none is ticked
    and ``fallback``, e.g. right after loading)."""
    available = list(session.data["A_T"])
    ticked = [c for c in (p.get("MAP_CHANNELS") or []) if c in available]
    if not ticked:
        if not fallback:
            raise StepError("tick at least one channel in 'Channels on the "
                            "maps'")
        ticked = [c for c in available if not c.endswith(RESAMPLED_SUFFIX)]
    return ticked


def load_data_figures(session, p):
    """T(z, t) maps of the channels selected with the individual profiles
    marked, and the map of one channel with the profiles."""
    S = session.data
    shown = S.get("A_LOAD_SELECTED") or list(S["A_T"])
    TIME = {c: S["A_TIME"][c] for c in shown}
    Z = {c: S["A_Z"][c] for c in shown}
    T = {c: S["A_T"][c] for c in shown}
    chain = S["A_LEXPLORE"] if S.get("A_SHOW_CHAIN") else {}
    cmap = p.get("CMAP", "seismic")
    if cmap in (None, "", "default"):
        cmap = "seismic"
    profile_times = S["A_PROFILE_TIMES"]
    figures = [("T(z, t) maps",
                figs.analysis_maps(TIME, Z, T, chain, S["A_MAX_DEPTH"],
                                   shading(p), cmap, profile_times))]
    selection = getattr(session, "profile_selection", None)
    profiles = [(label, when) for (label, text), (_, when) in
                zip([r for r in p.get("PROFILE_TIMES", []) if str(r[1]).strip()],
                    instants(p.get("PROFILE_TIMES", [])))
                if not selection           # none ticked (figure hidden):
                or profile_item_name(label, text) in selection]   # all
    if profiles:
        figures.append(("Individual profiles",
                        figs.individual_profiles(
                            TIME, Z, T, chain, profiles, S["A_MAX_DEPTH"])))
    return figures


def profile_item_name(label, text):
    """Name of an individual profile in the figure list."""
    return f"{label} – {str(text).strip()}"


def ana_0_instants(session, p):
    """Update of the individual profiles: the table becomes the list used by
    the analyses, marked on the maps."""
    session.require("A_T")
    profile_times = instants(p["PROFILE_TIMES"])
    session.data["A_PROFILE_TIMES"] = profile_times
    print("individual profiles: " + ("; ".join(
        f"{label} ({stamp(when)})" for label, when in profile_times)
        or "none"))
    return load_data_figures(session, p)


def ana_0_replot(session, p):
    """Select / Update plot: the maps of Load preprocessed data with the channels ticked
    and the display options (no data read again; the other steps keep
    their own channel selections)."""
    S = session.data
    session.require("A_T")
    S["A_LOAD_SELECTED"] = map_channels(session, p, fallback=False)
    print("channels on the maps:", ", ".join(S["A_LOAD_SELECTED"]))
    S["A_SHOW_CHAIN"] = bool(p.get("INCLUDE_CHAIN", True))
    return load_data_figures(session, p)


def ana_0_2(session, p):
    """Brunt-Vaisala frequency of every profile."""
    S = session.data
    records = _records(session, p)
    print(f"physical parameters: g = {core.physics('GRAVITY'):g} m s⁻², "
          f"{core.eos_summary()}")
    N_profiles, N_mean, N_std, N_depth, N_time = {}, {}, {}, {}, {}
    N2_profiles = {}
    for name, time, depth, T in records:
        width = (p["N_SMOOTH_WIDTH"] if p.get("IS_N_SMOOTHING")
                 and name != CHAIN_NAME else None)
        step = p.get("N_SMOOTH_STEP") or (width if width else None)
        depth, N, N_squared = core.brunt_vaisala(depth, T, width, step)
        if width:
            print(f"{name}: T averaged over {width:g} m windows, every "
                  f"{np.median(np.diff(depth)):.3g} m, before dT/dz and N")
        mean, std = core.time_mean_std(N)
        N_profiles[name], N2_profiles[name] = N, N_squared
        N_mean[name], N_std[name] = mean, std
        N_depth[name], N_time[name] = depth, time
        peak = int(np.nanargmax(mean))
        unstable = np.isfinite(N_squared) & (N_squared < 0)
        print(f"{name}: maximum time-average N = {1e3 * mean[peak]:.2f} mHz "
              f"at {depth[peak]:.1f} m; N² < 0 (unstable) in "
              f"{100 * unstable.sum() / max(np.isfinite(N_squared).sum(), 1):.1f}"
              f" % of the points")
    S.update(A_N_PROFILES=N_profiles, A_N_MEAN=N_mean, A_N_STD=N_std,
             A_N_DEPTH=N_depth, A_N_TIME=N_time, A_N2_PROFILES=N2_profiles)
    return [("Mean N profiles", figs.n_mean_profiles(N_mean, N_std, N_depth,
                                                     S["A_MAX_DEPTH"])),
            ("N(z, t) maps", figs.n_maps(N_profiles, N_time, N_depth,
                                         S["A_MAX_DEPTH"], shading(p)))]


def ana_2(session, p):
    """Depth of one isotherm vs time."""
    curves = []
    for name, time, depth, T in _records(session, p):
        iso_depth, uncertainty = core.isotherm_depth(depth, T, p["T_ISO"])
        curves.append((name, time, iso_depth, uncertainty))
    session.data["A_ISOTHERM"] = {
        "T_iso_degC": p["T_ISO"],
        **{name: {"time": time, "depth_m": iso_depth,
                  "uncertainty_m": uncertainty}
           for name, time, iso_depth, uncertainty in curves}}
    return [("Isotherm depth", figs.isotherm_depth(curves, p["T_ISO"]))]


def fft_depth_time(time, T_matrix):
    """Frequencies (Hz) and amplitude 2|X|/n of each row over time (row
    mean removed, NaN -> 0, zero frequency dropped)."""
    dt = np.median(np.diff(time)) / np.timedelta64(1, "s")
    anomaly = np.asarray(T_matrix, float)
    anomaly = np.nan_to_num(anomaly - np.nan_to_num(
        nan_mean_rows(anomaly))[:, None], nan=0.0)
    amplitude = 2.0 * np.abs(np.fft.rfft(anomaly, axis=1)) / anomaly.shape[1]
    frequency = np.fft.rfftfreq(anomaly.shape[1], d=dt)
    return frequency[1:], amplitude[:, 1:]


def coriolis_Hz(latitude_deg=None):
    return core.coriolis_frequency_Hz(latitude_deg)


# window averages over depth (moved to dts_core in 3.02)
smooth_matrix = core.smooth_matrix
smooth_profile = core.smooth_profile


def ana_3_1(session, p):
    """FFT over time at each depth."""
    S = session.data
    N_mean, N_depth = session.require("A_N_MEAN", "A_N_DEPTH")
    latitude = core.physics("LATITUDE_DEG")
    f_coriolis = coriolis_Hz(latitude)
    S["A_F_CORIOLIS"], S["A_LATITUDE"] = f_coriolis, latitude
    print(f"Coriolis parameter at {latitude:.1f} N: f = "
          f"{f_coriolis:.3e} Hz (inertial period "
          f"{1 / f_coriolis / 3600:.1f} h)")
    # auto (None): every frequency available (above zero)
    f_plot = (1.0 / (p["PERIOD_MAX_PLOT"] * 3600.0)
              if p.get("PERIOD_MAX_PLOT") else np.finfo(float).tiny)
    f_colour = (1.0 / (p["PERIOD_MAX_COLOUR"] * 3600.0)
                if p.get("PERIOD_MAX_COLOUR") else np.finfo(float).tiny)
    panels = []
    for name, time, depth, T in _records(session, p):
        frequency, amplitude = fft_depth_time(time, T)
        keep = frequency >= f_plot
        overlay = None
        if name in N_mean:
            overlay_depth, overlay_N = N_depth[name], N_mean[name]
            if p["IS_N_SMOOTHING"] and name != "LeXPLORE chain":
                overlay_depth, overlay_N = smooth_profile(
                    overlay_depth, overlay_N, p["N_SMOOTH_WIDTH"],
                    p.get("N_SMOOTH_STEP") or p["N_SMOOTH_WIDTH"])
            overlay = (overlay_N, overlay_depth)
        panels.append((name, frequency[keep], depth, amplitude[:, keep],
                       overlay))
    colour_values = np.concatenate([a[:, f >= f_colour].ravel()
                                    for _, f, _, a, _ in panels])
    colour_values = colour_values[colour_values > 0]
    vmin, vmax = np.percentile(colour_values, [50, 99.5])
    limits = p.get("COLOUR_LIMITS", "None")
    if p.get("USE_RESOLUTION"):            # older settings files
        limits = "Instrument resolution"
    if limits == "Instrument resolution":
        if S["A_RESOLUTION"]:
            vmin = 0.5 * min(S["A_RESOLUTION"].values())
        else:
            print("no instrument resolution available: automatic limits")
    elif limits == "User defined":
        vmin = p.get("COLOUR_MIN") or vmin
        vmax = p.get("COLOUR_MAX") or vmax
    if not 0 < vmin < vmax:
        raise StepError(f"colour limits must satisfy 0 < lower < upper "
                        f"(got {vmin:g}, {vmax:g})")
    print(f"colour limits: {vmin:.3g} - {vmax:.3g} K ({limits})")
    S["A_FFT_DEPTH"] = {
        name: {"frequency_Hz": frequency, "depth_m": depth,
               "amplitude_K": amplitude,
               **({"N_overlay_Hz": overlay[0],
                   "N_overlay_depth_m": overlay[1]} if overlay else {})}
        for name, frequency, depth, amplitude, overlay in panels}
    S["A_FFT_DEPTH_COLOUR_LIMITS"] = (float(vmin), float(vmax))
    return [("Frequency × depth",
             figs.fft_depth_maps(panels, vmin, vmax, f_coriolis,
                                 S["A_MAX_DEPTH"], shading(p),
                                 p.get("X_AXIS", "frequency"),
                                 p.get("X_SCALE", "log")))]


def ana_3_2(session, p):
    """FFT of the depth of one isotherm, with f, N and Poincare bands."""
    S = session.data
    N_mean, N_depth = session.require("A_N_MEAN", "A_N_DEPTH")
    f_coriolis = session.require("A_F_CORIOLIS")[0]
    start, end = None, None     # the time window of the step sets the limits

    def window_of(time, a, b):
        keep = np.ones(time.size, bool)
        if a is not None:
            keep &= time >= a
        if b is not None:
            keep &= time <= b
        return keep

    curves, spectra, N_values = [], {}, []
    for name, time, depth, T in _records(session, p):
        iso_depth, uncertainty = core.isotherm_depth(depth, T, p["T_PICK"])
        curves.append((name, time, iso_depth, uncertainty))
        keep = window_of(time, start, end)
        frequency, amplitude = fft_depth_time(time[keep],
                                              iso_depth[keep][None, :])
        spectra[name] = (frequency, amplitude[0])
        if name in N_mean:
            in_window = iso_depth[keep]
            in_window = in_window[np.isfinite(in_window)]
            if in_window.size:
                in_range = ((N_depth[name] >= in_window.min())
                            & (N_depth[name] <= in_window.max()))
                values = N_mean[name][in_range]
                N_values += list(values[np.isfinite(values)])
    N_band = (min(N_values), max(N_values)) if N_values else None

    # Poincare V1 band from the profiles of the first channel in the window
    TIME, Z, T = S["A_TIME"], S["A_Z"], S["A_T"]
    channel = selected(p, list(T))[0]      # first channel ticked in 3.2
    lake_width = core.physics("LAKE_WIDTH_KM")
    k_cross = np.pi / (lake_width * 1e3)
    print(f"Poincaré estimate: lake width {lake_width:g} km, g = "
          f"{core.physics('GRAVITY'):g} m s⁻², {core.eos_summary()}")
    frequencies = []
    poincare = parse_window(p.get("POINCARE_WINDOW"))   # None: same as DTS
    keep = window_of(TIME[channel], *((poincare[1], poincare[2])
                                      if poincare else (None, None)))
    if poincare:
        print(f"Poincaré estimate on {poincare[0]}: {stamp(poincare[1])} -> "
              f"{stamp(poincare[2])} UTC")
    for index in np.nonzero(keep)[0]:
        core.check_cancel()
        profile = T[channel][:, index]
        if not np.isfinite(profile).all():
            continue
        z = Z[channel]
        interface = int(np.argmax(np.abs(core.vertical_gradient(z,
                                                                profile)[1])))
        if interface in (0, z.size - 1):
            continue
        h1, h2 = float(z[interface]), float(z[-1]) - float(z[interface])
        g_reduced = float(core.reduced_gravity(profile[:interface].mean(),
                                               profile[interface:].mean()))
        if g_reduced <= 0 or h2 <= 0:
            continue
        c = np.sqrt(g_reduced * h1 * h2 / (h1 + h2))
        omega = np.sqrt((2 * np.pi * f_coriolis) ** 2 + (c * k_cross) ** 2)
        frequencies.append(omega / (2 * np.pi))
    poincare = (min(frequencies), max(frequencies)) if frequencies else None
    if poincare:
        print(f"Poincare V1 band ({channel}, {len(frequencies)} profiles): "
              f"{poincare[0]:.3e} - {poincare[1]:.3e} Hz (periods "
              f"{1 / poincare[1] / 3600:.1f} - {1 / poincare[0] / 3600:.1f} h)")
    else:
        print("Poincare V1 band: no usable profile in the window")

    floor = None
    if p["USE_RESOLUTION"]:
        floors = []
        for name, time, depth, Tm in _records(session, p, with_chain=False):
            iso = [c for c in curves if c[0] == name][0][2]
            if not np.isfinite(iso).any() or name not in S["A_RESOLUTION"]:
                continue
            gradient = core.vertical_gradient(depth, nan_mean_rows(Tm))[1]
            here = abs(np.interp(float(np.nanmean(iso)), depth, gradient))
            floors.append(S["A_RESOLUTION"][name] / max(here, 1e-12))
        floor = 0.5 * min(floors) if floors else None
    for name, (frequency, amplitude) in spectra.items():
        dominant = int(np.nanargmax(amplitude))
        print(f"{name}: dominant period {1 / frequency[dominant] / 3600:.1f} h"
              f" (amplitude {amplitude[dominant]:.2f} m)")
    S["A_ISO_PICK_DEPTH"] = {
        c[0]: {"time": c[1], "depth_m": c[2], "uncertainty_m": c[3]}
        for c in curves if len(c) >= 4}
    S.update(A_ISO_FFT=spectra, A_T_PICK=p["T_PICK"], A_N_ISO=N_band,
             A_POINCARE=poincare)
    marks = dict(f_coriolis=f_coriolis, poincare=poincare, N_band=N_band,
                 dz=S["A_DZ"], floor=floor)
    return [("Depth vs time", figs.isotherm_depth(curves, p["T_PICK"],
                                                  window=(start, end))),
            ("Spectrum",
             figs.isotherm_spectrum(spectra, p["T_PICK"], marks,
                                    p.get("SPECTRUM_AXIS", "frequency"),
                                    p.get("SPECTRUM_SCALE", "log")))]


def ana_4_1_1(session, p):
    """Vertical FFT of every profile (time x k_z)."""
    S = session.data
    profile_times = (instants(p.get("KZ_PROFILES") or [])
                     or session.require("A_PROFILE_TIMES")[0])
    # None (box 'full spectrum' ticked) = every wavenumber > 0
    k_plot = 1.0 / p["WAVELENGTH_MAX_PLOT"] \
        if p.get("WAVELENGTH_MAX_PLOT") else 0.0
    k_colour = 1.0 / p["WAVELENGTH_MAX_COLOUR"] \
        if p.get("WAVELENGTH_MAX_COLOUR") else 0.0
    panels = []
    for name, time, depth, T in _records(session, p):
        if name == "LeXPLORE chain":
            step = float(np.median(np.diff(depth)))
            uniform = np.arange(depth[0], depth[-1] + step / 2, step)
            T = np.vstack([np.interp(uniform, depth, T[:, i])
                           for i in range(time.size)]).T
            depth = uniform
        wavenumber, amplitude = core.fft_vertical(depth, T)
        keep = (wavenumber >= k_plot) & (wavenumber > 0)
        if not keep.any():
            print(f"NOTE: {name} resolves no wavenumber above "
                  f"1/{p['WAVELENGTH_MAX_PLOT']:g} m^-1 - skipped")
            continue
        panels.append((name, time, wavenumber[keep], amplitude[keep, :]))
    values = np.concatenate([a[k >= k_colour, :].ravel()
                             for _, _, k, a in panels])
    values = values[values > 0]
    vmin, vmax = np.percentile(values, [20, 99.9])
    if p["USE_RESOLUTION"] and S["A_RESOLUTION"]:
        vmin = 0.5 * min(S["A_RESOLUTION"].values())
    S["A_KZ_SPECTRA"] = {
        name: {"time": time, "wavenumber_per_m": wavenumber,
               "amplitude_K": amplitude}
        for name, time, wavenumber, amplitude in panels}
    figures = [("Time × k_z", figs.vertical_fft_maps(
        panels, profile_times, vmin, vmax, p["VERTICAL_AXIS"], shading(p)))]
    k_range = (p.get("K_MIN"), p.get("K_MAX"))
    fits = None
    if p.get("_FIT_SCALING"):
        if not profile_times:
            raise StepError("no individual profile: add profiles first")
        fits = scaling_fits(panels, profile_times, k_range)
        S["A_KZ_SCALING"] = fits
    if profile_times:
        figures.append(("FFT of the individual profiles",
                         figs.vertical_fft_profiles(panels, profile_times,
                                                    p["VERTICAL_AXIS"],
                                                    k_range, fits)))
    return figures


def scaling_fits(panels, profile_times, k_range):
    """Least-squares fit of a scaling law A = a k^b to the vertical spectrum
    of every individual profile of every record, between k_min and k_max
    (in log10 A vs log10 k): {record: [(label, a, b, k used)]}."""
    k_min, k_max = k_range
    out = {}
    print("scaling law A = a k^b, k in "
          f"[{k_min if k_min else 'min'}, {k_max if k_max else 'max'}] 1/m:")
    for name, time, wavenumber, amplitude in panels:
        rows = []
        for label, when in profile_times:
            index = nearest_index(time, when)
            A = amplitude[:, index]
            use = (wavenumber > 0) & np.isfinite(A) & (A > 0)
            if k_min:
                use &= wavenumber >= k_min
            if k_max:
                use &= wavenumber <= k_max
            if use.sum() < 3:
                print(f"  {name} {label}: fewer than 3 wavenumbers in the "
                      f"range - no fit")
                rows.append((label, np.nan, np.nan, wavenumber[use]))
                continue
            b, log_a = np.polyfit(np.log10(wavenumber[use]),
                                  np.log10(A[use]), 1)
            a = 10.0 ** log_a
            rows.append((label, a, b, wavenumber[use]))
            print(f"  {name} {label}: a = {a:.3e} K m^b, b = {b:+.2f} "
                  f"({int(use.sum())} wavenumbers)")
        out[name] = rows
    return out


def ana_4_1_1_fit(session, p):
    """Fit scaling: the wavenumber-domain figures with the a k^b fits."""
    return ana_4_1_1(session, dict(p, _FIT_SCALING=True))


def _unsigned_kz(k_z, amplitude):
    positive = amplitude[k_z > 0, :]
    negative = amplitude[k_z < 0, :][::-1, :]
    n_pairs = min(positive.shape[0], negative.shape[0])
    return k_z[k_z > 0][:n_pairs], positive[:n_pairs] + negative[:n_pairs]


def ana_4_1_2(session, p):
    """2D FFT (depth x time) of every channel ticked and every layer ticked:
    one figure per channel with one panel per layer (common colour
    scale)."""
    S = session.data
    records = _records(session, p, with_chain=False)
    if not records:
        raise StepError("tick at least one channel")
    layers = [l for l in (p.get("LAYERS") or []) if l] or [WHOLE_COLUMN]
    window = parse_window(p.get("TIME_WINDOW"))
    cropped = {}
    for layer in layers:                    # depths of each layer
        if layer == WHOLE_COLUMN:
            continue
        name = layer.split(":")[0].strip()
        try:
            cropped[layer] = layered_data(S, name, window)
        except StepError as error:
            print(f"{name}: skipped ({error})")
    results = {}                            # channel -> [(layer, f, k, a)]
    for channel, time, depth, T in records:
        rows = []
        for layer in layers:
            if layer == WHOLE_COLUMN:
                z, matrix, title = depth, T, WHOLE_COLUMN
            elif layer in cropped and channel in cropped[layer]["A_Z"]:
                z = cropped[layer]["A_Z"][channel]
                matrix = cropped[layer]["A_T"][channel]
                title = layer
            else:
                continue
            frequency, k_z, amplitude = core.fft2_matrix(
                time, z, matrix, label=f"{channel} {title}")
            k_unsigned, a_unsigned = _unsigned_kz(k_z, amplitude)
            rows.append((title, frequency, k_unsigned, a_unsigned))
        if rows:
            results[channel] = rows
    if not results:
        raise StepError("no layer could be transformed")
    S["A_FFT2"] = {
        channel: {title: {"frequency_Hz": frequency,
                          "k_z_unsigned_per_m": k_z,
                          "amplitude_K": amplitude}
                  for title, frequency, k_z, amplitude in rows}
        for channel, rows in results.items()}
    values = np.concatenate([a[a > 0].ravel() for rows in results.values()
                             for *_, a in rows])
    vmin, vmax = np.percentile(values, [20, 99.9])
    if p["USE_RESOLUTION"]:
        resolutions = [S["A_RESOLUTION"][n] for n in results
                       if n in S.get("A_RESOLUTION", {})]
        if resolutions:
            vmin = 0.5 * min(resolutions)
    return [(f"2D FFT – {channel}", figs.fft2_maps(
                rows, vmin, vmax, f"2D FFT (depth × time) – {channel}",
                p["VERTICAL_AXIS"], p["TIME_AXIS"], shading(p), columns=2))
            for channel, rows in results.items()]


def thermocline_from_chain(chain):
    """Depth of the largest |dT/dz| of every chain profile (NaN when the
    profile has fewer than 3 values)."""
    depth = np.asarray(chain["depth"], float)
    T = np.asarray(chain["temperature"], float)
    out = np.full(T.shape[1], np.nan)
    for index in range(T.shape[1]):
        good = np.isfinite(T[:, index])
        if good.sum() < 3:
            continue
        z, t = depth[good], T[good, index]
        gradient = np.diff(t) / np.diff(z)
        k = int(np.nanargmax(np.abs(gradient)))
        out[index] = 0.5 * (z[k] + z[k + 1])
    return out


def ana_1(session, p):
    """Multi-layer decomposition: interfaces of two or three layers."""
    S = session.data
    layering = p.get("LAYERING", "One layer")
    if layering == "One layer":
        print("one layer: the whole water column, nothing to do")
        S["A_LAYERS"] = {"layering": layering, "interfaces": {}}
        return []
    records = _records(session, p)
    prefix = "TWO" if layering == "Two layers" else "THREE"
    smoothing = bool(p.get(f"{prefix}_SMOOTHING"))
    width = p.get(f"{prefix}_SMOOTH_WIDTH")
    step = p.get(f"{prefix}_SMOOTH_STEP")

    def smoothed(name, depth, T):
        """T averaged over depth windows (DTS records only)."""
        if not smoothing or name == CHAIN_NAME:
            return depth, T
        z, Ts = smooth_matrix(depth, T, width, step)
        print(f"{name}: T smoothed over {width:g} m windows, every "
              f"{np.median(np.diff(z)):.3g} m")
        return z, Ts

    records_fit = [(name, time) + smoothed(name, depth, T)
                   for name, time, depth, T in records]
    interfaces, method = {}, ""
    if layering == "Two layers":
        if p.get("TWO_FROM_ISOTHERM"):
            method = f"isotherm {p['T_ISOTHERM']:g} °C"
            for name, time, depth, T in records_fit:
                z1 = core.isotherm_depth(depth, T, p["T_ISOTHERM"])[0]
                interfaces[name] = (time, [z1])
        else:
            chain = S.get("A_LEXPLORE") or {}
            if not (S.get("A_IS_LEXPLORE") and chain):
                raise StepError("no LeXPLORE chain data over the record: "
                                "the thermocline cannot be taken from the "
                                "chain (choose 'From isotherm')")
            variable = (chain.get("variables") or {}).get(
                "thermocline_depth")
            seconds = lambda t: t.astype("datetime64[ms]").astype(float)
            if variable is not None and tuple(variable["dims"]) == \
                    ("time",) and np.size(variable["data"]) == \
                    chain["time"].size:
                z_chain = np.asarray(variable["data"], float)
                good = np.isfinite(z_chain)
                if good.sum() < 2:
                    raise StepError("the LeXPLORE variable "
                                    "'thermocline_depth' has no value over "
                                    "the record")
                method = ("thermocline_depth of the LeXPLORE files, "
                          "interpolated in time")
                print(f"LeXPLORE thermocline_depth: {good.sum()} values, "
                      f"{np.nanmin(z_chain):.1f} - {np.nanmax(z_chain):.1f} "
                      f"m (mean {np.nanmean(z_chain):.1f} m)")
                if smoothing:
                    print("NOTE: the smoothing does not change the "
                          "thermocline_depth read from the files")
                for name, time, depth, T in records:
                    z1 = np.interp(seconds(time),
                                   seconds(chain["time"][good]),
                                   z_chain[good], left=np.nan, right=np.nan)
                    interfaces[name] = (time, [z1])
                    print(f"{name}: thermocline interpolated onto "
                          f"{time.size} profiles "
                          f"({int(np.isfinite(z1).sum())} inside the chain "
                          f"record)")
            else:
                print("NOTE: no 'thermocline_depth' in the LeXPLORE data - "
                      "the thermocline is the depth of the largest |dT/dz| "
                      "of every chain profile")
                method = "thermocline of the LeXPLORE chain (max |dT/dz|)"
                if smoothing:                  # the chain defines Z1 here
                    depth_c, T_c = smooth_matrix(chain["depth"],
                                                 chain["temperature"], width,
                                                 step)
                    print(f"LeXPLORE chain: T smoothed over {width:g} m "
                          f"windows, every "
                          f"{np.median(np.diff(depth_c)):.3g} m")
                    z_chain = thermocline_from_chain(
                        {"depth": depth_c, "temperature": T_c})
                else:
                    z_chain = thermocline_from_chain(chain)
                good = np.isfinite(z_chain)
                for name, time, depth, T in records:
                    z1 = np.interp(seconds(time),
                                   seconds(chain["time"][good]),
                                   z_chain[good], left=np.nan, right=np.nan)
                    interfaces[name] = (time, [z1])
    else:
        if p.get("THREE_BEST_FIT"):
            method = (f"best fit (tolerance {p['RMS_TOL']:g} K, "
                      f"{int(p['MIN_POINTS'])} points, gap "
                      f"{p['MIN_GAP']:g} m)")
            for name, time, depth, T in records_fit:
                print(f"three-layer fit of {name}:")
                fit = core.fit_three_layers_batch(
                    depth, T, rms_tol=p["RMS_TOL"],
                    min_points=int(p["MIN_POINTS"]), min_gap=p["MIN_GAP"])
                interfaces[name] = (time, [fit["Z1"], fit["Z2"]])
        else:
            if p["T_TOP"] <= p["T_BOTTOM"]:
                raise StepError("the top isotherm must be warmer than the "
                                "bottom isotherm")
            method = (f"isotherms {p['T_TOP']:g} °C (Z1) and "
                      f"{p['T_BOTTOM']:g} °C (Z2)")
            for name, time, depth, T in records_fit:
                z1 = core.isotherm_depth(depth, T, p["T_TOP"])[0]
                z2 = core.isotherm_depth(depth, T, p["T_BOTTOM"])[0]
                interfaces[name] = (time, [z1, z2])
    if smoothing:
        method += f", T smoothed over {width:g} m"
    print(f"{layering.lower()} from the {method}")
    for name, (time, levels) in interfaces.items():
        text = ", ".join(f"Z{k + 1} = {np.nanmean(z):.1f} ± "
                         f"{np.nanstd(z):.1f} m" for k, z in enumerate(levels))
        print(f"  {name}: {text} ({np.isfinite(levels[0]).sum()} of "
              f"{time.size} profiles)")
    S["A_LAYERS"] = {"layering": layering, "method": method,
                     "interfaces": interfaces}
    figures = [("Layers", figs.layer_maps(
        records, interfaces, S["A_MAX_DEPTH"], shading(p),
        f"{layering} – {method}", profiles=layer_profile_list(S, p)))]
    profiles = layer_profile_list(S, p)
    if profiles:
        best_fit = layering == "Three layers" and p.get("THREE_BEST_FIT")
        fit_depths = {name: (depth, T) for name, time, depth, T in records_fit}
        for label, when in profiles:
            entries = []
            for name, time, depth, T in records:
                if name not in interfaces:
                    continue
                index = nearest_index(time, when)
                itime, levels = interfaces[name]
                k = nearest_index(itime, when)
                z_levels = [float(z[k]) for z in levels]
                profile = np.asarray(T, float)[:, index]
                model = None
                if best_fit:                  # continuous model, as fitted
                    z_fit, T_fit = fit_depths.get(name, (depth, T))
                    column = np.asarray(T_fit, float)[:, index]
                    try:
                        fit = core.fit_three_layers(
                            np.asarray(z_fit, float), column,
                            rms_tol=p["RMS_TOL"],
                            min_points=int(p["MIN_POINTS"]),
                            min_gap=p["MIN_GAP"])
                    except Exception as error:     # noqa: BLE001
                        print(f"{name} {label}: no fit ({error})")
                        fit = None
                    if fit is not None:
                        model = (np.asarray(z_fit, float),
                                 np.asarray(fit["T_fit"], float),
                                 fit["slopes"], fit.get("rms"))
                        z_levels = [float(fit["Z1"]), float(fit["Z2"])]
                segments = [] if model is not None else \
                    piecewise_layers(depth, profile, z_levels)
                entries.append((name, time[index], np.asarray(depth, float),
                                profile, z_levels, segments, model))
            figures.append((f"Individual profile {label}",
                            figs.layer_profile_figure(
                                label, when, entries,
                                f"{layering} – {method}",
                                S["A_MAX_DEPTH"])))
    return figures


def layer_profile_list(S, p):
    """Individual profiles of the Multi-layer panel (the shared list; the
    profiles of Load preprocessed data when the table is empty)."""
    return (instants(p.get("LAYER_PROFILES") or [])
            or list(S.get("A_PROFILE_TIMES") or []))


def piecewise_layers(depth, profile, levels):
    """Straight line T(z) fitted (least squares) in every layer between the
    interfaces ``levels``: [(z_top, z_bottom, T_top, T_bottom)] per layer
    (None for a layer with fewer than 2 finite points)."""
    depth = np.asarray(depth, float)
    profile = np.asarray(profile, float)
    good = np.isfinite(profile) & np.isfinite(depth)
    if not good.any():
        return []
    edges = [float(depth[good].min())] + [z for z in levels
                                           if np.isfinite(z)] + \
        [float(depth[good].max())]
    segments = []
    for top, bottom in zip(edges[:-1], edges[1:]):
        inside = good & (depth >= top) & (depth <= bottom)
        if inside.sum() < 2 or bottom <= top:
            segments.append(None)
            continue
        slope, intercept = np.polyfit(depth[inside], profile[inside], 1)
        segments.append((top, bottom, intercept + slope * top,
                         intercept + slope * bottom))
    return segments


def three_layers(session, name):
    """Interfaces Z1, Z2 of every profile of one record: those of the
    Multi-layer decomposition when it was run with three layers (the
    interfaces of the record, else of 'Combined', interpolated in time),
    otherwise the best three-layer fit with the default settings
    (cached)."""
    S = session.data
    layers = S.get("A_LAYERS") or {}
    interfaces = layers.get("interfaces") or {}
    if layers.get("layering") == "Three layers" and interfaces:
        key = name if name in interfaces else (
            cn.COMBINED if cn.COMBINED in interfaces
            else next(iter(interfaces)))
        source_time, (z1, z2) = interfaces[key]
        if name == CHAIN_NAME and name not in S.get("A_T", {}):
            time = S["A_LEXPLORE"]["time"]
        else:
            time = S["A_TIME"][name]
        seconds = lambda t: np.asarray(t, "datetime64[ms]").astype(float)
        out = {}
        for label, z in (("Z1", z1), ("Z2", z2)):
            good = np.isfinite(z)
            out[label] = (np.interp(seconds(time),
                                    seconds(source_time[good]), z[good],
                                    left=np.nan, right=np.nan)
                          if good.sum() >= 2 else np.full(time.size, np.nan))
        if (name, "note") not in session.three_layer_cache:
            print(f"{name}: layers of the Multi-layer decomposition "
                  f"({layers.get('method', '')}, interfaces of {key})")
            session.three_layer_cache[(name, "note")] = True
        return out
    if ("fallback", "note") not in session.three_layer_cache:
        print("NOTE: no three-layer Multi-layer decomposition - the "
              "interfaces come from the default best fit (run the "
              "Multi-layer decomposition with three layers to choose "
              "them)")
        session.three_layer_cache[("fallback", "note")] = True
    params = S.get("A_LAYER_PARAMS", (0.05, 5, 2.0))
    key = (name, params, S.get("A_WINDOW"), S.get("A_LAYER"))
    if key not in session.three_layer_cache:
        if name == "LeXPLORE chain":
            depth, T = S["A_LEXPLORE"]["depth"], S["A_LEXPLORE"]["temperature"]
        else:
            depth, T = S["A_Z"][name], S["A_T"][name]
        print(f"three-layer fit of {name}:")
        session.three_layer_cache[key] = core.fit_three_layers_batch(
            depth, T, rms_tol=params[0], min_points=params[1],
            min_gap=params[2])
    return session.three_layer_cache[key]


LAYER_NAMES = ("top (mixed)", "middle (stratified)", "bottom (weak)")


def layer_bounds_at(S, name, label, when):
    """Depth range (top, bottom) of the layer chosen in the list 'Layer' for
    one record at one instant: the interfaces of the Multi-layer
    decomposition interpolated in time (those of 'Combined', else of the
    first record, for a record not decomposed).  The whole column gives
    (-inf, inf)."""
    label = (label or WHOLE_COLUMN)
    if label == WHOLE_COLUMN:
        return -np.inf, np.inf, WHOLE_COLUMN
    label = label.split(":")[0].strip()
    layers = S.get("A_LAYERS") or {}
    interfaces = layers.get("interfaces") or {}
    if not interfaces:
        raise StepError("no layers: run the Multi-layer decomposition first")
    number = LAYER_NUMBERS.get(label)
    if number is None:                        # the bottom layer
        number = 2 if layers.get("layering") == "Two layers" else 3
    key = name if name in interfaces else (
        cn.COMBINED if cn.COMBINED in interfaces else next(iter(interfaces)))
    time, levels = interfaces[key]
    seconds = lambda t: np.asarray(t, "datetime64[ms]").astype(float)
    values = []
    for z in levels:
        good = np.isfinite(z)
        values.append(float(np.interp(seconds(when), seconds(time[good]),
                                      z[good])) if good.sum() >= 1
                      else np.nan)
    edges = [-np.inf] + values + [np.inf]
    if number > len(edges) - 1:
        raise StepError(f"layer {label} does not exist with "
                        f"{layers['layering'].lower()}")
    return edges[number - 1], edges[number], label


def ana_4_2_5(session, p):
    """Staircases inside the layer chosen at the individual profiles, all
    the channels ticked on one figure."""
    S = session.data
    profiles = (instants(p.get("STAIRCASE_PROFILES") or [])
                or list(S.get("A_PROFILE_TIMES") or []))
    if not profiles:
        raise StepError("give at least one individual profile (table "
                        "Individual profiles)")
    S["A_STAIRCASE_TIMES"] = profiles
    if p.get("USE_MAX_GRADIENT"):
        print(f"threshold: |dT/dz| < {p['MAX_GRADIENT']:g} K/m")
    else:
        print(f"threshold: |dT/dz| < {p['GRAD_FACTOR']:g} x the mean "
              "gradient of the layer")
    records = _records(session, p, with_chain=False)
    if not records:
        raise StepError("tick at least one channel")
    results = {label: [] for label, _ in profiles}
    extent = {label: [np.inf, -np.inf] for label, _ in profiles}
    layer_name = WHOLE_COLUMN
    for name, time, depth, T in records:
        T = np.asarray(T, float)
        for label, when in profiles:
            index = nearest_index(time, when)
            top, bottom, layer_name = layer_bounds_at(
                S, name, p.get("LAYER"), time[index])
            if not (np.isfinite(top) or np.isfinite(bottom)) \
                    and layer_name != WHOLE_COLUMN:
                print(f"{name} {label}: no interface at this time, skipped")
                results[label].append((name, time[index], None))
                continue
            stairs = core.find_staircase(
                depth, T[:, index], top, bottom,
                grad_factor=p["GRAD_FACTOR"],
                min_thickness=p["MIN_THICKNESS"],
                smooth_length=p["SMOOTH_LENGTH"],
                max_gradient=(p.get("MAX_GRADIENT")
                              if p.get("USE_MAX_GRADIENT") else None))
            shown_top = max(top, float(np.nanmin(depth)))
            shown_bottom = min(bottom, float(np.nanmax(depth)))
            extent[label][0] = min(extent[label][0], shown_top)
            extent[label][1] = max(extent[label][1], shown_bottom)
            if stairs is None:
                print(f"{name} {label}: layer too thin, skipped")
            else:
                print(f"{name} {label} {stamp(time[index])} UTC: "
                      f"{layer_name} = [{shown_top:.1f}, {shown_bottom:.1f}]"
                      f" m, {stairs['step_T'].size} step(s)")
            results[label].append((name, time[index], stairs))
    S["A_STAIRCASES"] = {
        label: {"layer": layer_name, "depth_range_m": tuple(extent[label]),
                **{name: ({"time": when_used, **stairs}
                          if stairs is not None else {"time": when_used})
                   for name, when_used, stairs in results[label]}}
        for label, _ in profiles}
    TIME = {name: time for name, time, _, _ in records}
    Z = {name: depth for name, _, depth, _ in records}
    T = {name: np.asarray(matrix, float) for name, _, _, matrix in records}
    return [("Maps", figs.analysis_maps(
                TIME, Z, T, {}, float(max(z[-1] for z in Z.values())),
                shading(p), "seismic", profiles)),
            ("Staircases", figs.staircases(
                [(label, when, results[label], tuple(extent[label]))
                 for label, when in profiles],
                layer_name))]


ana_4_2_5.own_layer = True     # the layer is applied per snapshot instant


def ana_4_2_6(session, p):
    """Raw dT/dz maps (one figure) and the individual profiles of the
    gradient (all channels)."""
    S = session.data
    profiles = (instants(p.get("GRADIENT_PROFILES") or [])
                or list(S.get("A_PROFILE_TIMES") or []))
    maps = []
    width = p.get("GRADIENT_SMOOTH_WIDTH") if p.get("IS_GRADIENT_SMOOTHING") \
        else None
    step = p.get("GRADIENT_SMOOTH_STEP") or width
    for channel, time, depth, T in _records(session, p, with_chain=False):
        grid, gradient = core.vertical_gradient(depth, T, width, step)
        maps.append((channel, time, grid, gradient))
    if width:
        print(f"T averaged over {width:g} m windows (every {step:g} m) "
              f"before dT/dz")
    if not maps:
        raise StepError("tick at least one channel")
    S["A_GRADIENT"] = {
        channel: {"time": time, "depth_m": grid, "dTdz_K_per_m": gradient}
        for channel, time, grid, gradient in maps}
    S["A_GRADIENT_PROFILES"] = profiles
    figures = [("Maps", figs.gradient_maps(
        maps, profiles, "Vertical temperature gradient dT/dz",
        shading(p)))]
    if profiles:
        layers = S.get("A_LAYERS") or {}
        interfaces = layers.get("interfaces") or {}
        key = next((k for k in [cn.COMBINED] + [m[0] for m in maps]
                    if k in interfaces), None)
        figures.append(("Individual profiles", figs.gradient_profiles(
            maps, profiles, interfaces.get(key) if key else None)))
        print("individual profiles: " + "; ".join(
            f"{label} ({stamp(when)})" for label, when in profiles))
    else:
        print("no individual profile: add some in the Individual profiles "
              "box (or in Load preprocessed data)")
    return figures


def ana_4_2_9(session, p):
    """Seismogram-like plot of the S2 profiles of a time window, one
    figure per channel ticked."""
    window = parse_window(p.get("SEISMO_WINDOW"))
    if window is not None:
        label, start, end = window
        span = f"{label}, {stamp(start)} -> {stamp(end)} UTC"
    else:
        start = utc(p["WATERFALL_START"])
        if start is None:
            raise StepError("give the start of the profiles (or choose a "
                            "time window W1, W2, ...)")
        hours = p["WATERFALL_DURATION_HOURS"]
        end = start + np.timedelta64(int(round(hours * 3600)), "s")
        span = f"{hours:g} h from {stamp(start)} UTC"
    records = _records(session, p, with_chain=False)
    if not records:
        raise StepError("tick at least one channel")
    figures = []
    seismogram = {}
    step_min = p.get("WATERFALL_STEP_MIN")
    for channel, time, depth, T in records:
        indices = np.nonzero((time >= start) & (time <= end))[0]
        if step_min and indices.size > 1:
            # the profile nearest to every multiple of the step
            step = np.timedelta64(int(round(step_min * 60e3)), "ms")
            n_steps = int((time[indices[-1]] - time[indices[0]]) / step) + 1
            targets = time[indices[0]] + step * np.arange(n_steps)
            chosen = [indices[int(np.argmin(np.abs(time[indices] - t)))]
                      for t in targets]
            indices = np.array(sorted(set(chosen)))
            print(f"{channel}: one profile every {step_min:g} min")
        print(f"{channel}: {indices.size} profiles in {span}")
        if indices.size == 0:
            continue
        layers = three_layers(session, channel)
        seismogram[channel] = {
            "time": time[indices], "depth_m": depth,
            "T_degC": np.asarray(T, float)[:, indices],
            "spacing_K": p["WATERFALL_SPACING"]}
        figures.append((f"Seismogram-like profiles – {channel}",
                        figs.waterfall(
                            time, depth, np.asarray(T, float), layers,
                            indices, p["WATERFALL_SPACING"],
                            f"S2 temperature profiles, {span} ({channel})")))
    if not figures:
        raise StepError("no profile in the time window: change it")
    session.data["A_SEISMOGRAM"] = seismogram
    return figures


ana_4_2_9.own_layer = True     # S2 of each profile, not the 'Layer' list


def ana_5(session, p):
    """Markdown report + figures of the analysis steps run."""
    S = session.data
    folders = session.require("A_FOLDERS")[0]
    session.require("A_T")
    folder = p.get("OUTPUT_FOLDER") or folders[0]
    figure_folder = os.path.join(folder, p["FIGURES_NAME"])
    os.makedirs(figure_folder, exist_ok=True)
    saved = _save_step_figures(session, "ana.", figure_folder)
    lines = [f"# DTS analysis report — "
             f"{', '.join(os.path.basename(f) for f in folders)}", "",
             f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC "
             f"by the DTS GUI. All times are UTC.", "", "## 1. Data set", ""]
    for channel, time in S["A_TIME"].items():
        z = S["A_Z"][channel]
        period = np.median(np.diff(time)) / np.timedelta64(1, "s")
        lines.append(f"- `{channel}`: {time.size} profiles, {stamp(time[0])}"
                     f" -> {stamp(time[-1])} UTC, sampling period "
                     f"{period:.0f} s; depths {z[0]:.2f} - {z[-1]:.2f} m "
                     f"({z.size} levels).")
    for channel, resolution in S["A_RESOLUTION"].items():
        lines.append(f"- Instrument resolution `{channel}`: "
                     f"{resolution:.4f} K.")
    if S.get("A_IS_LEXPLORE"):
        lines.append(f"- LeXPLORE chain: {S['A_LEXPLORE']['time'].size} "
                     f"profiles, {S['A_LEXPLORE']['depth'].size} depths.")
    lines.append("")
    if "A_N_MEAN" in S:
        lines += ["## 2. Stratification", ""]
        for name, mean in S["A_N_MEAN"].items():
            peak = int(np.nanargmax(mean))
            lines.append(f"- `{name}`: maximum time-average N = "
                         f"{1e3 * mean[peak]:.2f} mHz at "
                         f"{S['A_N_DEPTH'][name][peak]:.1f} m.")
        lines.append("")
    if "A_F_CORIOLIS" in S:
        f = S["A_F_CORIOLIS"]
        lines += ["## 3. Frequency domain", "",
                  f"- Coriolis parameter f = {f:.3e} Hz at "
                  f"{S['A_LATITUDE']:g}° N (inertial period "
                  f"{1 / f / 3600:.1f} h)."]
        if S.get("A_POINCARE"):
            low, high = S["A_POINCARE"]
            lines.append(f"- Poincaré V1 band: {low:.3e} - {high:.3e} Hz "
                         f"({1 / high / 3600:.1f} - {1 / low / 3600:.1f} h).")
        if S.get("A_N_ISO"):
            low, high = S["A_N_ISO"]
            lines.append(f"- N at the {S['A_T_PICK']:g} °C isotherm: "
                         f"{1e3 * low:.2f} - {1e3 * high:.2f} mHz.")
        for name, (frequency, amplitude) in S.get("A_ISO_FFT", {}).items():
            dominant = int(np.nanargmax(amplitude))
            lines.append(f"- Dominant period of the {S['A_T_PICK']:g} °C "
                         f"isotherm depth, `{name}`: "
                         f"{1 / frequency[dominant] / 3600:.1f} h "
                         f"({amplitude[dominant]:.2f} m).")
        lines.append("")
    reported = [key for key in session.three_layer_cache
                if key[0] != "LeXPLORE chain" and key[1] != "note"]
    if reported:
        lines += ["## 4. Three-layer decomposition", ""]
        for key in reported:
            name, params = key[0], key[1]
            layers = session.three_layer_cache[key]
            lines.append(f"- `{name}` (tolerance {params[0]:g} K): Z1 = "
                         f"{np.nanmean(layers['Z1']):.1f} ± "
                         f"{np.nanstd(layers['Z1']):.1f} m, Z2 = "
                         f"{np.nanmean(layers['Z2']):.1f} ± "
                         f"{np.nanstd(layers['Z2']):.1f} m.")
        lines.append("")
    lines += ["## 5. Figures", ""]
    for name, caption in saved:
        lines += [f"![{name}]({p['FIGURES_NAME']}/{name}.png)", "",
                  caption, ""]
    path = os.path.join(folder, p["REPORT_NAME"])
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"report written: {path}\n{len(saved)} figures in "
          f"{p['FIGURES_NAME']}/")
    return []


# ---------------------------------------------------------------------------
# Advanced: sound speed maps and STC profiles
# ---------------------------------------------------------------------------
def _sound_flags(p):
    flags = dict(use_T=bool(p.get("USE_T", True)),
                 use_P=bool(p.get("USE_P", True)),
                 use_S=bool(p.get("USE_S", True)))
    text = ", ".join(f"{k[-1]} {'on' if v else 'off'}"
                     for k, v in flags.items())
    return flags, text


def _day_month(when):
    """'21.10 06:00' (UTC)."""
    text = stamp(when)
    return f"{text[8:10]}.{text[5:7]} {text[11:16]}"


def _stc_selection(p):
    """[(file name, start time)] of the STC profiles ticked."""
    folder = p.get("STC_FOLDER") or ""
    wanted = p.get("STC_PROFILES")
    profiles = core.stc_profile_files(folder)
    if wanted is not None:
        profiles = [(n, t) for n, t in profiles if n in wanted]
    if p.get("STC_AT_LEXPLORE_ONLY"):          # option of the first box
        kept = [(n, t) for n, t in profiles
                if core.at_lexplore(*core.stc_position(folder, n))]
        left_out = [n for n, _ in profiles if n not in dict(kept)]
        if left_out:
            print(f"only the STC profiles at LéXPLORE (within "
                  f"{core.physics('LEXPLORE_RADIUS_M'):g} m): left out "
                  + ", ".join(left_out))
        profiles = kept
    return folder, profiles


def _gap_text(seconds):
    return (f"{seconds / 86400:.1f} d" if seconds > 86400 else
            f"{seconds / 3600:.1f} h" if seconds > 3600 else
            f"{seconds / 60:.0f} min" if seconds > 60 else
            f"{seconds:.0f} s")


def _resample_stc(profile, width, step):
    """The STC profile, averaged over depth windows when width is set
    (the samples sorted by depth first)."""
    if not width:
        return profile
    order = np.argsort(profile["depth"])
    depth = np.asarray(profile["depth"], float)[order]
    out = dict(profile)
    for key in ("temperature", "sound_speed"):
        out["depth"], out[key] = core.smooth_profile(
            depth, np.asarray(profile[key], float)[order], width, step)
    return out


def ana_6(session, p):
    """Sound-speed maps c(z, t) of the channels ticked."""
    S = session.data
    flags, flag_text = _sound_flags(p)
    print(f"sound speed: {core.physics('SOUND_FORMULA')}; {flag_text}; "
          f"g = {core.physics('GRAVITY'):g} m s⁻², {core.eos_summary()}")
    records, speeds, info = [], {}, {}
    available = list(session.require("A_T")[0])
    channel = cn.COMBINED if cn.COMBINED in available else available[0]
    if channel != cn.COMBINED:
        print(f"no Combined channel in the data loaded: {channel} is used")
    for name, time, depth, T in _records(
            session, dict(p, CHANNELS=[channel]), with_chain=False):
        core.check_cancel()
        c, details = core.sound_speed_matrix(depth, T, **flags)
        speeds[name], info[name] = c, details
        records.append((name, time, depth, c))
        print(f"{name}: c = {np.nanmin(c):.2f} – {np.nanmax(c):.2f} m s⁻¹ "
              f"(mean density ρ̄ = {details['rho_mean']:.2f} kg m⁻³, "
              f"S = {details['S']:g} PSU"
              + (f", T fixed at {details['T_reference']:g} °C"
                 if details["T_reference"] is not None else "") + ")")
    if not records:
        raise StepError("tick at least one channel")
    folder, stc = _stc_selection(p)
    marks = [(_day_month(start), start) for _, start in stc]
    if stc:
        first = min(r[1][0] for r in records)
        last = max(r[1][-1] for r in records)
        outside = [m for m in marks if not first <= m[1] <= last]
        if outside:
            print(f"{len(outside)} of {len(marks)} STC profile(s) outside "
                  f"the DTS record ({stamp(first)} → {stamp(last)} UTC): "
                  f"not marked on the maps")
        marks = [m for m in marks if first <= m[1] <= last]
    S.update(A_SOUND_SPEED=speeds, A_SOUND_INFO=info,
             A_SOUND_FLAGS=flag_text)
    return [("Sound speed maps",
             figs.sound_speed_maps(records, marks, shading(p),
                                   f"Speed of sound "
                                   f"({core.physics('SOUND_FORMULA')}; "
                                   f"{flag_text})"))]


def ana_6_stc(session, p):
    """STC profiles (temperature, sound speed) against the DTS."""
    S = session.data
    flags, flag_text = _sound_flags(p)
    folder, stc = _stc_selection(p)
    if not stc:
        raise StepError("no STC profile to load: choose the STC folder and "
                        "tick profiles in 'Individual STC profiles'"
                        + (" (with 'Only STC profiles at LéXPLORE', the "
                           "profiles ticked must lie within the LéXPLORE "
                           "radius of the physical parameters)"
                           if p.get("STC_AT_LEXPLORE_ONLY") else ""))
    dts_root = (p.get("DTS_FOLDER") or "") if p.get("USE_DTS_STC", True) \
        else ""
    products = core.find_dts_products(dts_root)
    if not p.get("USE_DTS_STC", True):
        print("DTS not included (box DTS folder unticked)")
    if products:
        print(f"DTS folder {dts_root}: {len(products)} preprocessed "
              f"record(s) with a Combined channel: "
              + ", ".join(c for _, c in products))
    elif dts_root:
        print(f"no preprocessed DTS file with a Combined channel in "
              f"{dts_root}: no DTS profile on the STC figures")
    chain = None                         # LéXPLORE chain, whole record
    chain_root = (p.get("LEXPLORE_FOLDER") or "") \
        if p.get("USE_LEXPLORE_STC", True) else ""
    if not p.get("USE_LEXPLORE_STC", True):
        print("LéXPLORE chain not included (box LéXPLORE folder unticked)")
    if chain_root:
        try:
            chain_time, chain_z, chain_T, used = \
                core._load_lexplore_folder(chain_root)
            if chain_time.size:
                chain = (chain_time, np.asarray(chain_z, float), chain_T,
                         np.median(np.diff(chain_time)) if chain_time.size > 1
                         else np.timedelta64(600, "s"))
                print(f"LéXPLORE chain: {len(used)} file(s), "
                      f"{stamp(chain_time[0])} → {stamp(chain_time[-1])} UTC")
        except Exception as error:                 # noqa: BLE001
            print(f"LéXPLORE chain not read ({chain_root}): {error}")
    if chain is None and chain_root:
        print("no LéXPLORE chain data: the STC figures show the STC and the "
              "DTS only")
    results, figures = {}, []
    # positions: header of the .vp2 file of each profile, LéXPLORE from the
    # physical parameters, lake outline saved in the STC folder
    points = []
    for file_name, start in stc:
        lat, lon = core.stc_position(folder, file_name)
        points.append((_day_month(start), lat, lon))
        print(f"STC {file_name}: " + (f"{lat:.5f} N, {lon:.5f} E (.vp2 "
                                      f"header)" if np.isfinite(lat) else
                                      "no position (no .vp2 file with the "
                                      "same name)"))
    outline = core.load_lake_outline(folder)
    if not outline:
        print(f"no lake outline (.geojson) in {folder}: the map shows the "
              f"points only")
    lexplore = (core.physics("LEXPLORE_LAT"), core.physics("LEXPLORE_LON"))
    figures.append(("STC positions",
                    figs.stc_position_map(outline, lexplore, points)))
    width = p.get("STC_WINDOW") if p.get("IS_STC_RESAMPLING") else None
    step = p.get("STC_WINDOW_STEP") or width
    if width:
        print(f"profiles averaged over {width:g} m depth windows, every "
              f"{step:g} m")
    for (file_name, _), (_, lat, lon) in zip(stc, points):
        core.check_cancel()
        profile = core.read_stc_csv(os.path.join(folder, file_name))
        start, end = profile["start"], profile["end"]
        span = (end - start) / np.timedelta64(1, "s")
        shown = _resample_stc(profile, width, step)
        shown["resolution"] = core.resolution_text(shown["depth"])
        c_stc, _ = core.sound_speed_matrix(shown["depth"],
                                           shown["temperature"], **flags)
        dts = []
        closest = core.closest_dts_profile(products, start)
        if closest is not None:             # closest Combined DTS profile
            grid, T_profile = core.read_dts_profile(
                closest["path"], closest["index"], closest["channel"])
            gap = closest["shift_s"]
            how = (f"{closest['configuration']}, Δt = "
                   f"{'+' if gap >= 0 else '−'}{_gap_text(abs(gap))}, "
                   f"{core.resolution_text(grid)}")
            T_part = T_profile[:, None]
            if width:
                grid, T_part = core.smooth_matrix(grid, T_part, width, step)
            c_part, _ = core.sound_speed_matrix(grid, T_part, **flags)
            dts.append(dict(name=cn.COMBINED, depth=grid, T=T_part[:, 0],
                            T_std=None, c=c_part[:, 0], c_std=None, how=how,
                            times=np.array([closest["time"]]),
                            file=closest["path"]))
            print(f"STC {file_name} ({stamp(start)} → {stamp(end)} UTC, "
                  f"{span:.0f} s): closest DTS profile {stamp(closest['time'])}"
                  f" UTC ({how}, {closest['path']})")
        if chain is not None:              # closest chain profile, if any
            chain_time, chain_z, chain_T, chain_step = chain
            index = nearest_index(chain_time, start)
            gap = (chain_time[index] - start) / np.timedelta64(1, "s")
            if abs(gap) <= 2 * chain_step / np.timedelta64(1, "s"):
                grid, T_part = chain_z, np.asarray(chain_T, float)[:, [index]]
                if width:
                    grid, T_part = core.smooth_matrix(grid, T_part, width,
                                                      step)
                good = np.isfinite(T_part[:, 0])
                c_part, _ = core.sound_speed_matrix(grid[good],
                                                    T_part[good], **flags)
                how = (f"Δt = {'+' if gap >= 0 else '−'}"
                       f"{_gap_text(abs(gap))}, "
                       f"{core.resolution_text(grid[good], spread=True)}")
                dts.append(dict(name="LeXPLORE chain", depth=grid[good],
                                T=T_part[good, 0], T_std=None,
                                c=c_part[:, 0], c_std=None, how=how,
                                times=np.array([chain_time[index]])))
                print(f"  LéXPLORE chain: profile {stamp(chain_time[index])}"
                      f" UTC ({how})")
            else:
                print(f"  LéXPLORE chain: no profile at that time (closest "
                      f"{_gap_text(abs(gap))} away)")
        # RMS of the differences over depth windows (STC measured =
        # reference)
        rms_width = p.get("RMS_WINDOW") or 2.0
        rms_T, rms_c = [], []
        stc_z = shown["depth"]
        rms_c.append(("STC recalculated − STC measured", "STC",
                      *core.rms_difference_profile(
                          stc_z, shown["sound_speed"], stc_z, c_stc,
                          rms_width)))
        for entry in dts:
            label = f"{entry['name']} ({entry['how']})"
            rms_T.append((f"{label} − STC", entry["name"],
                          *core.rms_difference_profile(
                              stc_z, shown["temperature"], entry["depth"],
                              entry["T"], rms_width)))
            rms_c.append((f"{label} − STC measured", entry["name"],
                          *core.rms_difference_profile(
                              stc_z, shown["sound_speed"], entry["depth"],
                              entry["c"], rms_width)))
        for label, _, _, values in rms_T + rms_c:
            if values.size:
                print(f"  RMS {label}: {np.sqrt(np.nanmean(values ** 2)):.3f}"
                      f" (whole profile, {rms_width:g} m windows)")
        measured = shown["sound_speed"]
        difference = c_stc - measured
        good = np.isfinite(difference)
        if good.any():
            print(f"  c recalculated from the STC temperature − measured c: "
                  f"mean {np.mean(difference[good]):+.2f} m s⁻¹, rms "
                  f"{np.sqrt(np.mean(difference[good] ** 2)):.2f} m s⁻¹")
        results[file_name] = dict(profile, c_recalculated=c_stc, dts=dts,
                                  rms_T=rms_T, rms_c=rms_c,
                                  latitude=lat, longitude=lon,
                                  descent_speed=core.stc_descent_speed(
                                      profile))
        figures.append((f"STC {_day_month(start)}",
                        figs.stc_profile_figure(shown, c_stc, dts,
                                                flag_text,
                                                core.physics(
                                                    "SOUND_FORMULA"),
                                                rms_T, rms_c, rms_width)))
    S.update(A_STC=results)
    return figures


# ---------------------------------------------------------------------------
# registry: step id -> (function, steps that must have run before)
# FIGURE_OWNER: the step whose figure tabs a step replaces; DISPLAY_ONLY:
# steps that only redraw (they neither complete nor invalidate anything)
# ---------------------------------------------------------------------------
FIGURE_OWNER = {"pre.1.replot": "pre.1.concat", "pre.3.replot": "pre.3",
                "ana.4.1.1.fit": "ana.4.1.1",
                "ana.0.instants": "ana.0.1", "ana.0.replot": "ana.0.1",
                "ana.0.select": "ana.0.1"}


def skip_chain(session):
    """Run All of Depth Calibration: the chain fit only when chain data
    are used and cover the DTS window."""
    if not session.data.get("IS_LEXPLORE_DATA_AVAILABLE"):
        return ("LeXPLORE chain not available ("
                f"{session.data.get('LEXPLORE_STATUS', 'unknown reason')}): "
                "the manual calibration is used")
    return ""


def skip_manual(session):
    if session.data.get("IS_LEXPLORE_DATA_AVAILABLE"):
        return "the LeXPLORE T-chain calibration is used"
    return ""


SKIPS = {"pre.2.1": skip_chain, "pre.2.2": skip_manual}
DISPLAY_ONLY = {"pre.1.replot", "pre.3.replot", "ana.0.instants",
                "ana.4.1.1.fit",
                "ana.0.replot", "ana.0.select"}
# steps that use the individual profiles of Load preprocessed data
USE_PROFILE_TIMES = ("ana.4.1.1",)
# figure brought forward after a run (instead of the first one)
FOCUS_FIGURE = {"ana.3.2": "Spectrum"}
STEPS = {
    "pre.1.load": (pre_1_load, []),
    "pre.1.mirror": (pre_1_mirror, ["pre.1.load"]),
    "pre.1.concat": (pre_1_concat, ["pre.1.mirror"]),
    "pre.1.replot": (pre_1_replot, ["pre.1.concat"]),
    "pre.2.1": (pre_2_1, ["pre.1.concat"]),
    "pre.2.2": (pre_2_2, ["pre.1.concat"]),
    "pre.3": (pre_3, ["pre.1.concat"]),
    "pre.3.replot": (pre_3_replot, ["pre.3"]),
    "pre.4": (pre_4, ["pre.3"]),
    "ana.0": (ana_0, []),
    "ana.0.1": (ana_0_1, ["ana.0"]),
    "ana.1": (ana_1, ["ana.0.1"]),
    "ana.0.3": (ana_0_3, ["ana.0.1"]),
    "ana.0.instants": (ana_0_instants, ["ana.0.1"]),
    "ana.0.replot": (ana_0_replot, ["ana.0.1"]),
    "ana.0.select": (ana_0_replot, ["ana.0.1"]),
    "ana.0.2": (ana_0_2, ["ana.0.1"]),
    "ana.2": (ana_2, ["ana.0.1"]),
    "ana.3.1": (ana_3_1, ["ana.0.2"]),
    "ana.3.2": (ana_3_2, ["ana.3.1"]),
    "ana.4.1.1": (ana_4_1_1, ["ana.0.1"]),
    "ana.4.1.1.fit": (ana_4_1_1_fit, ["ana.4.1.1"]),
    "ana.4.1.2": (ana_4_1_2, ["ana.0.1"]),
    "ana.4.2.5": (ana_4_2_5, ["ana.0.1"]),
    "ana.4.2.6": (ana_4_2_6, ["ana.0.1"]),
    "ana.4.2.9": (ana_4_2_9, ["ana.0.1"]),
    "ana.5": (ana_5, ["ana.0.1"]),
    "ana.6": (ana_6, ["ana.0.1"]),
    "ana.6.stc": (ana_6_stc, []),
}


# ---------------------------------------------------------------------------
# Display of the analysis figures: colour map chosen in the panel, and an
# 'Update plot' step (<step>.replot) for every analysis step that draws
# figures - the step drawn again, without marking the other steps outdated
# ---------------------------------------------------------------------------
def apply_colour_map(figures, cmap):
    """Colour map of every map (pcolormesh, image) of the figures; the
    colour bars follow.  'default' keeps the colour map of each figure."""
    if not cmap or cmap == "default":
        return figures
    from matplotlib.collections import QuadMesh
    from matplotlib.image import AxesImage
    for _, figure in figures:
        for ax in getattr(figure, "axes", []):
            for artist in list(ax.collections) + list(ax.images):
                if isinstance(artist, (QuadMesh, AxesImage)):
                    artist.set_cmap(cmap)
    return figures


WHOLE_RECORD = "Whole record"
WINDOWED_KEYS = ("A_TIME", "A_Z", "A_T", "A_LEXPLORE")


def window_label(label, start, end):
    """Text of a time window in the lists 'Time window'."""
    return f"{label}: {str(start).strip()} → {str(end).strip()}"


def parse_window(text):
    """'W1: start → end' -> (label, start, end) as datetime64, or None for
    the whole record."""
    if not text or text == WHOLE_RECORD or "→" not in text:
        return None
    label, times = text.split(":", 1)
    start, end = (part.strip() for part in times.split("→"))
    t0, t1 = utc(start), utc(end)
    if t0 is None or t1 is None or t1 <= t0:
        raise StepError(f"time window {text!r}: the end must come after "
                        f"the start")
    return label.strip(), t0, t1


def windowed_data(S, window):
    """The analysis records restricted to a time window (new dicts)."""
    label, t0, t1 = window
    TIME, Z, T = {}, {}, {}
    for channel, time in S["A_TIME"].items():
        keep = (time >= t0) & (time <= t1)
        if keep.sum() >= 2:
            TIME[channel] = time[keep]
            Z[channel] = S["A_Z"][channel]
            T[channel] = S["A_T"][channel][:, keep]
    if not T:
        raise StepError(f"time window {label}: fewer than 2 profiles of "
                        f"any channel between {stamp(t0)} and {stamp(t1)}")
    chain = S.get("A_LEXPLORE") or {}
    if chain:
        keep = (chain["time"] >= t0) & (chain["time"] <= t1)
        chain = (crop_chain(chain, keep)
                 if keep.sum() >= 2 else {})
    return {"A_TIME": TIME, "A_Z": Z, "A_T": T, "A_LEXPLORE": chain}


WHOLE_COLUMN = "Whole column"


def layer_choices(layers):
    """Items of the lists 'Layer' after the multi-layer decomposition."""
    items = [WHOLE_COLUMN]
    if not layers or not layers.get("interfaces"):
        return items
    n = 2 if layers["layering"] == "Two layers" else 3
    names = (["Top layer: surface – Z1", "Bottom layer: Z1 – bottom"]
             if n == 2 else
             ["Top mixed layer: surface – Z1", "Metalimnion: Z1 – Z2",
              "Bottom layer: Z2 – bottom"])
    return items + names


# layer name (before ':' in the lists) -> number from the surface
LAYER_NUMBERS = {"Top layer": 1, "Top mixed layer": 1, "Metalimnion": 2,
                 "Bottom layer": None}       # None: the last layer


def layer_bounds(S, name, number, t0=None, t1=None):
    """Depth range (top, bottom) of layer `number` (1, 2, 3) for one
    record: the interfaces of the multi-layer decomposition averaged over
    time (inside the time window when given).  A record that was not part
    of the decomposition takes the interfaces of 'mean', else of the first
    record."""
    layers = S.get("A_LAYERS") or {}
    interfaces = layers.get("interfaces") or {}
    if not interfaces:
        raise StepError("no layers: run the Multi-layer decomposition first")
    key = name if name in interfaces else (
        cn.COMBINED if cn.COMBINED in interfaces
        else next(iter(interfaces)))
    time, levels = interfaces[key]
    keep = np.ones(time.size, bool)
    if t0 is not None:
        keep = (time >= t0) & (time <= t1)
    means = [float(np.nanmean(z[keep])) if np.isfinite(z[keep]).any()
             else np.nan for z in levels]
    edges = [-np.inf] + means + [np.inf]
    if number > len(edges) - 1:
        raise StepError(f"layer {number} does not exist with "
                        f"{layers['layering'].lower()}")
    top, bottom = edges[number - 1], edges[number]
    if not (np.isfinite(top) or np.isfinite(bottom)) and len(means):
        raise StepError(f"{name}: no interface found for layer {number}")
    return top, bottom


def layered_data(S, label, window):
    """The analysis records cropped to one layer (rows between the
    time-mean interfaces)."""
    label = label.strip()
    number = LAYER_NUMBERS.get(label)
    if number is None:                        # the bottom layer
        layers = S.get("A_LAYERS") or {}
        number = 2 if layers.get("layering") == "Two layers" else 3
    t0, t1 = (window[1], window[2]) if window else (None, None)
    Z, T = {}, {}
    for channel, depth in S["A_Z"].items():
        top, bottom = layer_bounds(S, channel, number, t0, t1)
        rows = (depth >= top) & (depth <= bottom)
        if rows.sum() < 3:
            raise StepError(f"{channel}: layer {label} holds fewer than 3 "
                            f"depths ({top:.1f} – {bottom:.1f} m)")
        Z[channel] = depth[rows]
        T[channel] = S["A_T"][channel][rows]
        print(f"{channel}: layer {label} = {max(top, depth[0]):.1f} – "
              f"{min(bottom, depth[-1]):.1f} m ({rows.sum()} depths)")
    chain = S.get("A_LEXPLORE") or {}
    if chain:
        top, bottom = layer_bounds(S, CHAIN_NAME, number, t0, t1)
        rows = (chain["depth"] >= top) & (chain["depth"] <= bottom)
        chain = ({"time": chain["time"], "depth": chain["depth"][rows],
                  "temperature": chain["temperature"][rows]}
                 if rows.sum() >= 2 else {})
    return {"A_Z": Z, "A_T": T, "A_LEXPLORE": chain}


def _with_colour_map(function):
    def step(session, p):
        S = session.data
        window = parse_window(p.get("TIME_WINDOW"))
        layer = p.get("LAYER") or WHOLE_COLUMN
        layer = None if layer == WHOLE_COLUMN else layer.split(":")[0]
        if getattr(function, "own_layer", False) and window is None:
            layer = None                      # the step applies the layer
        if (window is None and layer is None) or "A_T" not in S:
            return apply_colour_map(function(session, p) or [],
                                    p.get("CMAP"))
        saved = {key: S.get(key) for key in WINDOWED_KEYS}
        saved_flag = S.get("A_IS_LEXPLORE")
        windowed = dict(saved)
        if window is not None:
            windowed.update(windowed_data(S, window))
            S.update(windowed)
            S["A_WINDOW"] = (window[0], str(window[1]), str(window[2]))
            print(f"time window {window[0]}: {stamp(window[1])} -> "
                  f"{stamp(window[2])} UTC")
        if layer is not None and not getattr(function, "own_layer", False):
            windowed.update(layered_data(S, layer, window))
            S.update(windowed)
            S["A_LAYER"] = layer
        S["A_IS_LEXPLORE"] = bool(windowed["A_LEXPLORE"]) and bool(saved_flag)
        window = window or (layer,)
        try:
            figures = function(session, p) or []
        finally:                   # the whole record back for other steps
            for key in WINDOWED_KEYS:
                if S.get(key) is windowed[key]:
                    S[key] = saved[key]
            S["A_IS_LEXPLORE"] = saved_flag
            S.pop("A_WINDOW", None)
            S.pop("A_LAYER", None)
        window = (" ".join(x for x in (
            (window[0] if len(window) == 3 else None), layer) if x),)
        for index, (title, figure) in enumerate(figures):
            if hasattr(figure, "suptitle") and getattr(figure, "_suptitle",
                                                       None) is not None:
                text = figure._suptitle.get_text()
                if window[0] and window[0].lower() not in text.lower():
                    figure._suptitle.set_text(text + f"  [{window[0]}]")
        return apply_colour_map(figures, p.get("CMAP"))
    step.__doc__ = function.__doc__
    return step


# ---------------------------------------------------------------------------
# LeXPLORE chain in the steps that work on gridded records only: the chain is
# interpolated onto a uniform 1 m grid and treated as one more channel
# ---------------------------------------------------------------------------
CHAIN_NAME = "LeXPLORE chain"
CHAIN_AS_CHANNEL = {"ana.4.1.2": "CHANNELS",
                    "ana.4.2.5": "CHANNELS", "ana.4.2.6": "CHANNELS",
                    "ana.4.2.9": "CHANNELS"}


def chain_on_grid(chain, step=1.0):
    """The chain T(depth, time) interpolated onto a uniform depth grid."""
    depth = np.asarray(chain["depth"], float)
    grid = np.arange(np.ceil(depth.min()), np.floor(depth.max()) + 0.5 * step,
                     step)
    T = np.asarray(chain["temperature"], float)
    out = np.full((grid.size, T.shape[1]), np.nan)
    for index in range(T.shape[1]):
        good = np.isfinite(T[:, index])
        if good.sum() >= 2:
            out[:, index] = np.interp(grid, depth[good], T[good, index],
                                      left=np.nan, right=np.nan)
    return grid, out


def _with_chain(function, key):
    def step(session, p):
        S = session.data
        chain = S.get("A_LEXPLORE") or {}
        if not (p.get("INCLUDE_CHAIN") and S.get("A_IS_LEXPLORE") and chain):
            return function(session, p)
        grid, T = chain_on_grid(chain)
        saved = {k: S[k] for k in ("A_TIME", "A_Z", "A_T")}
        S["A_TIME"] = dict(saved["A_TIME"], **{CHAIN_NAME: chain["time"]})
        S["A_Z"] = dict(saved["A_Z"], **{CHAIN_NAME: grid})
        S["A_T"] = dict(saved["A_T"], **{CHAIN_NAME: T})
        field = CHAIN_AS_CHANNEL[key]
        try:
            if field == "CHANNELS":            # one more channel
                q = dict(p, CHANNELS=list(p.get("CHANNELS") or [])
                         + [CHAIN_NAME])
                return function(session, q)
            # one channel: the chain first, then the channel (whose
            # results stay stored for the following steps)
            figures = [(f"{title} – {CHAIN_NAME}", figure) for title, figure
                       in (function(session, dict(p, **{field: CHAIN_NAME}))
                           or [])]
            return (function(session, p) or []) + figures
        finally:
            for k, value in saved.items():
                S[k] = value
    step.__doc__ = function.__doc__
    step.own_layer = getattr(function, "own_layer", False)
    return step


for _key in CHAIN_AS_CHANNEL:
    _function, _requires = STEPS[_key]
    STEPS[_key] = (_with_chain(_function, _key), _requires)

for _key in [k for k in STEPS if k.startswith("ana.")
             and k not in ("ana.0", "ana.0.1", "ana.5")]:
    _function, _requires = STEPS[_key]
    STEPS[_key] = (_with_colour_map(_function), _requires)
for _key in [k for k in list(STEPS) if k.startswith("ana.")
             and k.count(".") >= 1 and not k.endswith((".replot", ".select", ".fit",
                                                       ".instants"))
             and k not in ("ana.0", "ana.0.1", "ana.5")]:
    STEPS[_key + ".replot"] = (STEPS[_key][0], [_key])
    FIGURE_OWNER[_key + ".replot"] = _key
    DISPLAY_ONLY.add(_key + ".replot")
