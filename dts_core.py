"""dts_core.py -- computation library of the DTS GUI (Silixa XT-DTS, MIRAGE 2026).

Independent copy of the computation functions needed by the GUI (reading of
the XT WITSML files and of the LeXPLORE chain, folding of the U-shaped cable,
depth calibration, preprocessed NetCDF product, isotherms, FFTs, three-layer
fit, staircases). The functions were taken from DTS_XT_lib.py on
13.11.2026; from now on this file evolves with the GUI only.

No plotting code in this file: the figures are built in gui_figures.py.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import threading

import numpy as np

# name and version of the program that writes the files (set by dts_gui)
WRITER = "DTS GUI"


class Interrupted(BaseException):
    """Raised inside a long computation when the user presses Interrupt.
    A BaseException, so that the 'except Exception' of the file loops do
    not swallow it."""


CANCEL = threading.Event()


def check_cancel():
    """Stop the current computation when the user asked for it."""
    if CANCEL.is_set():
        raise Interrupted("interrupted by the user")

_DIFFLOSS_MODES = {"0": "fixed value", "1": "temperature matching",
                   "2": "external probe", "3": "double ended"}

_FNAME_TIME = re.compile(r"_(\d{17})\.xml$")

_EPOCH_MS = "milliseconds since 1970-01-01 00:00:00 UTC"


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _num(text, default=np.nan):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _parse_time(text: str) -> np.datetime64:
    # '2011-01-01T02:33:15.000Z' -> datetime64[ms] (naive, instrument clock)
    return np.datetime64(text.strip().rstrip("Z"), "ms")


def read_xt_xml(path: str) -> dict:
    """Read one XT-DTS WITSML file.

    Returns a dict with the profile arrays ('x', 'st', 'ast', 'rst', 'rast',
    'tmp'; 'rst'/'rast' are None for single-ended files) and the scalar
    metadata needed for processing.  The complete <customData> tree is kept
    as a flat dict in 'settings' (keys are tag paths, e.g.
    'UserConfiguration/ChannelConfiguration/AcquisitionConfiguration/SamplingInterval').
    """
    root = ET.parse(path).getroot()
    log = next(el for el in root.iter() if _strip_ns(el.tag) == "log")
    top = {_strip_ns(el.tag): el for el in log}

    # ---- data block -------------------------------------------------------
    logdata = top["logData"]
    mnem = None
    rows = []
    for el in logdata:
        t = _strip_ns(el.tag)
        if t == "mnemonicList":
            mnem = [m.strip() for m in el.text.split(",")]
        elif t == "data":
            rows.append(el.text)
    arr = np.array(" ".join(rows).replace(",", " ").split(), dtype=float)
    arr = arr.reshape(-1, len(mnem))
    col = {m: arr[:, i] for i, m in enumerate(mnem)}

    # ---- custom data (flatten) --------------------------------------------
    custom = top["customData"]
    settings = {}

    def walk(el, prefix):
        for ch in el:
            key = f"{prefix}/{_strip_ns(ch.tag)}" if prefix else _strip_ns(ch.tag)
            if len(ch):
                walk(ch, key)
            elif ch.text is not None:
                # keep the first occurrence of repeated keys (e.g. per-channel
                # blocks) but also store an indexed copy
                if key in settings:
                    i = 1
                    while f"{key}[{i}]" in settings:
                        i += 1
                    settings[f"{key}[{i}]"] = ch.text.strip()
                else:
                    settings[key] = ch.text.strip()

    walk(custom, "")

    # the user configuration may hold several ChannelConfiguration blocks;
    # extract the one for this file's channel
    chan_name = os.path.basename(os.path.dirname(path))
    user_cfg = {}
    for cc in custom.iter():
        if _strip_ns(cc.tag) == "ChannelConfiguration":
            d = {}
            for e in cc.iter():
                if not len(e) and e.text is not None:
                    d[_strip_ns(e.tag)] = e.text.strip()
            if d.get("ChannelName") == chan_name or not user_cfg:
                user_cfg = d

    def s(key):
        for k, v in settings.items():
            if k.endswith(key):
                return v
        return None

    is_de = s("isDoubleEnded") == "1"
    name = top["name"].text if "name" in top else ""
    m = _FNAME_TIME.search(os.path.basename(path))

    return dict(
        file=path,
        x=col["LAF"],
        st=col.get("ST"),
        ast=col.get("AST"),
        rst=col.get("REV-ST") if is_de else None,
        rast=col.get("REV-AST") if is_de else None,
        tmp=col.get("TMP"),
        time_start=_parse_time(top["startDateTimeIndex"].text),
        time_end=_parse_time(top["endDateTimeIndex"].text),
        file_stamp=m.group(1) if m else None,
        acquisition_time=_num(s("acquisitionTime")),
        ref_temp=_num(s("referenceTemperature")),
        probe1_temp=_num(s("probe1Temperature")),
        probe2_temp=_num(s("probe2Temperature")),
        fibre_ok=s("fibreStatusOk") == "1",
        fibre_break=_num(s("fibreBreakLocation")),
        status=s("measurementStatus"),
        double_ended=is_de,
        forward_channel=int(_num(s("forwardMeasurementChannel"), -1)),
        reverse_channel=int(_num(s("reverseMeasurementChannel"), -1)),
        serial=top["nameWell"].text if "nameWell" in top else None,
        log_name=name,
        configuration=s("ConfigurationName"),
        comment=s("ConfigurationComment"),
        channel_name=user_cfg.get("ChannelName", chan_name),
        gamma=_num(s("TemperatureScalingFactor")),
        diff_loss_dB_km=_num(user_cfg.get("DifferentialLoss")),
        sampling_interval=_num(user_cfg.get("SamplingInterval")),
        measurement_length=_num(user_cfg.get("MeasurementLength")),
        acquisition_time_cfg=_num(user_cfg.get("AcquisitionTime")),
        measurement_interval=_num(s("MeasurementInterval")),
        diff_loss_mode=_DIFFLOSS_MODES.get(user_cfg.get("DifferentialLossCalculation"),
                                           user_cfg.get("DifferentialLossCalculation")),
        paired_channel=int(_num(user_cfg.get("PairedChannel"), -1)),
        channel_config=user_cfg,
        settings=settings,
    )


def read_datasets(root, files=None, utc_offset=None, verbose=True):
    """Read one measurement file per channel of ``root`` (a configuration
    folder, one sub-folder per channel).

    files = None            -> the first file of each channel sub-folder;
    files = {channel: file} -> that file for that channel, given as a file
        name ('channel 1_20110101023315605.xml') or as a time stamp printed
        by :func:`available_datasets` ('2011-01-01_02-33-15').  Channels not
        listed keep their first file.
    utc_offset : clock offset from :func:`instrument_clock_offset`.  Stamps
        on the instrument clock (years behind, see
        :func:`correct_instrument_time`) are corrected to UTC at loading;
        the originals are kept under 'time_start_instrument' /
        'time_end_instrument' and 'clock_corrected' is set to True.

    Returns {channel: record}, each record the dict of :func:`read_xt_xml`
    plus 'time_mid' = centre of the measurement period (the time stamp of
    the profile: 0.5 * (time_start + time_end), on the corrected times).
    """
    out = {}
    for ch in sorted(os.listdir(root)):
        p = os.path.join(root, ch)
        if not os.path.isdir(p):
            continue
        xmls = sorted(f for f in os.listdir(p) if f.endswith(".xml"))
        if not xmls:
            continue
        pick = xmls[0]
        want = (files or {}).get(ch)
        if want is not None:
            digits = "".join(c for c in want if c.isdigit())
            cand = [f for f in xmls
                    if f == want or f[:-4].rsplit("_", 1)[-1].startswith(digits)]
            if not cand:
                raise FileNotFoundError(f"{ch}: no file matching {want!r}")
            pick = cand[0]
        rec = read_xt_xml(os.path.join(p, pick))
        rec["clock_corrected"] = False
        if utc_offset is not None:
            t0c, c0 = correct_instrument_time(rec["time_start"], utc_offset)
            t1c, _ = correct_instrument_time(rec["time_end"], utc_offset)
            if c0:
                rec["time_start_instrument"] = rec["time_start"]
                rec["time_end_instrument"] = rec["time_end"]
                rec["time_start"], rec["time_end"] = t0c, t1c
                rec["clock_corrected"] = True
        rec["time_mid"] = rec["time_start"] + \
            (rec["time_end"] - rec["time_start"]) / 2
        out[ch] = rec
        if verbose:
            extra = (f"  (instrument clock corrected -> starts {rec['time_start']} UTC)"
                     if rec["clock_corrected"] else "")
            print(f"{ch}: {pick}{extra}")
    return out


def local_to_UTC(date, time=None, zone="Europe/Zurich", verbose=True):
    """UTC time (numpy datetime64) of a local date & time.

    Either date 'DD.MM.YYYY' with time 'hh:mm:ss' ('.' also accepted), or a
    single string date = 'YYYY-MM-DD hh:mm:ss' with time omitted.  The IANA
    time zone ``zone`` (default Europe/Zurich) handles daylight saving.  All
    user times are given in local time and converted with this function just
    before calling a routine; the routines themselves work in UTC."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if time is None:
        dpart, time = date.strip().split()
        y_, m_, d_ = (int(v) for v in dpart.split("-"))
    else:
        d_, m_, y_ = (int(v) for v in date.split("."))
    h_, mi_, s_ = (int(v) for v in time.replace(".", ":").split(":"))
    local = datetime(y_, m_, d_, h_, mi_, s_, tzinfo=ZoneInfo(zone))
    utc = np.datetime64(local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None))
    if verbose:
        print(f"{zone} ({local.tzname()}) = UTC"
              f"{local.utcoffset().total_seconds()/3600:+.0f} h, of which daylight "
              f"saving {local.dst().total_seconds()/3600:+.0f} h: "
              f"{local:%d.%m.%Y %H:%M:%S} local = {utc} UTC")
    return utc


def instrument_clock_offset(instrument_time, utc_time, verbose=True):
    """Offset to ADD to instrument time stamps to obtain UTC.

    instrument_time : 'YYYY-MM-DD hh:mm:ss' as read on the instrument clock;
    utc_time : the true UTC time of the same moment (numpy datetime64, e.g.
    from :func:`local_to_UTC`).  Returns a numpy timedelta64 (ms)."""
    t = np.datetime64(instrument_time.strip().replace(" ", "T"), "ms")
    off = np.datetime64(utc_time, "ms") - t
    if verbose:
        print(f"instrument clock offset: +{off / np.timedelta64(1, 'D'):.6f} days "
              f"({t} instrument = {np.datetime64(utc_time, 'ms')} UTC)")
    return off


def correct_instrument_time(t, utc_offset):
    """(corrected time, corrected?) for one time stamp.

    A stamp more than one year in the past (such as the 2011 stamps of the
    unset XT clock, about 15 years behind) is taken as instrument time and
    shifted by ``utc_offset``; a recent stamp is already a real time and is
    returned unchanged.  ``utc_offset = None`` disables the correction."""
    t = np.datetime64(t)
    if utc_offset is not None and \
            np.datetime64("now") - t > np.timedelta64(365, "D"):
        return t + utc_offset, True
    return t, False


def build_summary(root, utc_offset=None, csv_name="summary.csv", rebuild=False,
                  verbose=True):
    """Inventory of all measurement files of a configuration folder.

    Scans every channel sub-folder of ``root`` and writes ``csv_name`` in
    ``root``, one line per file: file name, original start time (as written
    by the instrument), corrected start time in UTC (original + utc_offset
    when the stamp is on the instrument clock, see
    :func:`correct_instrument_time`; otherwise equal to the original),
    channel, acquisition duration (s) and spatial resolution (m).

    Returns the table as a pandas DataFrame.  With ``rebuild=False`` an
    existing CSV is read back instead of re-scanning the files."""
    import pandas as pd
    path = os.path.join(root, csv_name)
    if os.path.exists(path) and not rebuild:
        df = pd.read_csv(path)
        if verbose:
            print(f"summary read from {path} ({len(df)} files); "
                  f"use rebuild=True to re-scan the data")
        return df
    rows = []
    for ch in sorted(os.listdir(root)):
        p = os.path.join(root, ch)
        if not os.path.isdir(p):
            continue
        for f in sorted(f for f in os.listdir(p) if f.endswith(".xml")):
            check_cancel()
            r = read_xt_xml(os.path.join(p, f))
            tc, _ = correct_instrument_time(r["time_start"], utc_offset)
            rows.append({
                "file": f,
                "time original": str(r["time_start"].astype("datetime64[s]")).replace("T", " "),
                "time corrected (UTC)": str(tc.astype("datetime64[s]")).replace("T", " "),
                "channel": r["channel_name"],
                "acquisition (s)": round(float(r["acquisition_time"]), 1),
                "resolution (m)": round(float(np.median(np.diff(r["x"]))), 4),
            })
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    if verbose:
        n = int((df["time original"] != df["time corrected (UTC)"]).sum())
        print(f"summary written: {path} ({len(df)} files, {n} time-corrected)")
    return df


def _load_lexplore_folder(root):
    """time, z, T(z, time) concatenated from ALL the Datalakes NetCDF files
    of ``root``, plus the list of files used.

    Every ``.nc`` file in the folder is read (structure of the Level-2 chain
    files, see parseInformation.txt: 'time' = seconds since 1970-01-01
    **UTC**, used as such; 'depth' in m downwards; 'temp'(depth, time) in
    degC) and the records are concatenated along time, sorted, duplicate
    time stamps dropped (the first occurrence wins).  A file whose depth
    axis differs from the first file's is skipped with a printed warning.

    Returns (time, z, T, used): the full concatenated time vector
    (datetime64 ms, UTC), the common depths (m), the temperature matrix
    T(z, time) and the file names used."""
    import netCDF4
    ncs = sorted(f for f in os.listdir(root) if f.endswith(".nc"))
    if not ncs:
        raise FileNotFoundError(f"no .nc file in {root}")
    z_ref, times, temps, used = None, [], [], []
    extras = []                       # per file: {name: (array, dims, attrs)}
    for name in ncs:
        with netCDF4.Dataset(os.path.join(root, name)) as f:
            t = (np.datetime64("1970-01-01T00:00:00") +
                 (np.ma.filled(f["time"][:], np.nan) * 1000)
                 .astype("timedelta64[ms]"))
            z = np.ma.filled(f["depth"][:], np.nan)
            T = np.ma.filled(f["temp"][:, :], np.nan)
            extra = {}
            for vname, var in f.variables.items():
                if vname in ("time", "depth", "temp"):
                    continue
                try:
                    data = np.ma.filled(var[...].astype(float), np.nan)
                except (TypeError, ValueError):
                    continue                      # non-numeric variable
                extra[vname] = (np.asarray(data), tuple(var.dimensions),
                                {a: str(getattr(var, a))
                                 for a in var.ncattrs()})
        if z_ref is None:
            z_ref = z
        elif z.size != z_ref.size or not np.allclose(z, z_ref):
            print(f"WARNING: {name} skipped, its depth axis differs from "
                  f"{used[0]}")
            continue
        times.append(t)
        temps.append(T)
        extras.append(extra)
        used.append(name)
    time = np.concatenate(times)
    T = np.concatenate(temps, axis=1)
    order = np.argsort(time, kind="stable")
    time, T = time[order], T[:, order]
    first_of_each = np.concatenate(([True], np.diff(time) >
                                    np.timedelta64(0, "ms")))
    variables = {}
    for vname, (data, dims, attrs) in extras[0].items():
        if "time" in dims:                        # concatenated in time
            axis = dims.index("time")
            parts = [e[vname][0] for e in extras if vname in e
                     and e[vname][1] == dims]
            if len(parts) != len(extras):
                continue                          # missing in some files
            data = np.concatenate(parts, axis=axis)
            data = np.take(np.take(data, order, axis=axis),
                           np.nonzero(first_of_each)[0], axis=axis)
        variables[vname] = {"data": data, "dims": dims,
                            "units": attrs.get("units", ""),
                            "long_name": attrs.get("long_name", vname)}
    _load_lexplore_folder.variables = variables   # for with_variables
    return time[first_of_each], z_ref, T[:, first_of_each], used


def crop_chain_variables(variables, keep):
    """The chain variables (see :func:`read_lexplore_matrix_fromDisk`) with
    their time axis cut by the boolean mask ``keep``."""
    out = {}
    for name, item in (variables or {}).items():
        data, dims = item["data"], tuple(item["dims"])
        if "time" in dims and np.shape(data)[dims.index("time")] == \
                np.size(keep):
            data = np.compress(keep, data, axis=dims.index("time"))
        out[name] = dict(item, data=data)
    return out


def read_lexplore_matrix_fromDisk(root, t0=None, t1=None, verbose=True,
                                  with_variables=False):
    """time, z, T(z, time) of the LeXPLORE thermistor chain between ``t0``
    and ``t1`` (UTC).

    root : folder holding the Datalakes Level-2 NetCDF files (L2_*.nc); ALL
    the .nc files of the folder are read and concatenated in time (see
    :func:`_load_lexplore_folder`), so a requested window — typically the
    one covered by the DTS record — can span several files.  t0, t1 : UTC
    limits (numpy datetime64 or ISO strings); None keeps the full record;
    for a local time, convert first with :func:`local_to_UTC`.

    When ``verbose``, the coverage of the requested window is checked and
    reported: the files used, the chain record kept, and a WARNING when the
    chain starts after ``t0``, ends before ``t1`` (by more than one chain
    time step) or has internal gaps larger than twice the median step.

    Returns (time, z, T): the times kept (datetime64, UTC), the depths
    (m, downwards) and the temperature matrix T(z, time) in degC (NaN where
    missing); with ``with_variables``, also a dict of every other variable
    of the files (surface and bottom temperature, mixed-layer and
    thermocline depth, Schmidt stability, heat content, ...):
    {name: {"data", "dims", "units", "long_name"}}, cut to the same times."""
    time_all, z, T_all, used = _load_lexplore_folder(root)
    variables_all = getattr(_load_lexplore_folder, "variables", {})
    keep = np.ones(time_all.size, dtype=bool)
    if t0 is not None:
        keep &= time_all >= np.datetime64(t0)
    if t1 is not None:
        keep &= time_all <= np.datetime64(t1)
    t, T = time_all[keep], T_all[:, keep]
    if verbose:
        files = ", ".join(used)
        if t.size:
            print(f"LeXPLORE chain from {len(used)} file(s) ({files}): "
                  f"{t.size} profiles kept, {t[0]} -> {t[-1]} UTC, "
                  f"{z.size} depths ({z[0]:g} - {z[-1]:g} m)")
            step = np.median(np.diff(t)) if t.size > 1 else \
                np.timedelta64(600, "s")
            if t0 is not None and t[0] - np.datetime64(t0) > step:
                print(f"WARNING: the chain record starts "
                      f"{(t[0] - np.datetime64(t0)) / np.timedelta64(1, 'h'):.1f} h "
                      f"after the requested start {np.datetime64(t0)} UTC")
            if t1 is not None and np.datetime64(t1) - t[-1] > step:
                print(f"WARNING: the chain record ends "
                      f"{(np.datetime64(t1) - t[-1]) / np.timedelta64(1, 'h'):.1f} h "
                      f"before the requested end {np.datetime64(t1)} UTC")
            gap_after = np.nonzero(np.diff(t) > 2 * step)[0]
            for index in gap_after:
                print(f"WARNING: gap in the chain record, {t[index]} -> "
                      f"{t[index + 1]} UTC "
                      f"({np.diff(t)[index] / np.timedelta64(1, 'h'):.1f} h)")
        else:
            print(f"LeXPLORE chain from {len(used)} file(s) ({files}): "
                  f"no profile between {t0} and {t1} (UTC) — available "
                  f"{time_all[0]} -> {time_all[-1]} UTC")
    if with_variables:
        return t, z, T, crop_chain_variables(variables_all, keep)
    return t, z, T


def mirror(x, T, xs, xgrid):
    """Profile ``T(x)`` mirrored about ``xs`` and sampled on ``xgrid``:
    T(2 xs - xgrid), NaN outside the data."""
    return np.interp(xgrid, (2.0 * xs - np.asarray(x))[::-1],
                     np.asarray(T)[::-1], left=np.nan, right=np.nan)


def find_max_depth(x, T, scan=None, step=None, min_overlap=10):
    """Mirror distance that best superimposes the profile on its own reverse.

    A U-shaped cable goes down and comes back up, so T(x) ~ T(2 xs - x)
    with xs the distance of the bottom of the U (= max_depth).  The RMS of
    T - mirror(T) is scanned over xs in ``scan`` (None -> middle of the
    profile +/- 15 %) with step ``step`` (None -> a quarter of the sampling),
    and the minimum is refined with a parabola through the three points
    around it, giving a resolution much finer than the sampling.

    Returns (xs_best, rms_best, xs_scan, rms_scan)."""
    if scan is None:
        c0, s0 = 0.5 * (x[0] + x[-1]), 0.15 * (x[-1] - x[0])
        scan = (c0 - s0, c0 + s0)
    if step is None:
        step = 0.25 * float(np.median(np.diff(x)))
    xs_scan = np.arange(scan[0], scan[1] + step / 2, step)
    rms_scan = np.full(xs_scan.size, np.nan)
    for i, xs in enumerate(xs_scan):
        r = T - mirror(x, T, xs, x)
        ok = np.isfinite(r)
        if ok.sum() >= min_overlap:
            rms_scan[i] = np.sqrt(np.mean(r[ok] ** 2))
    k = int(np.nanargmin(rms_scan))
    xs_best, rms_best = float(xs_scan[k]), float(rms_scan[k])
    if 0 < k < xs_scan.size - 1 and np.isfinite(rms_scan[k - 1:k + 2]).all():
        y0, y1, y2 = rms_scan[k - 1:k + 2]       # parabola through 3 points
        den = y0 - 2 * y1 + y2
        if den > 0:
            xs_best = float(xs_scan[k] + 0.5 * step * (y0 - y2) / den)
            rms_best = float(y1 - (y0 - y2) ** 2 / (8 * den))
    return xs_best, rms_best, xs_scan, rms_scan


# ---------------------------------------------------------------------------
# raw cache: every profile of every channel, read once from the XML files
# ---------------------------------------------------------------------------
RAW_CACHE_NAME = "DTS_raw_cache.npz"


def build_raw_cache(root, channels, rebuild=False, verbose=True):
    """All the profiles of the given channels of one configuration.

    The XML files are slow to read, so every profile of every channel is
    read once and kept in ``root/DTS_raw_cache.npz`` (instrument time
    stamps as written in the files, so the cache does not depend on the
    clock correction).  When the cache exists and ``rebuild`` is False it is
    read back; a channel whose list of files changed since the cache was
    written (files added or removed) is read again from the XML files.

    Returns {channel: dict(x (nx,), tmp (nx, nt) float32, time_start (nt,),
    time_end (nt,) datetime64[ms] on the file clock, files (nt,) the files
    read, seen = every XML file found)}.  Files
    whose spatial axis differs from the first file of the channel, or that
    cannot be read, are skipped and listed."""
    path = os.path.join(root, RAW_CACHE_NAME)
    cached = {}
    if os.path.exists(path) and not rebuild:
        with np.load(path, allow_pickle=False) as handle:
            names = [k.split("|")[0] for k in handle.files
                     if k.endswith("|x")]
            for channel in names:
                cached[channel] = {key: handle[f"{channel}|{key}"]
                                   for key in ("x", "tmp", "time_start",
                                               "time_end", "files", "seen")}
    raw, changed = {}, False
    for channel in channels:
        folder = os.path.join(root, channel)
        xmls = sorted(f for f in os.listdir(folder) if f.endswith(".xml"))
        if not xmls:
            raise FileNotFoundError(f"no .xml file in {folder}")
        entry = cached.get(channel)
        if entry is not None:
            if sorted(entry["seen"].tolist()) == xmls:
                raw[channel] = entry
                if verbose:
                    print(f"{channel}: {entry['files'].size} profiles read "
                          f"from the raw cache")
                continue
            if verbose:
                print(f"{channel}: the files changed since the cache was "
                      f"written - reading the XML files again")
        raw[channel] = _read_channel_files(folder, channel, xmls, verbose)
        changed = True
    if changed or rebuild:
        keep = {**{c: v for c, v in cached.items() if c not in raw}, **raw}
        arrays = {f"{c}|{k}": v for c, entry in keep.items()
                  for k, v in entry.items()}
        np.savez(path, **arrays)
        if verbose:
            size = os.path.getsize(path) / 1e6
            print(f"raw cache written: {path} ({size:.1f} MB)")
    return raw


def _read_channel_files(folder, channel, xmls, verbose=True):
    x_ref, profiles, starts, ends, files, skipped = None, [], [], [], [], []
    for index, name in enumerate(xmls):
        check_cancel()
        try:
            record = read_xt_xml(os.path.join(folder, name))
            if x_ref is None:
                x_ref = record["x"]
            elif record["x"].size != x_ref.size or \
                    not np.allclose(record["x"], x_ref):
                raise ValueError("spatial axis differs from the first file")
            profiles.append(record["tmp"].astype(np.float32))
            starts.append(np.datetime64(record["time_start"], "ms"))
            ends.append(np.datetime64(record["time_end"], "ms"))
            files.append(name)
        except Exception as error:                      # noqa: BLE001
            skipped.append((name, str(error)))
        if verbose and (index + 1) % 200 == 0:
            print(f"{channel}: {index + 1}/{len(xmls)} files read")
    if verbose:
        print(f"{channel}: {len(files)} profiles read from the XML files"
              + (f", {len(skipped)} skipped" if skipped else ""))
        for name, why in skipped:
            print(f"    skipped {name}: {why}")
    return dict(x=np.asarray(x_ref, float), tmp=np.column_stack(profiles),
                time_start=np.array(starts, dtype="datetime64[ms]"),
                time_end=np.array(ends, dtype="datetime64[ms]"),
                files=np.array(files), seen=np.array(xmls))


def raw_mid_times(entry, utc_offset=None):
    """Centre of the measurement period of every cached profile, corrected
    to UTC when ``utc_offset`` is given (see correct_instrument_time)."""
    starts = np.array([correct_instrument_time(t, utc_offset)[0]
                       for t in entry["time_start"]], dtype="datetime64[ms]")
    ends = np.array([correct_instrument_time(t, utc_offset)[0]
                     for t in entry["time_end"]], dtype="datetime64[ms]")
    return starts + (ends - starts) / 2


def max_depth_from_raw(entry, xmin, xmax, scan=None, step=None,
                       halfwidth=1.0):
    """Mirror distance of every cached profile: full scan on the first
    profile, +/- halfwidth around it for the others.  NaN for a profile that cannot be fitted."""
    keep = (entry["x"] >= xmin) & (entry["x"] <= xmax)
    x = entry["x"][keep] - xmin
    distances = np.full(entry["tmp"].shape[1], np.nan)
    local_scan = scan
    for index in range(distances.size):
        check_cancel()
        try:
            distance, _, _, _ = find_max_depth(
                x, entry["tmp"][keep, index].astype(float), scan=local_scan,
                step=step)
        except ValueError:
            continue
        if local_scan is scan:
            local_scan = (distance - halfwidth, distance + halfwidth)
        distances[index] = distance
    return distances


def fold_raw(entry, xmin, xmax, max_depth, zgrid):
    """Every cached profile cropped to [xmin, xmax] (x = 0 at xmin) and
    folded at ``max_depth`` on the vertical grid ``zgrid``.  Returns T_down, T_up, T_mean (nz, nt)."""
    keep = (entry["x"] >= xmin) & (entry["x"] <= xmax)
    x = entry["x"][keep] - xmin
    z = np.asarray(zgrid, float)
    nt = entry["tmp"].shape[1]
    T_down = np.empty((z.size, nt))
    T_up = np.empty((z.size, nt))
    for index in range(nt):
        check_cancel()
        profile = entry["tmp"][keep, index].astype(float)
        T_down[:, index] = np.interp(z, x, profile)
        T_up[:, index] = mirror(x, profile, max_depth, z)
    both = np.isfinite(T_down) & np.isfinite(T_up)
    T_mean = np.where(both, 0.5 * (T_down + T_up),
                      np.where(np.isfinite(T_down), T_down, T_up))
    return T_down, T_up, T_mean


CHAIN_GROUP = "LeXPLORE T-chain"


def save_product(root, uncalibrated, calibrated, shifts, attributes,
                 configuration=None, chain=None, preprocessing=None,
                 filename="DTS_preprocessed.nc",
                 readme="README_DTS_preprocessed.md", verbose=True):
    """Write the preprocessed product of the GUI (netCDF-4).

    root           folder of the file;
    uncalibrated,  {channel: {"time", "z", "temperature"}} or None (not
    calibrated     saved): T(z, time) in the connector coordinate, and
                   after the depth calibration (depth from the surface);
    shifts         {channel: {"z_shift_m", "z_shift_std_m", "T_shift_K",
                   "T_shift_std_K"}} applied shifts;
    attributes     global attributes (str, int or float values);
    configuration  pandas DataFrame (rows = settings, columns = channels)
                   saved in the group 'configuration', or None;
    chain          LeXPLORE record {"time", "depth", "temperature"} saved as
                   the group 'LeXPLORE T-chain', or None;
    preprocessing  {"attributes": {name: value}, "series": {name: {channel:
                   {"time": array, other: array, ...}}}} saved in the group
                   'preprocessing' (every variable used by the steps).

    Every group carries the attribute ``kind``: "channel", "LeXPLORE
    chain", "configuration" or "preprocessing"."""
    import netCDF4

    channels = list(shifts)
    path = os.path.join(root, filename)

    def put_time(group, name, values, dimension):
        time = np.asarray(values, dtype="datetime64[ms]")
        group.createDimension(dimension, time.size)
        variable = group.createVariable(name, "i8", (dimension,))
        variable.units = _EPOCH_MS
        variable[:] = time.astype("int64")

    def put_attribute(target, name, value):
        if value is None:
            return
        if isinstance(value, (bool, np.bool_)):
            value = np.int32(bool(value))
        elif isinstance(value, (list, tuple, np.ndarray)):
            value = ", ".join(str(v) for v in value)
        elif isinstance(value, (np.datetime64, np.timedelta64)):
            value = str(value)
        target.setncattr(name.replace(" ", "_"), value)

    with netCDF4.Dataset(path, "w", format="NETCDF4") as f:
        f.title = "DTS preprocessed temperature record (DTS GUI)"
        f.configuration = os.path.basename(os.path.normpath(root))
        f.history = f"written {np.datetime64('now')} UTC by the {WRITER}"
        f.source = (f"{WRITER} (GUI/dts_core.py, save_product); Silixa "
                    "XT-DTS XT13002, MIRAGE October 2026")
        f.channels = ", ".join(channels)
        f.contents = ", ".join(
            (["uncalibrated"] if uncalibrated else [])
            + (["calibrated"] if calibrated else [])
            + (["configuration"] if configuration is not None else [])
            + (["LeXPLORE T-chain"] if chain else [])
            + (["preprocessing variables"] if preprocessing else [])).strip()
        for name, value in attributes.items():
            put_attribute(f, name, value)

        for channel in channels:
            group = f.createGroup(channel)
            group.kind = "channel"
            for name, value in shifts[channel].items():
                group.setncattr(name, float(value))
            reference = (uncalibrated or calibrated)[channel]
            put_time(group, "time", reference["time"], "time")
            group["time"].long_name = ("centre of the measurement period of "
                                       "each profile, UTC")
            for kind, records, meaning in (
                    ("uncalibrated", uncalibrated,
                     "0 at the connector of the XT"),
                    ("calibrated", calibrated,
                     "0 at the water surface (z_shift_m applied)")):
                if not records:
                    continue
                record = records[channel]
                z = np.asarray(record["z"], dtype=float)
                group.createDimension(f"z_{kind}", z.size)
                z_var = group.createVariable(f"z_{kind}", "f8",
                                             (f"z_{kind}",))
                z_var.units = "m"
                z_var.long_name = f"depth, positive downwards, {meaning}"
                z_var[:] = z
                T_var = group.createVariable(f"T_{kind}", "f8",
                                             (f"z_{kind}", "time"),
                                             zlib=True, complevel=4)
                T_var.units = "degC"
                T_var.long_name = f"{kind} temperature (mean of the two legs)"
                T_var[:] = np.asarray(record["temperature"], dtype=float)

        if chain:
            group = f.createGroup(CHAIN_GROUP)
            group.kind = "LeXPLORE chain"
            group.comment = ("LeXPLORE thermistor chain over the DTS record, "
                             "as used in the depth calibration")
            put_time(group, "time", chain["time"], "time")
            group.createDimension("depth", np.size(chain["depth"]))
            depth = group.createVariable("depth", "f8", ("depth",))
            depth.units = "m"
            depth.long_name = "sensor depth, positive downwards from the surface"
            depth[:] = np.asarray(chain["depth"], dtype=float)
            temperature = group.createVariable("temperature", "f8",
                                               ("depth", "time"), zlib=True)
            temperature.units = "degC"
            temperature[:] = np.asarray(chain["temperature"], dtype=float)
            for vname, item in (chain.get("variables") or {}).items():
                dims = tuple(item["dims"])
                if any(d not in ("time", "depth") for d in dims):
                    continue
                data = np.asarray(item["data"], dtype=float)
                if data.shape != tuple(group.dimensions[d].size
                                       for d in dims):
                    continue
                var = group.createVariable(vname, "f8", dims, zlib=True)
                var.units = str(item.get("units", ""))
                var.long_name = str(item.get("long_name", vname))
                var[...] = data

        if configuration is not None:
            group = f.createGroup("configuration")
            group.kind = "configuration"
            group.createDimension("row", configuration.shape[0])
            group.createDimension("column", configuration.shape[1])
            rows = group.createVariable("rows", str, ("row",))
            columns = group.createVariable("columns", str, ("column",))
            table = group.createVariable("table", str, ("row", "column"))
            for i, name in enumerate(configuration.index):
                rows[i] = str(name)
            for j, name in enumerate(configuration.columns):
                columns[j] = str(name)
            for i in range(configuration.shape[0]):
                for j in range(configuration.shape[1]):
                    table[i, j] = str(configuration.iat[i, j])

        if preprocessing:
            group = f.createGroup("preprocessing")
            group.kind = "preprocessing"
            for name, value in preprocessing.get("attributes", {}).items():
                put_attribute(group, name, value)
            for series_name, per_channel in preprocessing.get(
                    "series", {}).items():
                series_group = group.createGroup(series_name)
                for channel, arrays in per_channel.items():
                    sub = series_group.createGroup(channel)
                    put_time(sub, "time", arrays["time"], "time")
                    for name, values in arrays.items():
                        if name == "time":
                            continue
                        variable = sub.createVariable(name, "f8", ("time",))
                        variable[:] = np.asarray(values, dtype=float)

    if readme:
        _write_product_readme(root, filename, readme, uncalibrated,
                              calibrated, shifts, configuration, chain,
                              preprocessing,
                              attributes.get("configuration"))
    if verbose:
        print(f"saved {path} ({os.path.getsize(path) / 1e6:.1f} MB): "
              f"channels {', '.join(channels)}; contents: {f_contents(path)}")
    return path


def f_contents(path):
    import netCDF4
    with netCDF4.Dataset(path) as f:
        return getattr(f, "contents", "")


def _write_product_readme(root, filename, readme, uncalibrated, calibrated,
                          shifts, configuration, chain, preprocessing,
                          name=None):
    """README next to the product: what the file holds."""
    lines = [f"# {filename} — preprocessed DTS temperature record", "",
             f"Written by the {WRITER} (GUI/dts_core.py, save_product) on "
             f"{np.datetime64('now')} UTC for the "
             f"configuration `{name or os.path.basename(os.path.normpath(root))}`. "
             "All times are UTC (int64, ms since 1970-01-01).", "",
             "## Groups", "",
             "Every group has the attribute `kind`.", "",
             "| group | kind | content |", "|---|---|---|"]
    for channel, shift in shifts.items():
        parts = []
        if uncalibrated:
            parts.append("`z_uncalibrated` (m, 0 at the connector of the "
                         "XT), `T_uncalibrated` (degC, z × time)")
        if calibrated:
            parts.append("`z_calibrated` (m, 0 at the water surface), "
                         "`T_calibrated` (degC, z × time)")
        lines.append(f"| `{channel}` | channel | `time`; " + "; ".join(parts)
                     + f"; attributes z_shift_m = {shift['z_shift_m']:+.3f} "
                     f"± {shift['z_shift_std_m']:.3f}, T_shift_K = "
                     f"{shift['T_shift_K']:+.3f} ± {shift['T_shift_std_K']:.3f} |")
    if chain:
        lines.append(f"| `{CHAIN_GROUP}` | LeXPLORE chain | `time`, `depth` "
                     f"(m from the surface), `temperature` (degC, depth × "
                     f"time): the chain over the DTS record |")
    if configuration is not None:
        lines.append("| `configuration` | configuration | `rows`, `columns`, "
                     "`table` (text): settings of each channel read in the "
                     "XML files |")
    if preprocessing:
        series = ", ".join(f"`{name}`" for name in preprocessing.get(
            "series", {}))
        lines.append("| `preprocessing` | preprocessing | attributes: every "
                     "variable used by the preprocessing (settings of each "
                     "step in `settings_json`, mirror distances, grid, "
                     "calibration method, fit depths and windows, ...); "
                     f"sub-groups {series} (time series per channel) |")
    lines += ["", "The `mean` channel, when present, is the "
              "profile-by-profile mean of the DTS channels."]
    with open(os.path.join(root, readme), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def load_preprocessed_netcdf(root, filename="DTS_preprocessed.nc",
                             verbose=True):
    """Read back a preprocessed product (:func:`save_product`, or the
    older notebook format).

    Returns a dict ready for the analysis notebook:
        'TIME'                     {channel: (nt,) datetime64 ms, UTC};
        'Z_CALIBRATED'             {channel: (nz_c,) m, 0 at the water
                                   surface (or at the connector when the
                                   calibration was manual with zero shift)};
        'T_USHAPED_CALIBRATED'     {channel: (nz_c, nt)} degC;
        'Z_UNCALIBRATED'           {channel: (nz_u,) m, 0 at the connector};
        'T_USHAPED_UNCALIBRATED'   {channel: (nz_u, nt)} degC;
        'Z_SHIFT', 'T_SHIFT'       {channel: float} applied shifts (m, K);
        'Z_SHIFT_STD', 'T_SHIFT_STD'  {channel: float} (NaN when absent);
        'IS_TIME_CORRECTION', 'IS_LEXPLORE_DATA_AVAILABLE'  bool;
        'LEXPLORE_ROOT'            folder of the chain files (None when the
                                   file has no such attribute);
        'attrs'                    all global attributes."""
    import netCDF4

    path = os.path.join(root, filename)
    out = dict(TIME={}, Z_CALIBRATED={}, T_USHAPED_CALIBRATED={},
               Z_UNCALIBRATED={}, T_USHAPED_UNCALIBRATED={},
               Z_SHIFT={}, T_SHIFT={}, Z_SHIFT_STD={}, T_SHIFT_STD={})
    with netCDF4.Dataset(path) as f:
        attrs = {name: f.getncattr(name) for name in f.ncattrs()}
        out["LEXPLORE"] = None
        for channel in f.groups:
            group = f[channel]
            group.set_auto_mask(False)
            kind = getattr(group, "kind", "channel")
            if kind == "LeXPLORE chain":
                out["LEXPLORE"] = {
                    "time": np.array(group["time"][:], dtype="int64")
                    .astype("datetime64[ms]"),
                    "depth": np.array(group["depth"][:], dtype=float),
                    "temperature": np.array(group["temperature"][:],
                                            dtype=float),
                    "variables": {
                        vname: {"data": np.array(var[...], dtype=float),
                                "dims": tuple(var.dimensions),
                                "units": getattr(var, "units", ""),
                                "long_name": getattr(var, "long_name",
                                                     vname)}
                        for vname, var in group.variables.items()
                        if vname not in ("time", "depth", "temperature")}}
                continue
            if kind != "channel":
                continue                    # configuration, preprocessing
            if "T_calibrated" not in group.variables:
                if verbose:
                    print(f"{channel}: no calibrated temperature in the "
                          f"file - skipped")
                continue
            out["TIME"][channel] = np.array(
                group["time"][:], dtype="int64").astype("datetime64[ms]")
            out["Z_CALIBRATED"][channel] = np.array(group["z_calibrated"][:],
                                                    dtype=float)
            out["T_USHAPED_CALIBRATED"][channel] = np.array(
                group["T_calibrated"][:], dtype=float)
            if "T_uncalibrated" in group.variables:
                out["Z_UNCALIBRATED"][channel] = np.array(
                    group["z_uncalibrated"][:], dtype=float)
                out["T_USHAPED_UNCALIBRATED"][channel] = np.array(
                    group["T_uncalibrated"][:], dtype=float)
            out["Z_SHIFT"][channel] = float(group.z_shift_m)
            out["T_SHIFT"][channel] = float(group.T_shift_K)
            out["Z_SHIFT_STD"][channel] = float(
                getattr(group, "z_shift_std_m", np.nan))
            out["T_SHIFT_STD"][channel] = float(
                getattr(group, "T_shift_std_K", np.nan))
    out["IS_TIME_CORRECTION"] = bool(attrs.get("IS_TIME_CORRECTION", 1))
    out["IS_LEXPLORE_DATA_AVAILABLE"] = bool(
        attrs.get("IS_LEXPLORE_DATA_AVAILABLE", 0))
    out["LEXPLORE_ROOT"] = attrs.get("LEXPLORE_ROOT", None)
    out["attrs"] = attrs
    if verbose:
        print(f"loaded from NetCDF: {path}")
        print(f"configuration {attrs.get('configuration', '?')}; time "
              f"correction: {out['IS_TIME_CORRECTION']}, LeXPLORE "
              f"calibration: {out['IS_LEXPLORE_DATA_AVAILABLE']}")
        for channel, time in out["TIME"].items():
            depths = out["Z_CALIBRATED"][channel]
            print(f"  {channel}: {time.size} profiles, {time[0]} -> "
                  f"{time[-1]} UTC; calibrated depths {depths[0]:.2f} - "
                  f"{depths[-1]:.2f} m (z shift "
                  f"{out['Z_SHIFT'][channel]:+.2f} m, T shift "
                  f"{out['T_SHIFT'][channel]:+.3f} K)")
    return out


def load_preprocessed_netcdf_multi(roots, filename="DTS_preprocessed.nc",
                                   period_tolerance=0.05, verbose=True):
    """Load and concatenate the preprocessed records of several folders.

    ``roots`` is one configuration folder or a list of them; every folder
    must hold ``filename`` (a missing file raises ``FileNotFoundError``
    naming all the folders that lack it).  All the records must share one
    sampling period (median time step, within ``period_tolerance``
    relative spread): mixing cadences would corrupt the time-domain
    analyses, so differing periods raise ``ValueError`` with every
    period listed, and nothing is loaded.  The records are concatenated
    along time, per channel NAME: a channel present in only some folders
    is concatenated from those folders alone (the summary says which).
    The depth grids may differ slightly between records (per-record
    calibration shifts): every later record is interpolated onto the grid
    of the first record that carries the channel (NaN outside).

    Returns the dict of :func:`load_preprocessed_netcdf`, with
    ``Z_SHIFT``/``T_SHIFT`` (and their stds) as nested dicts
    ``{channel: {folder name: value}}``, ``IS_TIME_CORRECTION`` =
    True only when every record was corrected,
    ``IS_LEXPLORE_DATA_AVAILABLE`` = True when ANY record was calibrated
    on the chain (the chain reader then reports its coverage), and
    ``LEXPLORE_ROOT`` from the first record that has it; ``folders``
    lists the folders used.

    ``filename`` is one file name for every folder, or a list with one
    name per folder (several files of one folder: repeat the folder).
    Records are named after their folder, with the file name added when it
    is not DTS_preprocessed.nc or when a folder gives several files."""
    roots = [roots] if isinstance(roots, str) else list(roots)
    names = ([filename] * len(roots) if isinstance(filename, str)
             else list(filename))
    if len(names) != len(roots):
        raise ValueError("one file name per folder is needed")
    missing = [os.path.join(root, name) for root, name in zip(roots, names)
               if not os.path.isfile(os.path.join(root, name))]
    if missing:
        raise FileNotFoundError(
            "missing preprocessed file(s): " + ", ".join(missing)
            + " - run the preprocessing on these folders first")
    labels, folder_of, keys = {}, {}, []
    for root, name in zip(roots, names):
        key = os.path.join(root, name)
        label = os.path.basename(os.path.normpath(root))
        if name != "DTS_preprocessed.nc" or roots.count(root) > 1:
            label += f" ({name})"
        labels[key], folder_of[key] = label, root
        keys.append(key)
    parts = [(key, load_preprocessed_netcdf(folder_of[key],
                                            os.path.basename(key),
                                            verbose=False))
             for key in keys]
    # chronological order of the records
    parts.sort(key=lambda item: min(t[0] for t in item[1]["TIME"].values()))

    # all the data sets must share one sampling period: mixing cadences
    # would corrupt the time-domain analyses
    sampling_periods = {}
    for root, part in parts:
        for channel, time in part["TIME"].items():
            period = float(np.median(np.diff(time)) / np.timedelta64(1, "s"))
            sampling_periods[(labels[root],
                              channel)] = period
    period_values = np.array(list(sampling_periods.values()))
    spread = (period_values.max() - period_values.min()) / period_values.min()
    if spread > period_tolerance:
        listing = "\n".join(f"  {folder} / {channel}: {period:.0f} s"
                            for (folder, channel), period
                            in sampling_periods.items())
        raise ValueError(
            "the data sets do not share one sampling period - loading "
            "skipped.\nSampling periods found:\n" + listing +
            "\nLoad records of equal cadence together, or analyse them "
            "separately.")

    out = dict(TIME={}, Z_CALIBRATED={}, T_USHAPED_CALIBRATED={},
               Z_UNCALIBRATED={}, T_USHAPED_UNCALIBRATED={},
               Z_SHIFT={}, T_SHIFT={}, Z_SHIFT_STD={}, T_SHIFT_STD={})
    channels = []
    for _, part in parts:
        for channel in part["TIME"]:
            if channel not in channels:
                channels.append(channel)
    sources = {}
    for channel in channels:
        with_channel = [(root, part) for root, part in parts
                        if channel in part["TIME"]]
        sources[channel] = [labels[root]
                            for root, _ in with_channel]
        for kind, z_key, T_key in (("calibrated", "Z_CALIBRATED",
                                    "T_USHAPED_CALIBRATED"),
                                   ("uncalibrated", "Z_UNCALIBRATED",
                                    "T_USHAPED_UNCALIBRATED")):
            if not all(channel in part[T_key] for _, part in with_channel):
                continue                    # not saved in every file
            z_reference = with_channel[0][1][z_key][channel]
            blocks = []
            for _, part in with_channel:
                z_part = part[z_key][channel]
                T_part = part[T_key][channel]
                if z_part.size == z_reference.size and \
                        np.allclose(z_part, z_reference):
                    blocks.append(T_part)
                else:
                    blocks.append(_interp_depth(z_reference, z_part, T_part))
            out[z_key][channel] = z_reference
            out[T_key][channel] = np.concatenate(blocks, axis=1)
        time = np.concatenate([part["TIME"][channel]
                               for _, part in with_channel])
        order = np.argsort(time, kind="stable")
        out["TIME"][channel] = time[order]
        out["T_USHAPED_CALIBRATED"][channel] = \
            out["T_USHAPED_CALIBRATED"][channel][:, order]
        if channel in out["T_USHAPED_UNCALIBRATED"]:
            out["T_USHAPED_UNCALIBRATED"][channel] = \
                out["T_USHAPED_UNCALIBRATED"][channel][:, order]
        for key in ("Z_SHIFT", "T_SHIFT", "Z_SHIFT_STD", "T_SHIFT_STD"):
            out[key][channel] = {
                labels[root]: part[key][channel]
                for root, part in with_channel}
    out["IS_TIME_CORRECTION"] = all(part["IS_TIME_CORRECTION"]
                                    for _, part in parts)
    out["IS_LEXPLORE_DATA_AVAILABLE"] = any(part["IS_LEXPLORE_DATA_AVAILABLE"]
                                            for _, part in parts)
    out["LEXPLORE_ROOT"] = next((part["LEXPLORE_ROOT"] for _, part in parts
                                 if part["LEXPLORE_ROOT"]), None)
    chains = [part["LEXPLORE"] for _, part in parts if part.get("LEXPLORE")]
    out["LEXPLORE"] = None
    if chains:
        depth = chains[0]["depth"]
        same = [c for c in chains if c["depth"].size == depth.size
                and np.allclose(c["depth"], depth)]
        time = np.concatenate([c["time"] for c in same])
        temperature = np.concatenate([c["temperature"] for c in same], axis=1)
        order = np.argsort(time, kind="stable")
        time, temperature = time[order], temperature[:, order]
        keep = np.concatenate(([True], np.diff(time) > np.timedelta64(0)))
        variables = {}
        first = same[0].get("variables") or {}
        for vname, item in first.items():
            dims = tuple(item["dims"])
            pieces = [(c.get("variables") or {}).get(vname) for c in same]
            if "time" not in dims:
                variables[vname] = item
            elif all(piece is not None for piece in pieces):
                axis = dims.index("time")
                data = np.concatenate([piece["data"] for piece in pieces],
                                      axis=axis)
                data = np.take(np.take(data, order, axis=axis),
                               np.nonzero(keep)[0], axis=axis)
                variables[vname] = dict(item, data=data)
        out["LEXPLORE"] = {"time": time[keep], "depth": depth,
                           "temperature": temperature[:, keep],
                           "variables": variables}
    out["folders"] = [folder_of[root] for root, _ in parts]
    out["attrs"] = {labels[root]: part["attrs"]
                    for root, part in parts}
    if verbose:
        print(f"loaded and concatenated {len(parts)} preprocessed record(s):")
        for root, part in parts:
            times = next(iter(part["TIME"].values()))
            print(f"  {labels[root]}: "
                  f"{', '.join(part['TIME'])}; {times[0]} -> {times[-1]} UTC")
        for channel in channels:
            time = out["TIME"][channel]
            print(f"  -> {channel}: {time.size} profiles, {time[0]} -> "
                  f"{time[-1]} UTC (from {', '.join(sources[channel])})")
    return out


def _interp_depth(zgrid, z, T):
    """T (1-D profile or matrix T(z, time)) linearly interpolated onto zgrid."""
    T = np.asarray(T)
    if T.ndim == 1:
        return np.interp(zgrid, z, T, left=np.nan, right=np.nan)
    out = np.empty((zgrid.size, T.shape[1]))
    for i in range(T.shape[1]):
        check_cancel()
        out[:, i] = np.interp(zgrid, z, T[:, i], left=np.nan, right=np.nan)
    return out


def resample_time_mean(time_src, T_src, time_target, window=None,
                       verbose=True):
    """Source matrix averaged onto the sampling periods of a target record.

    Every column of ``T_src(z, time_src)`` whose time falls within
    ± ``window``/2 of a target time is averaged (NaN-aware) into that
    target's column: the result ``T(z, time_target)`` has the sampling
    period of the target record (e.g. the DTS averaged onto the 10-min
    LeXPLORE chain sampling).  ``window`` is a numpy timedelta64 (default:
    the median step of ``time_target``).  A target time with no source
    profile in its window gets a NaN column.

    Returns the resampled matrix (nz, time_target.size)."""
    time_src = np.asarray(time_src, dtype="datetime64[ms]")
    time_target = np.asarray(time_target, dtype="datetime64[ms]")
    T_src = np.asarray(T_src, dtype=float)
    if window is None:
        if time_target.size < 2:
            raise ValueError("window must be given when time_target has "
                             "fewer than 2 times")
        window = np.median(np.diff(time_target))
    half = window / 2
    # cumulative sums over the sorted source columns: the mean of any
    # contiguous block of profiles comes from two lookups
    order = np.argsort(time_src, kind="stable")
    time_sorted, T_sorted = time_src[order], T_src[:, order]
    finite = np.isfinite(T_sorted)
    value_cumsum = np.zeros((T_sorted.shape[0], T_sorted.shape[1] + 1))
    count_cumsum = np.zeros_like(value_cumsum)
    np.cumsum(np.where(finite, T_sorted, 0.0), axis=1,
              out=value_cumsum[:, 1:])
    np.cumsum(finite, axis=1, out=count_cumsum[:, 1:])
    first = np.searchsorted(time_sorted, time_target - half, side="left")
    last = np.searchsorted(time_sorted, time_target + half, side="right")
    counts = count_cumsum[:, last] - count_cumsum[:, first]
    sums = value_cumsum[:, last] - value_cumsum[:, first]
    with np.errstate(invalid="ignore"):
        T_resampled = np.where(counts > 0, sums / np.maximum(counts, 1),
                               np.nan)
    if verbose:
        filled = (last > first)
        per_bin = (last - first)[filled]
        mean_per_bin = (f"{per_bin.mean():.1f}" if per_bin.size else "0")
        print(f"{time_target.size} target steps "
              f"(window {window / np.timedelta64(1, 's'):.0f} s): "
              f"{int(filled.sum())} filled with "
              f"{mean_per_bin} source profiles on average"
              + (f", {int((~filled).sum())} empty (NaN)"
                 if (~filled).any() else ""))
    return T_resampled


def vertical_offset_timeseries(time_ref, z_ref, T_ref, time_dts, z_dts, T_dts,
                               offset_scan=3.0, offset_step=0.02,
                               fit_temperature_shift=True, max_time_gap=None,
                               z_min=None, z_max=None, min_depths=10,
                               verbose=True):
    """Best vertical offset of the DTS against every reference profile.

    Every profile of the reference record (the LeXPLORE chain: ``time_ref``,
    ``z_ref``, ``T_ref(z, time)``) is compared with the DTS profile closest
    in time (``time_dts``, ``z_dts`` — a uniform grid — and
    ``T_dts(z, time)``): the DTS profile is shifted vertically by every
    offset of the scan (−``offset_scan`` .. +``offset_scan`` m in steps of
    ``offset_step``), evaluated at the reference depths, and the offset
    with the smallest rms difference is kept.

    Sign convention: a POSITIVE offset means the DTS sees the structures
    too shallow — the offset is the distance to ADD to the DTS depth axis
    for the best match with the reference.

    fit_temperature_shift : when True (default), a free constant
        temperature shift is allowed at every offset (the per-column mean
        difference is removed before the rms), so the known constant
        calibration offset of each channel does not bias the vertical fit;
        when False the raw difference is used.
    max_time_gap : maximum |time_ref − time_dts| for a pair to be used
        (numpy timedelta64; None = the median DTS time step).
    z_min, z_max : reference depths used in the fit (None = all).
    min_depths : minimum number of valid common depths, otherwise the
        profile gets NaN.

    Returns (time, offset, rms, temperature_shift): the reference times
    used (datetime64, UTC) and, per profile, the best offset (m), the rms
    at the best offset (K) and the constant temperature shift applied
    there (K; 0 when ``fit_temperature_shift`` is False).  NaN where fewer
    than ``min_depths`` depths overlap at every offset."""
    time_ref = np.asarray(time_ref, dtype="datetime64[ms]")
    time_dts = np.asarray(time_dts, dtype="datetime64[ms]")
    z_ref, z_dts = np.asarray(z_ref, float), np.asarray(z_dts, float)
    T_ref, T_dts = np.asarray(T_ref, float), np.asarray(T_dts, float)

    # pair every reference profile with the closest DTS profile in time
    position = np.searchsorted(time_dts, time_ref)
    position = np.clip(position, 1, time_dts.size - 1)
    take_right = (np.abs(time_dts[position] - time_ref)
                  <= np.abs(time_ref - time_dts[position - 1]))
    matched = np.where(take_right, position, position - 1)
    gap = np.abs(time_dts[matched] - time_ref)
    if max_time_gap is None:
        max_time_gap = np.median(np.diff(time_dts))
    paired = gap <= max_time_gap
    if not paired.any():
        raise ValueError("no reference profile within max_time_gap of a "
                         "DTS profile")
    time_used = time_ref[paired]
    T_ref_used = T_ref[:, paired]                       # (nk, n)
    T_dts_used = T_dts[:, matched[paired]]              # (nz, n)

    # reference depths taking part in the fit
    in_range = np.ones(z_ref.size, dtype=bool)
    if z_min is not None:
        in_range &= z_ref >= z_min
    if z_max is not None:
        in_range &= z_ref <= z_max
    depths = z_ref[in_range]
    T_ref_used = T_ref_used[in_range, :]
    if depths.size < 3:
        raise ValueError(
            f"only {depths.size} reference depth(s) between "
            f"{z_min if z_min is not None else z_ref.min():g} and "
            f"{z_max if z_max is not None else z_ref.max():g} m "
            f"({', '.join(f'{d:g}' for d in depths) or 'none'}); at least 3 "
            f"are needed - widen the depth range")
    # a narrow range holds few sensors: ask for all of them, at least 3
    min_depths = max(3, min(min_depths, depths.size))

    dz_grid = float(np.median(np.diff(z_dts)))
    offsets = np.arange(-offset_scan, offset_scan + offset_step / 2,
                        offset_step)
    n_profiles = time_used.size
    rms_all = np.full((offsets.size, n_profiles), np.nan)
    shift_all = np.zeros((offsets.size, n_profiles))
    for j, offset in enumerate(offsets):
        check_cancel()
        # shifted DTS evaluated at the reference depths: T_dts(z - offset)
        fraction = (depths - offset - z_dts[0]) / dz_grid
        index_low = np.floor(fraction).astype(int)
        weight = fraction - index_low
        inside = (index_low >= 0) & (index_low < z_dts.size - 1)
        index_low = np.clip(index_low, 0, z_dts.size - 2)
        shifted = ((1.0 - weight)[:, None] * T_dts_used[index_low, :]
                   + weight[:, None] * T_dts_used[index_low + 1, :])
        shifted[~inside, :] = np.nan
        difference = T_ref_used - shifted               # (nk, n)
        finite = np.isfinite(difference)
        count = finite.sum(axis=0)
        enough = count >= min_depths
        if not enough.any():
            continue
        if fit_temperature_shift:
            mean_diff = np.where(enough,
                                 np.nansum(np.where(finite, difference, 0.0),
                                           axis=0) / np.maximum(count, 1), 0.0)
            difference = difference - mean_diff
            shift_all[j, :] = mean_diff
        sum_sq = np.nansum(np.where(finite, difference ** 2, 0.0), axis=0)
        rms_all[j, enough] = np.sqrt(sum_sq[enough] / count[enough])

    usable = np.isfinite(rms_all).any(axis=0)
    best_index = np.zeros(n_profiles, dtype=int)
    best_index[usable] = np.nanargmin(rms_all[:, usable], axis=0)
    offset_best = np.where(usable, offsets[best_index], np.nan)
    rms_best = np.where(usable, rms_all[best_index, np.arange(n_profiles)],
                        np.nan)
    shift_best = np.where(usable,
                          shift_all[best_index, np.arange(n_profiles)],
                          np.nan)
    if not usable.any():
        raise ValueError(
            f"no profile could be fitted: fewer than {min_depths} of the "
            f"{depths.size} reference depths overlap the shifted DTS profile "
            f"at every offset - check the depth range and the offset scan")
    if verbose:
        mean_offset = float(np.nanmean(offset_best))
        std_offset = float(np.nanstd(offset_best))
        print(f"vertical offset over {int(usable.sum())} paired profiles "
              f"({time_used[0]} -> {time_used[-1]} UTC, DTS within "
              f"{max_time_gap / np.timedelta64(1, 'm'):.1f} min): "
              f"mean {mean_offset:+.3f} m, std {std_offset:.3f} m "
              f"(positive = add to the DTS depth axis); median rms "
              f"{float(np.nanmedian(rms_best)):.3f} K"
              + (f", median temperature shift "
                 f"{float(np.nanmedian(shift_best)):+.3f} K"
                 if fit_temperature_shift else ""))
    return time_used, offset_best, rms_best, shift_best


def _prefix_line_fits(x, y):
    """Least-squares line fitted to the first k points, for every k:
    returns (slope, intercept, rms), each an array over k = 1..n
    (entries for k < 3 are NaN).  Vectorised with cumulative sums."""
    k = np.arange(1, x.size + 1, dtype=float)
    Sx, Sy = np.cumsum(x), np.cumsum(y)
    Sxx, Sxy, Syy = np.cumsum(x * x), np.cumsum(x * y), np.cumsum(y * y)
    denom = k * Sxx - Sx ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = (k * Sxy - Sx * Sy) / denom
        intercept = (Sy - slope * Sx) / k
        sse = Syy - intercept * Sy - slope * Sxy
        rms = np.sqrt(np.maximum(sse, 0.0) / k)
    slope[:2] = intercept[:2] = rms[:2] = np.nan
    return slope, intercept, rms


def fit_three_layers(z, T, rms_tol=0.05, min_points=5, min_gap=2.0):
    """Three-layer description of a temperature profile.

    The well-mixed top and the weakly stratified bottom are fitted first
    and alone: Z1 is the deepest depth such that the straight-line fit of
    the profile above it keeps an rms of at most ``rms_tol`` (slope s1),
    and Z2 is likewise the shallowest depth such that the fit below it
    stays within ``rms_tol`` (slope s3).  The strongly stratified middle
    layer, whose structure is complex, takes no part in these fits: its
    slope s2 is simply that of the segment joining the two fitted lines at
    Z1 and Z2, so the model stays continuous.  Each outer layer keeps at
    least ``min_points`` samples and the interfaces at least ``min_gap`` m
    apart.

    Returns a dict: 'Z1', 'Z2' (m), 'slopes' = (s1, s2, s3) (K/m),
    'T_fit' (the model on the full z axis) and 'rms' (K, over the top and
    bottom layers only — the layers that were fitted)."""
    z = np.asarray(z, float)
    T = np.asarray(T, float)
    finite = np.isfinite(T)
    z_fit, T_fit_data = z[finite], T[finite]
    n = z_fit.size
    counts = np.arange(1, n + 1)

    slope_top, intercept_top, rms_top = _prefix_line_fits(z_fit, T_fit_data)
    slope_bot, intercept_bot, rms_bot = _prefix_line_fits(z_fit[::-1],
                                                          T_fit_data[::-1])
    ok_top = (counts >= min_points) & (rms_top <= rms_tol)
    ok_bot = (counts >= min_points) & (rms_bot <= rms_tol)
    k_top = int(np.nonzero(ok_top)[0][-1]) if ok_top.any() else min_points - 1
    k_bot = int(np.nonzero(ok_bot)[0][-1]) if ok_bot.any() else min_points - 1
    # keep the interfaces apart (shrink the worse-fitting layer first)
    while z_fit[n - 1 - k_bot] - z_fit[k_top] < min_gap:
        if k_top <= min_points - 1 and k_bot <= min_points - 1:
            break
        if k_bot <= min_points - 1 or (k_top > min_points - 1 and
                                       rms_top[k_top] >= rms_bot[k_bot]):
            k_top -= 1
        else:
            k_bot -= 1

    Z1 = float(z_fit[k_top])
    Z2 = float(z_fit[n - 1 - k_bot])
    s1, a1 = float(slope_top[k_top]), float(intercept_top[k_top])
    s3, a3 = float(slope_bot[k_bot]), float(intercept_bot[k_bot])
    T_at_Z1 = a1 + s1 * Z1
    T_at_Z2 = a3 + s3 * Z2
    s2 = (T_at_Z2 - T_at_Z1) / (Z2 - Z1)
    T_model = np.where(z <= Z1, a1 + s1 * z,
                       np.where(z >= Z2, a3 + s3 * z,
                                T_at_Z1 + s2 * (z - Z1)))
    outer = (z_fit <= Z1) | (z_fit >= Z2)
    residual = T_fit_data[outer] - np.where(
        z_fit[outer] <= Z1, a1 + s1 * z_fit[outer], a3 + s3 * z_fit[outer])
    return dict(Z1=Z1, Z2=Z2, slopes=(s1, s2, s3), T_fit=T_model,
                rms=float(np.sqrt(np.mean(residual ** 2))))


def fit_three_layers_batch(z, T_matrix, rms_tol=0.05, min_points=5,
                           min_gap=2.0, verbose=True):
    """Three-layer description (:func:`fit_three_layers`) of every profile
    of ``T_matrix(z, time)``.

    Returns a dict of arrays over time: 'Z1', 'Z2' (m), 'slopes' (3, nt)
    (K/m, top / middle / bottom layer) and 'rms' (K, over the fitted outer
    layers)."""
    T_matrix = np.asarray(T_matrix, float)
    nt = T_matrix.shape[1]
    Z1 = np.full(nt, np.nan)
    Z2 = np.full(nt, np.nan)
    slopes = np.full((3, nt), np.nan)
    rms = np.full(nt, np.nan)
    for profile_index in range(nt):
        check_cancel()
        result = fit_three_layers(z, T_matrix[:, profile_index],
                                  rms_tol=rms_tol, min_points=min_points,
                                  min_gap=min_gap)
        Z1[profile_index], Z2[profile_index] = result["Z1"], result["Z2"]
        slopes[:, profile_index] = result["slopes"]
        rms[profile_index] = result["rms"]
    if verbose:
        print(f"three-layer fit: {nt} profiles, Z1 = {np.nanmean(Z1):.1f} "
              f"± {np.nanstd(Z1):.1f} m, Z2 = {np.nanmean(Z2):.1f} "
              f"± {np.nanstd(Z2):.1f} m, outer rms {np.nanmean(rms):.3f} K")
    return dict(Z1=Z1, Z2=Z2, slopes=slopes, rms=rms)


def find_staircase(z, T, z_top, z_bottom, grad_factor=0.5,
                   min_thickness=0.5, smooth_length=0.5, max_gradient=None):
    """Staircase detection in one temperature profile, restricted to the
    depth range [``z_top``, ``z_bottom``] (the stratified layer S2 of
    :func:`fit_three_layers`).

    The profile is smoothed with a running mean of length ``smooth_length``
    (m), the vertical gradient is computed, and the samples where the
    gradient magnitude is below ``grad_factor`` times the mean gradient of
    the layer are classified as steps (well-mixed treads); with
    ``max_gradient`` (K/m) given, the threshold is that fixed value
    instead.  Contiguous runs
    thinner than ``min_thickness`` (m) are discarded; the gaps between
    consecutive steps are the interfaces (risers).

    Returns a dict:
      'z', 'T', 'T_smooth'            samples of the layer (m, degC)
      'gradient'                      smoothed gradient dT/dz (K/m)
      'threshold'                     gradient threshold used (K/m, > 0)
      'step_top', 'step_bottom'       one entry per detected step (m)
      'step_T'                        mean temperature of each step (degC)
      'interface_z', 'interface_dT'   centre (m) and temperature jump (K,
                                      upper minus lower step) of each
                                      interface between consecutive steps
    or None when the layer holds fewer than 8 samples."""
    z = np.asarray(z, float)
    T = np.asarray(T, float)
    inside = (z >= z_top) & (z <= z_bottom) & np.isfinite(T)
    z_layer, T_layer = z[inside], T[inside]
    if z_layer.size < 8:
        return None
    dz = float(np.median(np.diff(z_layer)))
    n_smooth = max(int(round(smooth_length / dz)) | 1, 1)   # odd
    if n_smooth > 1:
        pad = n_smooth // 2
        T_padded = np.pad(T_layer, pad, mode="edge")
        T_smooth = np.convolve(T_padded, np.ones(n_smooth) / n_smooth,
                               mode="valid")
    else:
        T_smooth = T_layer.copy()
    gradient = np.gradient(T_smooth, z_layer)
    mean_gradient = (T_smooth[-1] - T_smooth[0]) / (z_layer[-1] - z_layer[0])
    threshold = (abs(float(max_gradient)) if max_gradient is not None
                 else grad_factor * abs(mean_gradient))
    is_step = np.abs(gradient) < threshold
    min_points = max(int(round(min_thickness / dz)), 2)
    step_top, step_bottom, step_T = [], [], []
    run_start = None
    for index in range(is_step.size + 1):
        if index < is_step.size and is_step[index]:
            if run_start is None:
                run_start = index
        elif run_start is not None:
            if index - run_start >= min_points:
                step_top.append(float(z_layer[run_start]))
                step_bottom.append(float(z_layer[index - 1]))
                step_T.append(float(np.mean(T_layer[run_start:index])))
            run_start = None
    interface_z = [0.5 * (step_bottom[k] + step_top[k + 1])
                   for k in range(len(step_T) - 1)]
    interface_dT = [step_T[k] - step_T[k + 1]
                    for k in range(len(step_T) - 1)]
    return dict(z=z_layer, T=T_layer, T_smooth=T_smooth, gradient=gradient,
                threshold=float(threshold),
                step_top=np.array(step_top), step_bottom=np.array(step_bottom),
                step_T=np.array(step_T), interface_z=np.array(interface_z),
                interface_dT=np.array(interface_dT))


def isotherm_depth(z, T_matrix, T_iso):
    """Depth of the shallowest crossing of T_iso in each profile (linear
    interpolation between samples; NaN when the profile never crosses).

    Also returns the uncertainty of each interpolated depth: the average
    distance to the two closest measured points of the profile, i.e. half
    the local spacing of the depth grid."""
    crossing_depth = np.full(T_matrix.shape[1], np.nan)
    uncertainty = np.full(T_matrix.shape[1], np.nan)
    for profile_index in range(T_matrix.shape[1]):
        finite_samples = np.isfinite(T_matrix[:, profile_index])
        z_finite = z[finite_samples]
        T_finite = T_matrix[finite_samples, profile_index]
        below_iso = np.nonzero(T_finite < T_iso)[0]
        if below_iso.size and below_iso[0] > 0:
            first_below = below_iso[0]
            crossing_depth[profile_index] = \
                z_finite[first_below - 1] + \
                (z_finite[first_below] - z_finite[first_below - 1]) * \
                (T_finite[first_below - 1] - T_iso) / \
                (T_finite[first_below - 1] - T_finite[first_below])
            uncertainty[profile_index] = 0.5 * \
                (z_finite[first_below] - z_finite[first_below - 1])
    return crossing_depth, uncertainty


# ---- spectral analysis: detrending, window, amplitude or power ------------
DETRENDS = ("constant", "linear")
WINDOWS = ("none", "Hann", "Hamming", "Blackman", "Tukey (25 %)")
SPECTRUM_KINDS = ("FFT amplitude", "Power spectral density")


def detrend_along(x, axis=0, kind="constant"):
    """Remove from every series along ``axis`` its mean ('constant') or
    its least-squares line ('linear'), NaN-aware (the fit uses the finite
    samples); NaN are then set to 0."""
    x = np.moveaxis(np.asarray(x, dtype=float), axis, 0)
    finite = np.isfinite(x)
    n = np.maximum(finite.sum(axis=0), 1)
    y = np.where(finite, x, 0.0)
    mean = y.sum(axis=0) / n
    out = np.where(finite, x - mean, 0.0)
    if kind == "linear":
        index = np.arange(x.shape[0], dtype=float).reshape(
            (-1,) + (1,) * (x.ndim - 1))
        t = np.where(finite, index, 0.0)
        t_mean = t.sum(axis=0) / n
        dt = np.where(finite, index - t_mean, 0.0)
        denominator = (dt ** 2).sum(axis=0)
        slope = np.where(denominator > 0, (dt * out).sum(axis=0)
                         / np.where(denominator > 0, denominator, 1.0), 0.0)
        out = np.where(finite, out - slope * dt, 0.0)
    elif kind != "constant":
        raise ValueError(f"detrend must be one of {DETRENDS}, not {kind!r}")
    return np.moveaxis(out, 0, axis)


def window_weights(n, kind="none"):
    """Taper of ``n`` samples: none (rectangular), Hann, Hamming, Blackman
    or Tukey (25 % cosine tapers)."""
    from scipy.signal import get_window
    name = (kind or "none").lower()
    if name == "none":
        return np.ones(n)
    if name.startswith("tukey"):
        return get_window(("tukey", 0.25), n, fftbins=False)
    if name in ("hann", "hamming", "blackman"):
        return get_window(name, n, fftbins=False)
    raise ValueError(f"window must be one of {WINDOWS}, not {kind!r}")


def spectrum_along(x, step, axis=0, detrend="constant", window="none",
                   kind="FFT amplitude"):
    """One-sided spectrum of every series of ``x`` along ``axis`` (sample
    spacing ``step``: seconds, metres, ...), after detrending and tapering.

    'FFT amplitude': 2|X| / Σw, the amplitude of a sinusoid in the units of
    x (the window's coherent gain is corrected).  'Power spectral density':
    2|X|² / (fs Σw²), in units of x² per cycle per unit of ``step``
    (Σ PSD Δf = variance of the tapered series).  Returns (frequencies
    (cycles per unit of step, zero dropped), spectrum with the frequency
    along ``axis``)."""
    prepared = detrend_along(x, axis, detrend)
    n = prepared.shape[axis]
    w = window_weights(n, window)
    shape = [1] * prepared.ndim
    shape[axis] = n
    X = np.fft.rfft(prepared * w.reshape(shape), axis=axis)
    frequency = np.fft.rfftfreq(n, d=step)
    if kind == "FFT amplitude":
        values = 2.0 * np.abs(X) / w.sum()
    elif kind == "Power spectral density":
        values = 2.0 * np.abs(X) ** 2 / ((1.0 / step) * (w ** 2).sum())
    else:
        raise ValueError(f"kind must be one of {SPECTRUM_KINDS}, not "
                         f"{kind!r}")
    values = np.take(values, np.arange(1, frequency.size), axis=axis)
    return frequency[1:], values


def fft_vertical(z, T_matrix, detrend="constant", window="none",
                 kind="FFT amplitude"):
    """FFT of each profile along depth: wavenumber spectra of a record.

    ``z``: depths of the rows of ``T_matrix`` (m, uniform grid);
    ``T_matrix``: temperature (nz, nt). Each profile (column) has its mean
    removed (NaN-aware, NaN then filled with 0) before the real FFT along
    depth. Returns ``(wavenumber, amplitude)``: wavenumbers in cycles per
    metre and the amplitude 2|X|/n per profile, the zero wavenumber
    dropped (``amplitude[k, t]``)."""
    dz_grid = float(np.median(np.diff(z)))
    return spectrum_along(np.asarray(T_matrix, dtype=float), dz_grid, 0,
                          detrend, window, kind)


def fft2_matrix(time, z, T_matrix, verbose=True, label="",
                signed_frequency=False, detrend="linear", window="none",
                kind="FFT amplitude"):
    """2D FFT (depth x time) of one temperature matrix T(z, time).

    ``time`` must have a uniform step and ``z`` a uniform spacing; depth
    rows holding any NaN are dropped.  Every remaining row is demeaned and
    linearly detrended over time, then the matrix is transformed in both
    directions: one-sided in frequency (Hz, zero dropped) and two-sided,
    centred, in vertical wavenumber (cycles/m; the two signs of ``k_z``
    separate the two directions of vertical phase propagation, z positive
    downwards).  Amplitude 2|F| / (nz nt) in K.

    With ``signed_frequency=True`` the frequency axis is kept two-sided and
    centred as well (zero column included, same amplitude factor).  The
    temperature is real, so the full 2D spectrum is point-symmetric,
    amplitude(-f, -k_z) = amplitude(f, k_z): the information sits in the
    asymmetry between the quadrants (f > 0, k_z > 0) and (f > 0, k_z < 0).

    Returns ``(frequency, k_z, amplitude(k_z, frequency))``, or None when
    fewer than 4 complete depth rows remain."""
    time = np.asarray(time)
    T_matrix = np.asarray(T_matrix, float)
    z = np.asarray(z, float)
    dt_seconds = float(np.median(np.diff(time)) / np.timedelta64(1, "s"))
    dz = float(np.median(np.diff(z)))
    nt = time.size
    rows_ok = np.all(np.isfinite(T_matrix), axis=1)
    T_clean = T_matrix[rows_ok]
    nz = T_clean.shape[0]
    if nz < 4:
        if verbose:
            print(f"{label}: only {nz} complete depth row(s), skipped")
        return None
    # detrend over time at each depth (removes the mean profile), then
    # along depth at each time; taper in both directions
    T_clean = detrend_along(detrend_along(T_clean, 1, detrend), 0, detrend)
    w_z, w_t = window_weights(nz, window), window_weights(nt, window)
    T_clean = T_clean * np.outer(w_z, w_t)
    if kind == "FFT amplitude":
        scale = 2.0 / (w_z.sum() * w_t.sum())
    elif kind == "Power spectral density":
        scale = 2.0 * dt_seconds * dz / ((w_z ** 2).sum() * (w_t ** 2).sum())
    else:
        raise ValueError(f"kind must be one of {SPECTRUM_KINDS}")

    def finish(F):
        return scale * (np.abs(F) if kind == "FFT amplitude"
                        else np.abs(F) ** 2)
    k_z = np.fft.fftshift(np.fft.fftfreq(nz, d=dz))
    if signed_frequency:
        spectrum = np.fft.fft2(T_clean)        # two-sided in f and k_z
        amplitude = finish(np.fft.fftshift(spectrum, axes=(0, 1)))
        frequency = np.fft.fftshift(np.fft.fftfreq(nt, d=dt_seconds))
        if verbose:
            print(f"{label}: {nz} depths x {nt} times, "
                  f"|k_z| <= {np.abs(k_z).max():.3f} 1/m, "
                  f"|f| <= {np.abs(frequency).max() * 1e3:.3f} mHz (signed)")
        return frequency, k_z, amplitude
    spectrum = np.fft.rfft(T_clean, axis=1)    # time  -> frequency (one-sided)
    spectrum = np.fft.fft(spectrum, axis=0)    # depth -> k_z (two-sided)
    amplitude = finish(np.fft.fftshift(spectrum, axes=0))
    frequency = np.fft.rfftfreq(nt, d=dt_seconds)
    if verbose:
        print(f"{label}: {nz} depths x {nt} times, "
              f"|k_z| <= {np.abs(k_z).max():.3f} 1/m, "
              f"f <= {frequency[-1] * 1e3:.3f} mHz")
    return frequency[1:], k_z, amplitude[:, 1:]



# ===========================================================================
# PHYSICAL PARAMETERS
#
# Every physical constant used by a computation is listed in
# PHYSICAL_PARAMETERS and read from PHYSICS at run time (never written as a
# number inside a step).  A new constant needed by a future step is added to
# this list: it then appears in Advanced > Physical parameters, is saved
# with the analysis settings and is written in the log of the steps.
# ===========================================================================
PHYSICAL_PARAMETERS = [
    # (name, label, unit, default, group, kind, extra)
    ("GRAVITY", "Gravity g", "m s⁻²", 9.81, "Constants", "float",
     dict(help="Acceleration of gravity: Brunt–Väisälä frequency, reduced "
               "gravity of the Poincaré estimate, pressure from depth.")),
    ("EARTH_ROTATION", "Earth rotation rate Ω", "rad s⁻¹", 7.2921e-5,
     "Constants", "float", dict(help="Coriolis parameter f = 2Ω sin φ.")),
    ("LATITUDE_DEG", "Latitude φ", "°N", 46.5, "Lake", "float",
     dict(help="Latitude of the measurements (LéXPLORE, 46.5° N): "
               "Coriolis frequency f of the frequency-domain steps.")),
    ("LAKE_WIDTH_KM", "Lake width", "km", 13.0, "Lake", "float",
     dict(help="Cross-lake width of the first Poincaré mode, "
               "k = π / width.")),
    ("LEXPLORE_LAT", "LéXPLORE latitude", "°N", 46.500228, "Lake",
     "float", dict(help="Position of the LéXPLORE platform (46°30'0.819\" N, "
                        "published position), drawn on the STC position "
                        "map.")),
    ("LEXPLORE_LON", "LéXPLORE longitude", "°E", 6.660835, "Lake", "float",
     dict(help="Position of the LéXPLORE platform (6°39'39.007\" E).")),
    ("LEXPLORE_RADIUS_M", "LéXPLORE radius", "m", 100.0, "Lake", "float",
     dict(help="An STC profile taken within this distance of LéXPLORE "
               "counts as taken at LéXPLORE (option 'Only STC profiles at "
               "LéXPLORE' of the sound-speed panel).")),
    ("SALINITY", "Salinity S", "PSU", 0.0, "Water", "float",
     dict(help="Salinity used by the equation of state and the sound "
               "speed (0 = fresh water; to be refined later).")),
    ("EOS_MODE", "Density and expansion", "", "Equation of state", "Water",
     "choice", dict(choices=["Equation of state", "Fixed values"],
                    help="Equation of state: ρ(T, S) and α(T, S) = "
                         "−(1/ρ) dρ/dT from the equation chosen below. "
                         "Fixed values: ρ and α constant (the two fixed "
                         "values below).")),
    ("EOS", "Equation of state", "", "Parabolic (fresh water)", "Water",
     "choice", dict(choices=["Parabolic (fresh water)",
                             "UNESCO EOS-80 (one atmosphere)"],
                    mode="Equation of state",
                    help="Parabolic: ρ = ρ₀ [1 − b (T − T_md)²], "
                         "α = 2b (T − T_md) (the convention of the "
                         "notebooks). UNESCO EOS-80: international "
                         "equation of state of sea water at one atmosphere "
                         "(Millero & Poisson 1981), valid for fresh water "
                         "with S = 0.")),
    ("RHO_0", "Reference density ρ₀", "kg m⁻³", 999.97, "Water", "float",
     dict(mode="Equation of state",
          help="Density at the temperature of maximum density "
               "(parabolic law); also the Boussinesq reference density.")),
    ("T_MAX_DENSITY", "Temperature of maximum density T_md", "°C", 3.98,
     "Water", "float", dict(mode="Equation of state",
                            help="Parabolic law (fresh water: 3.98 °C).")),
    ("PARABOLIC_B", "Parabolic coefficient b", "K⁻²", 6.8e-6, "Water",
     "float", dict(mode="Equation of state",
                   help="Parabolic law: ρ = ρ₀ [1 − b (T − T_md)²].")),
    ("RHO_FIXED", "Fixed density ρ", "kg m⁻³", 999.7, "Water", "float",
     dict(mode="Fixed values", help="Density when 'Fixed values' is "
                                    "chosen.")),
    ("ALPHA_FIXED", "Fixed thermal expansion α", "K⁻¹", 1.0e-4, "Water",
     "float", dict(mode="Fixed values",
                   help="Thermal expansion coefficient when 'Fixed "
                        "values' is chosen.")),
    ("SOUND_FORMULA", "Sound-speed formula", "", "UNESCO (Chen & Millero "
     "1977)", "Sound speed", "choice",
     dict(choices=["UNESCO (Chen & Millero 1977)", "Medwin (1975)",
                   "Mackenzie (1981)"],
          help="UNESCO: the international standard (Fofonoff & Millard "
               "1983), valid 0–40 °C, 0–40 PSU, 0–1000 bar: suited to "
               "fresh water. Medwin and Mackenzie: simpler sea-water "
               "formulas (their salinity range starts above 0; less "
               "accurate in a lake).")),
    ("SOUND_T_REFERENCE", "Temperature when T is off", "°C", 10.0,
     "Sound speed", "float",
     dict(help="Constant temperature used by the sound speed when the box "
               "'Temperature' is unticked.")),
]

PHYSICS_DEFAULTS = {name: default for name, _, _, default, *_ in
                    PHYSICAL_PARAMETERS}
PHYSICS = dict(PHYSICS_DEFAULTS)


def physics(name):
    """Current value of one physical parameter."""
    return PHYSICS.get(name, PHYSICS_DEFAULTS[name])


def set_physics(values):
    """Change physical parameters (unknown names are ignored); returns the
    names that changed."""
    changed = []
    for name, value in (values or {}).items():
        if name in PHYSICS_DEFAULTS and PHYSICS.get(name) != value:
            PHYSICS[name] = value
            changed.append(name)
    return changed


def eos_summary():
    if physics("EOS_MODE") == "Fixed values":
        return (f"fixed ρ = {physics('RHO_FIXED'):g} kg m⁻³, "
                f"α = {physics('ALPHA_FIXED'):g} K⁻¹")
    return f"{physics('EOS')}, S = {physics('SALINITY'):g} PSU"


def _rho_eos80(T, S):
    """UNESCO EOS-80 density at one atmosphere (kg m⁻³), T in °C, S PSU."""
    T = np.asarray(T, float)
    rho_w = (999.842594 + 6.793952e-2 * T - 9.095290e-3 * T ** 2
             + 1.001685e-4 * T ** 3 - 1.120083e-6 * T ** 4
             + 6.536332e-9 * T ** 5)
    return (rho_w
            + S * (0.824493 - 4.0899e-3 * T + 7.6438e-5 * T ** 2
                   - 8.2467e-7 * T ** 3 + 5.3875e-9 * T ** 4)
            + S ** 1.5 * (-5.72466e-3 + 1.0227e-4 * T - 1.6546e-6 * T ** 2)
            + 4.8314e-4 * S ** 2)


def density(T, S=None):
    """Density ρ(T, S) (kg m⁻³) from the physical parameters."""
    T = np.asarray(T, float)
    S = physics("SALINITY") if S is None else S
    if physics("EOS_MODE") == "Fixed values":
        return np.where(np.isfinite(T), physics("RHO_FIXED"), np.nan)
    if physics("EOS").startswith("UNESCO"):
        return _rho_eos80(T, S)
    return physics("RHO_0") * (1.0 - physics("PARABOLIC_B")
                               * (T - physics("T_MAX_DENSITY")) ** 2)


def thermal_expansion(T, S=None):
    """Thermal expansion coefficient α = −(1/ρ) dρ/dT (K⁻¹)."""
    T = np.asarray(T, float)
    S = physics("SALINITY") if S is None else S
    if physics("EOS_MODE") == "Fixed values":
        return np.where(np.isfinite(T), physics("ALPHA_FIXED"), np.nan)
    if physics("EOS").startswith("UNESCO"):
        step = 0.01
        return -((_rho_eos80(T + step, S) - _rho_eos80(T - step, S))
                 / (2 * step) / _rho_eos80(T, S))
    # parabolic law, Boussinesq form (the notebooks' 1.36e-5 (T - 3.98))
    return 2.0 * physics("PARABOLIC_B") * (T - physics("T_MAX_DENSITY"))


def reference_density():
    return (physics("RHO_FIXED") if physics("EOS_MODE") == "Fixed values"
            else physics("RHO_0"))


def reduced_gravity(T_upper, T_lower):
    """g' = g (ρ_lower − ρ_upper) / ρ₀ between two layer temperatures."""
    if physics("EOS_MODE") == "Fixed values":
        return physics("GRAVITY") * physics("ALPHA_FIXED") * (T_upper
                                                              - T_lower)
    return physics("GRAVITY") * (density(T_lower) - density(T_upper)) \
        / reference_density()


def coriolis_frequency_Hz(latitude_deg=None):
    """f / 2π (Hz), f = 2Ω sin φ."""
    latitude = physics("LATITUDE_DEG") if latitude_deg is None \
        else latitude_deg
    return (2.0 * physics("EARTH_ROTATION") * np.sin(np.deg2rad(latitude))
            / (2 * np.pi))


# ---------------------------------------------------------------------------
# vertical gradient, smoothing, Brunt-Vaisala frequency
# ---------------------------------------------------------------------------
def nan_mean_rows(matrix):
    """NaN-aware mean over time of each row (empty rows -> NaN)."""
    matrix = np.asarray(matrix, float)
    n_finite = np.isfinite(matrix).sum(axis=1)
    total = np.nansum(np.nan_to_num(matrix, nan=0.0), axis=1)
    return np.where(n_finite > 0, total / np.maximum(n_finite, 1), np.nan)


def time_mean_std(matrix):
    """NaN-aware mean and standard deviation over time of each row."""
    matrix = np.asarray(matrix, float)
    mean = nan_mean_rows(matrix)
    n_finite = np.isfinite(matrix).sum(axis=1)
    square = np.nansum(np.nan_to_num((matrix - mean[:, None]) ** 2, nan=0.0),
                       axis=1)
    std = np.where(n_finite > 0, np.sqrt(square / np.maximum(n_finite, 1)),
                   np.nan)
    return mean, std


def smooth_matrix(z, matrix, width, step=None):
    """NaN-aware window average over depth of every column of
    matrix(z, time), at centres every step (None = the window width:
    windows side by side).  Returns (centres, smoothed matrix)."""
    z = np.asarray(z, float)
    matrix = np.asarray(matrix, float)
    if not step:
        step = float(width)
    centres = np.arange(float(z[0]), float(z[-1]) + 0.5 * step, step)
    smoothed = np.full((centres.size, matrix.shape[1]), np.nan)
    for index, centre in enumerate(centres):
        rows = np.abs(z - centre) <= 0.5 * width
        if rows.any():
            block = matrix[rows]
            count = np.isfinite(block).sum(axis=0)
            total = np.nansum(block, axis=0)
            smoothed[index] = np.where(count > 0,
                                       total / np.maximum(count, 1), np.nan)
    return centres, smoothed


def smooth_profile(z, profile, width, step=None):
    """NaN-aware window average of profile(z) at centres every step (None =
    the window width)."""
    z = np.asarray(z, float)
    profile = np.asarray(profile, float)
    if not step:
        step = float(width)
    centres = np.arange(float(z[0]), float(z[-1]) + 0.5 * step, step)
    smoothed = np.full(centres.size, np.nan)
    for index, centre in enumerate(centres):
        window = (np.abs(z - centre) <= 0.5 * width) & np.isfinite(profile)
        if window.any():
            smoothed[index] = profile[window].mean()
    return centres, smoothed


def vertical_gradient(z, T, smooth_width=None, smooth_step=None):
    """dT/dz (K m⁻¹) of every profile of T(z, time) (or of one profile).
    With smooth_width: T is first window-averaged over depth (centres every
    smooth_step, default = the width) and the gradient is taken on the
    window centres.  Returns (depth grid, gradient)."""
    z = np.asarray(z, float)
    T = np.asarray(T, float)
    one = T.ndim == 1
    if one:
        T = T[:, None]
    if smooth_width:
        z, T = smooth_matrix(z, T, smooth_width, smooth_step)
    gradient = np.gradient(T, z, axis=0) if z.size > 1 else \
        np.full_like(T, np.nan)
    return z, (gradient[:, 0] if one else gradient)


def brunt_vaisala(z, T, smooth_width=None, smooth_step=None):
    """Brunt-Vaisala frequency of every profile of T(z, time).

    N² = −g α(T) dT/dz (positive z downwards, so a stable column has
    dT/dz < 0 and N² > 0); N = √max(N², 0) / 2π in Hz.  With smooth_width,
    T is window-averaged over depth before the gradient, so the noise is
    reduced before the square root.  Returns (depth grid, N (Hz), N² (s⁻²),
    the signed N² keeping the unstable regions N² < 0)."""
    depth, gradient = vertical_gradient(z, T, smooth_width, smooth_step)
    T = np.asarray(T, float)
    if smooth_width:
        _, T = smooth_matrix(np.asarray(z, float),
                             T if T.ndim == 2 else T[:, None],
                             smooth_width, smooth_step)
        if gradient.ndim == 1:
            T = T[:, 0]
    N_squared = -physics("GRAVITY") * thermal_expansion(T) * gradient
    N = np.sqrt(np.maximum(N_squared, 0.0)) / (2.0 * np.pi)
    N[~np.isfinite(N_squared)] = np.nan
    return depth, N, N_squared


# ---------------------------------------------------------------------------
# sound speed
# ---------------------------------------------------------------------------
def pressure_dbar(z, rho_mean=None):
    """Gauge pressure (dbar) at depth z (m): P = ρ̄ g z (the atmospheric
    pressure is left out, as in the sound-speed formulas)."""
    rho = reference_density() if rho_mean is None else rho_mean
    return rho * physics("GRAVITY") * np.asarray(z, float) / 1.0e4


def _sound_unesco(T, P_dbar, S):
    """UNESCO 1983 (Chen & Millero 1977), T in °C (ITS-90, converted to
    IPTS-68), P in dbar (converted to bar), S in PSU."""
    T = 1.00024 * np.asarray(T, float)
    P = np.asarray(P_dbar, float) / 10.0
    S = np.asarray(S, float)
    Cw = ((((3.1464e-9 * T - 1.47800e-6) * T + 3.3420e-4) * T
           - 5.80852e-2) * T + 5.03711) * T + 1402.388
    Cw = Cw + ((((-6.1185e-10 * T + 1.3621e-7) * T - 8.1788e-6) * T
                + 6.8982e-4) * T + 0.153563) * P
    Cw = Cw + ((((1.0405e-12 * T - 2.5335e-10) * T + 2.5974e-8) * T
                - 1.7107e-6) * T + 3.1260e-5) * P ** 2
    Cw = Cw + ((-2.3643e-12 * T + 3.8504e-10) * T - 9.7729e-9) * P ** 3
    A = ((((-3.21e-8 * T + 2.006e-6) * T + 7.164e-5) * T - 1.262e-2) * T
         + 1.389)
    A = A + ((((-2.0122e-10 * T + 1.0507e-8) * T - 6.4885e-8) * T
              - 1.2580e-5) * T + 9.4742e-5) * P
    A = A + (((7.988e-12 * T - 1.6002e-10) * T + 9.1041e-9) * T
             - 3.9064e-7) * P ** 2
    A = A + ((-3.389e-13 * T + 6.649e-12) * T + 1.100e-10) * P ** 3
    B = -1.922e-2 - 4.42e-5 * T + (7.3637e-5 + 1.7945e-7 * T) * P
    D = 1.727e-3 - 7.9836e-6 * P
    return Cw + A * S + B * S ** 1.5 + D * S ** 2


def sound_speed(T, P_dbar, S, formula=None):
    """Speed of sound c(T, P, S) (m s⁻¹) with the formula of the physical
    parameters (or the one given)."""
    formula = formula or physics("SOUND_FORMULA")
    T = np.asarray(T, float)
    if formula.startswith("UNESCO"):
        return _sound_unesco(T, P_dbar, S)
    # the depth formulas take the depth back from the pressure
    depth = np.asarray(P_dbar, float) * 1.0e4 / (reference_density()
                                                 * physics("GRAVITY"))
    if formula.startswith("Medwin"):
        return (1449.2 + 4.6 * T - 0.055 * T ** 2 + 0.00029 * T ** 3
                + (1.34 - 0.010 * T) * (S - 35.0) + 0.016 * depth)
    if formula.startswith("Mackenzie"):
        return (1448.96 + 4.591 * T - 5.304e-2 * T ** 2 + 2.374e-4 * T ** 3
                + 1.340 * (S - 35.0) + 1.630e-2 * depth + 1.675e-7 * depth ** 2
                - 1.025e-2 * T * (S - 35.0) - 7.139e-13 * T * depth ** 3)
    raise ValueError(f"unknown sound-speed formula {formula!r}")


def sound_speed_matrix(z, T, use_T=True, use_P=True, use_S=True):
    """Sound speed c(z, time) from the temperature matrix T(z, time) (or one
    profile).  use_T False: T = the reference temperature of the physical
    parameters; use_P False: P = 0; use_S False: S = 0.  The pressure is
    P = ρ̄ g z with ρ̄ the mean density of T (equation of state) or the
    fixed density.  Returns (c, info dict with rho_mean, S, T_reference)."""
    z = np.asarray(z, float)
    T = np.asarray(T, float)
    finite = np.isfinite(T)
    rho_mean = (float(np.nanmean(density(T[finite]))) if finite.any()
                else reference_density())
    T_used = T if use_T else np.where(finite, physics("SOUND_T_REFERENCE"),
                                      np.nan)
    depth = z[:, None] if T.ndim == 2 else z
    P = pressure_dbar(depth, rho_mean) if use_P else np.zeros_like(depth)
    S = physics("SALINITY") if use_S else 0.0
    c = sound_speed(T_used, P, S)
    return c, dict(rho_mean=rho_mean, S=S,
                   T_reference=None if use_T
                   else physics("SOUND_T_REFERENCE"))


# ---------------------------------------------------------------------------
# STC profiler (Valeport SWiFT SVP): CSV export
# ---------------------------------------------------------------------------
def stc_profile_files(folder):
    """The STC profiles of a folder: [(file name, start time UTC)], sorted
    by time (the CSV exports of the SWiFT SVP; files that cannot be read are
    left out)."""
    out = []
    if not folder or not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".csv"):
            continue
        start = _stc_first_time(os.path.join(folder, name))
        if start is not None:
            out.append((name, start))
    out.sort(key=lambda item: item[1])
    return out


def _stc_time(text):
    text = text.strip().replace("/", "-").replace(" ", "T")
    try:
        return np.datetime64(text, "ms")
    except ValueError:
        return None


def _stc_first_time(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.split(",")
                if len(parts) >= 3 and parts[0].strip()[:1].isdigit():
                    return _stc_time(parts[0])
    except OSError:
        return None
    return None


def read_stc_csv(path):
    """One STC profile (SWiFT SVP CSV export: Date/Time, Depth,
    Temperature, Sound Velocity, ...).  Returns dict with 'time' (n,)
    datetime64 ms (UTC), 'depth' (m), 'temperature' (°C), 'sound_speed'
    (m s⁻¹, measured), 'start', 'end', 'name', 'instrument'."""
    rows, header, instrument = [], None, ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if header is None:
                if parts[0].lower().startswith("date"):
                    header = [part.lower() for part in parts]
                elif not instrument:
                    instrument = line
                continue
            if not parts[0][:1].isdigit():
                continue
            rows.append(parts)
    if header is None or not rows:
        raise ValueError(f"{os.path.basename(path)}: no STC data found")

    def column(word):
        index = next(i for i, name in enumerate(header) if word in name)
        return np.array([_num(row[index]) if index < len(row) else np.nan
                         for row in rows], float)

    time = np.array([_stc_time(row[0]) for row in rows], "datetime64[ms]")
    return dict(time=time, depth=column("depth"),
                temperature=column("temp"),
                sound_speed=column("sound"), start=time[0], end=time[-1],
                name=os.path.basename(path), instrument=instrument)


def read_vp2_header(path):
    """[HEADER] of a SWiFT SVP .vp2 file as a dict of strings (key=value
    lines), e.g. 'Latitude', 'Longitude', 'DateStartTime', 'SerialNumber'."""
    header = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        inside = False
        for line in handle:
            line = line.strip()
            if line.startswith("["):
                inside = line.upper() == "[HEADER]"
                if not inside and header:
                    break
                continue
            if inside and "=" in line:
                key, value = line.split("=", 1)
                header[key.strip()] = value.strip()
    return header


def stc_position(folder, csv_name):
    """(latitude, longitude) of an STC profile from the header of the .vp2
    file with the same name as its CSV; (nan, nan) when there is none."""
    stem = os.path.splitext(csv_name)[0]
    for extension in (".vp2", ".VP2"):
        path = os.path.join(folder, stem + extension)
        if os.path.exists(path):
            header = read_vp2_header(path)
            try:
                return (float(header["Latitude"]),
                        float(header["Longitude"]))
            except (KeyError, ValueError):
                break
    return (np.nan, np.nan)


def stc_descent_speed(profile):
    """Mean descent speed (m s⁻¹) of an STC profile (dict of read_stc_csv,
    or the path of its CSV file): from the first sample to the deepest one,
    (z_max − z_first) / (t(z_max) − t_first).  NaN when it cannot be
    computed."""
    if isinstance(profile, str):
        profile = read_stc_csv(profile)
    depth = np.asarray(profile["depth"], float)
    good = np.isfinite(depth)
    if good.sum() < 2:
        return np.nan
    deepest = int(np.nanargmax(depth))
    seconds = ((profile["time"][deepest] - profile["time"][0])
               / np.timedelta64(1, "ms")) / 1000.0
    return float((depth[deepest] - depth[0]) / seconds) if seconds > 0 \
        else np.nan


# ---------------------------------------------------------------------------
# DTS products searched in a folder (STC comparison)
# ---------------------------------------------------------------------------
COMBINED_NAMES = ("Combined", "mean", "both")      # older names of Combined
_DTS_TIMES = {}                                    # path -> (mtime, info)


def _combined_group(handle):
    for name in COMBINED_NAMES:
        group = handle.groups.get(name)
        if group is not None and "T_calibrated" in group.variables \
                and "time" in group.variables:
            return group
    return None


def dts_combined_times(path):
    """(channel name, times) of the Combined channel of a preprocessed
    product (cached by modification time); None when the file has none."""
    import netCDF4
    try:
        stamp_ = os.path.getmtime(path)
    except OSError:
        return None
    cached = _DTS_TIMES.get(path)
    if cached is not None and cached[0] == stamp_:
        return cached[1]
    info = None
    try:
        with netCDF4.Dataset(path) as handle:
            group = _combined_group(handle)
            if group is not None:
                times = np.asarray(group["time"][:]).astype("int64") \
                    .astype("datetime64[ms]")
                info = (group.name, times)
    except Exception:                              # noqa: BLE001
        info = None
    _DTS_TIMES[path] = (stamp_, info)
    return info


def find_dts_products(root, max_depth=5):
    """Preprocessed DTS products (.nc with a Combined channel) under
    ``root``: [(path, configuration folder name)], sorted."""
    out = []
    if not root or not os.path.isdir(root):
        return out
    base = root.rstrip(os.sep).count(os.sep)
    for folder, folders, files in os.walk(root):
        if folder.count(os.sep) - base >= max_depth:
            folders[:] = []
        folders[:] = [f for f in folders if not f.startswith(".")]
        for name in sorted(files):
            if name.lower().endswith(".nc"):
                path = os.path.join(folder, name)
                if dts_combined_times(path) is not None:
                    out.append((path, os.path.basename(folder)))
    return sorted(out)


def closest_dts_profile(products, when):
    """Closest Combined DTS profile to the time ``when`` over the products
    [(path, configuration)]: dict(path, configuration, channel, index,
    time, shift_s (DTS − when)), or None."""
    best = None
    for path, configuration in products:
        info = dts_combined_times(path)
        if info is None or not info[1].size:
            continue
        channel, times = info
        index = int(np.argmin(np.abs(times - when)))
        shift = (times[index] - when) / np.timedelta64(1, "ms") / 1000.0
        if best is None or abs(shift) < abs(best["shift_s"]):
            best = dict(path=path, configuration=configuration,
                        channel=channel, index=index, time=times[index],
                        shift_s=float(shift))
    return best


def read_dts_profile(path, index, channel="Combined"):
    """(depth (m, from the water surface), T (°C)) of one calibrated
    profile of a preprocessed product."""
    import netCDF4
    with netCDF4.Dataset(path) as handle:
        group = handle.groups.get(channel) or _combined_group(handle)
        depth = np.asarray(group["z_calibrated"][:], float)
        T = np.ma.filled(np.ma.asarray(group["T_calibrated"][:, index],
                                       float), np.nan)
    return depth, T


def rms_difference_profile(z_ref, ref, z, values, width):
    """RMS of (values − ref) over depth windows of ``width`` (m), side by
    side: ``ref`` (on z_ref) is interpolated onto z where both exist.
    Returns (window centres, rms); empty arrays when they do not
    overlap."""
    z_ref, ref = np.asarray(z_ref, float), np.asarray(ref, float)
    z, values = np.asarray(z, float), np.asarray(values, float)
    good = np.isfinite(z_ref) & np.isfinite(ref)
    if good.sum() < 2:
        return np.array([]), np.array([])
    order = np.argsort(z_ref[good])
    zr, vr = z_ref[good][order], ref[good][order]
    zr, unique = np.unique(zr, return_index=True)
    vr = vr[unique]
    inside = np.isfinite(z) & np.isfinite(values) & (z >= zr[0]) \
        & (z <= zr[-1])
    if inside.sum() < 2:
        return np.array([]), np.array([])
    zz = z[inside]
    difference = values[inside] - np.interp(zz, zr, vr)
    order = np.argsort(zz)
    centres, mean_square = smooth_profile(zz[order], difference[order] ** 2,
                                          width, width)
    return centres, np.sqrt(mean_square)


def depth_resolution(z):
    """Native depth resolution of a profile: (median, smallest, largest)
    spacing (m) between successive distinct depths; NaNs when there are
    fewer than two depths."""
    z = np.unique(np.asarray(z, float)[np.isfinite(np.asarray(z, float))])
    if z.size < 2:
        return (np.nan, np.nan, np.nan)
    steps = np.diff(z)
    steps = steps[steps > 0]
    return (float(np.median(steps)), float(steps.min()), float(steps.max()))


def resolution_text(z, spread=False):
    """'Δz ≈ 0.25 m' (median spacing), or with ``spread`` the range of the
    spacings, 'Δz = 0.75–5 m' (sensors at irregular depths)."""
    median, low, high = depth_resolution(z)
    if not np.isfinite(median):
        return "Δz = ?"
    if spread and high > 1.5 * low:
        return f"Δz = {low:.2g}–{high:.2g} m"
    return f"Δz ≈ {median:.2g} m"


_CHAIN_TIMES = {}          # folder -> (file stamps, times)


def lexplore_times(root):
    """Times (UTC) of the LéXPLORE chain profiles of a folder (all the .nc
    files, cached until a file changes); an empty array without data."""
    if not root or not os.path.isdir(root):
        return np.array([], "datetime64[ms]")
    stamps = tuple(sorted((n, os.path.getmtime(os.path.join(root, n)))
                          for n in os.listdir(root)
                          if n.lower().endswith(".nc")))
    cached = _CHAIN_TIMES.get(root)
    if cached is not None and cached[0] == stamps:
        return cached[1]
    try:
        times = _load_lexplore_folder(root)[0]
    except Exception:                              # noqa: BLE001
        times = np.array([], "datetime64[ms]")
    _CHAIN_TIMES[root] = (stamps, times)
    return times


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance (m) between two positions (degrees)."""
    radius = 6_371_000.0
    phi1, phi2 = np.deg2rad(lat1), np.deg2rad(lat2)
    a = (np.sin((phi2 - phi1) / 2) ** 2 + np.cos(phi1) * np.cos(phi2)
         * np.sin(np.deg2rad(lon2 - lon1) / 2) ** 2)
    return float(2 * radius * np.arcsin(np.sqrt(a)))


def distance_to_lexplore(lat, lon):
    """Distance (m) from LéXPLORE (physical parameters); NaN without a
    position."""
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return np.nan
    return distance_m(physics("LEXPLORE_LAT"), physics("LEXPLORE_LON"),
                      lat, lon)


def at_lexplore(lat, lon):
    """True when a position lies within the LéXPLORE radius of the
    physical parameters (False without a position)."""
    distance = distance_to_lexplore(lat, lon)
    return bool(np.isfinite(distance)
                and distance <= physics("LEXPLORE_RADIUS_M"))


LAKE_OUTLINE_NAME = "Lake_Geneva_outline.geojson"


def load_lake_outline(folder):
    """Rings [(lon (n,), lat (n,), is_hole)] of the lake outline saved as
    GeoJSON in ``folder`` (Lake_Geneva_outline.geojson, else the first
    .geojson): the outer boundary of every polygon (is_hole False) and its
    islands (is_hole True); [] when there is none."""
    import json
    if not folder or not os.path.isdir(folder):
        return []
    names = sorted(n for n in os.listdir(folder)
                   if n.lower().endswith(".geojson"))
    names.sort(key=lambda n: n != LAKE_OUTLINE_NAME)
    if not names:
        return []
    with open(os.path.join(folder, names[0]), encoding="utf-8") as handle:
        data = json.load(handle)
    rings = []
    features = data.get("features", [data])
    for feature in features:
        geometry = feature.get("geometry", feature)
        polygons = (geometry["coordinates"] if geometry["type"] ==
                    "MultiPolygon" else [geometry["coordinates"]])
        for polygon in polygons:
            for index, ring in enumerate(polygon):
                ring = np.asarray(ring, float)
                rings.append((ring[:, 0], ring[:, 1], index > 0))
    return rings
