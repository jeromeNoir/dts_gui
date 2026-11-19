"""gui_figures.py -- figures of the DTS GUI.

Every function returns a matplotlib Figure built with the object interface
(no pyplot), so that the figures can be made in the worker thread and shown
afterwards in the window.  The computations are in dts_core / dts_steps.
"""

import numpy as np
import matplotlib.dates as mdates
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure
import matplotlib
import matplotlib.patches

# Okabe-Ito colours (colour-blind safe)
RECORD_COLORS = {"CH1": "#0072B2", "CH2": "#E69F00", "CH3": "#E69F00",
                 "CH4": "#CC79A7", "Combined": "#009E73",
                 "LeXPLORE chain": "k"}
CYCLE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00")
INSTANT_COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
                  "#56B4E9")
LAYER_COLORS = ("#0072B2", "#D55E00", "#009E73")


def color(name, index=0):
    return RECORD_COLORS.get(name, CYCLE[index % len(CYCLE)])


def stamp(value):
    return str(np.datetime64(value, "s")).replace("T", " ")


def new_figure(width, height):
    # fixed 100 dpi: the figures look the same whatever the matplotlib
    # settings of the computer (Retina screens are handled by matplotlib)
    return Figure(figsize=(width, height), dpi=100, layout="constrained")


def panels(figure, rows, columns=1, **kwargs):
    axes = figure.subplots(rows, columns, squeeze=False, **kwargs)
    return axes[:, 0] if columns == 1 else axes


def format_time_axis(ax, minor_hours=6):
    """UTC date-and-time labels: dd.mm over the record, HH:MM when zoomed."""
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(
        locator, formats=["%Y", "%d.%m", "%d.%m", "%H:%M", "%H:%M", "%S.%f"],
        offset_formats=["", "%Y", "%m.%Y", "%d.%m.%Y", "%d.%m.%Y",
                        "%d.%m.%Y %H:%M"]))
    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=minor_hours))


def period_axis(ax):
    axis = ax.secondary_xaxis(
        "top", functions=(lambda f: 1.0 / (3600.0 * np.maximum(f, 1e-12)),
                          lambda q: 1.0 / (3600.0 * np.maximum(q, 1e-12))))
    axis.set_xlabel("period (h)")


def nearest_index(times, when):
    return int(np.argmin(np.abs(times - when)))


def mark_instants(ax, time, instants, top, style="--", labels=True):
    for order, (label, when) in enumerate(instants):
        index = nearest_index(time, when)
        ax.axvline(time[index], color=INSTANT_COLORS[order % 6], lw=1.5,
                   ls=style)
        if labels:
            ax.text(time[index], top, f"{label} ", rotation=90, ha="right",
                    va="top", fontsize=8, color="k")


# ---------------------------------------------------------------------------
# preprocessing
# ---------------------------------------------------------------------------
def truncation(raw, truncated):
    fig = new_figure(10, 4.5)
    ax = fig.subplots()
    for index, channel in enumerate(raw):
        c = color(channel, index)
        ax.plot(raw[channel]["x"], raw[channel]["tmp"], "-", color=c,
                lw=0.7, alpha=0.35, label=f"{channel} untruncated")
        ax.plot(truncated[channel]["x"], truncated[channel]["tmp"], "-",
                color=c, lw=1.5, label=f"{channel} truncated")
    length = float(next(iter(truncated.values()))["measurement_length"])
    for edge in (0.0, length):
        ax.axvline(edge, color="k", lw=0.8, ls="--", alpha=0.5)
    low = min(np.nanpercentile(r["tmp"], 1) for r in truncated.values())
    high = max(np.nanpercentile(r["tmp"], 99) for r in truncated.values())
    ax.set_ylim(low - 2.0, high + 2.0)
    ax.set_xlabel("length along fibre (m)")
    ax.set_ylabel("T (°C)")
    ax.set_title("Truncation to [0, measurement length] (dashed: the "
                 "truncation bounds)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    return fig


def mirror_distance(times, distances, means):
    fig = new_figure(10, 4)
    ax = fig.subplots()
    for index, channel in enumerate(distances):
        c = color(channel, index)
        ax.plot(times[channel], distances[channel], "-", color=c, lw=1.0,
                label=f"{channel} (mean {means[channel]:.3f} m)")
        ax.axhline(means[channel], color=c, lw=0.8, ls="--", alpha=0.7)
    ax.set_xlabel("time (UTC)")
    ax.set_ylabel("mirror distance (m)")
    format_time_axis(ax)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.suptitle("Mirror distance of every profile (dashed: time average)")
    return fig


def folded_profiles(folded):
    fig = new_figure(6.5, 7)
    ax = fig.subplots()
    for index, (channel, (z, down, up, mean)) in enumerate(folded.items()):
        c = color(channel, index)
        ax.plot(down, z, ":", color=c, lw=1.0, label=f"{channel} down")
        ax.plot(up, z, "--", color=c, lw=1.0, label=f"{channel} up")
        ax.plot(mean, z, "-", color=c, lw=1.8, label=f"{channel} mean")
    ax.invert_yaxis()
    ax.set_xlabel("T (°C)")
    ax.set_ylabel("z (m, 0 at the connector)")
    ax.set_title("Uncalibrated profiles: first profile folded at the mean "
                 "mirror distance", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    return fig


def _maps_with_chain(rows, chain, cmap, shading, title, colour_label,
                     chain_title="LeXPLORE chain (depth from the surface)"):
    """One panel per record (DTS rows), the LeXPLORE chain on top when
    given; one colour scale for all (1st-99th percentile)."""
    all_rows = ([(chain_title, chain["time"], chain["depth"],
                  chain["temperature"], "depth (m)",
                  (float(chain["depth"].max()), 0.0))] if chain else [])
    all_rows += rows
    values = np.concatenate([m[np.isfinite(m)] for _, _, _, m, _, _ in
                             all_rows])
    vmin, vmax = np.percentile(values, [1, 99])
    fig = new_figure(10, 3.2 * len(all_rows) + 0.6)
    axes = panels(fig, len(all_rows), sharex=True)
    for ax, (name, time, depth, matrix, y_label, y_limits) in zip(axes,
                                                                  all_rows):
        mesh = ax.pcolormesh(time, depth, matrix, cmap=cmap, vmin=vmin,
                             vmax=vmax, shading=shading)
        ax.set_ylim(*y_limits)
        ax.set_ylabel(y_label)
        ax.set_title(name, fontsize=10)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label=colour_label, shrink=0.9)
    fig.suptitle(title)
    return fig


def connector_maps(TIME, Z, T, max_depth, shading, cmap="seismic",
                   chain=None):
    rows = [(channel, TIME[channel], Z[channel], T[channel],
             "z (m, 0 at the connector)", (max_depth, 0.0)) for channel in T]
    return _maps_with_chain(
        rows, chain, cmap, shading,
        "U-shaped mean temperature T(z, time), connector coordinate",
        "T (°C)")


def shift_timeseries(offsets):
    fig = new_figure(10, 7)
    ax_z, ax_T = panels(fig, 2, sharex=True)
    for index, (channel, (time, z_off, _, T_off)) in enumerate(
            offsets.items()):
        c = color(channel, index)
        for ax, values, unit, fmt in ((ax_z, z_off, "m", "+.2f"),
                                      (ax_T, T_off, "K", "+.3f")):
            mean, std = float(np.nanmean(values)), float(np.nanstd(values))
            ax.plot(time, values, "-", color=c, lw=0.9,
                    label=f"{channel} (mean {mean:{fmt}} ± {std:.3f} {unit})")
            ax.axhline(mean, color=c, lw=0.8, ls="--", alpha=0.7)
            ax.axhspan(mean - std, mean + std, color=c, alpha=0.10, lw=0)
    ax_z.set_ylabel("vertical offset (m)")
    ax_z.set_title("vertical offset (positive = add to the DTS depth axis)",
                   fontsize=10)
    ax_T.set_ylabel("temperature shift (K)")
    ax_T.set_title("temperature shift at the best offset (positive = add "
                   "to the DTS temperature)", fontsize=10)
    ax_T.set_xlabel("time (UTC)")
    format_time_axis(ax_T)
    for ax in (ax_z, ax_T):
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("Best Z and T shift of the DTS onto the LeXPLORE chain")
    return fig


def first_profile_vs_chain(first_profiles, chain_first, residuals,
                           fit_range=None):
    """Left: the first fitted DTS profile, shifted by its own (Z, T) pair,
    with the chain profile of the same time step. Right: mean difference
    DTS - chain at every chain sensor over all the fitted profiles
    (± one standard deviation)."""
    fig = new_figure(11, 7)
    ax, ax_res = fig.subplots(1, 2, sharey=True,
                              gridspec_kw=dict(width_ratios=[1.4, 1]))
    for axis in (ax, ax_res):
        if fit_range is not None:
            axis.axhspan(*fit_range, color="#E69F00", alpha=0.15, lw=0,
                         label=f"depths of the fit ({fit_range[0]:g} - "
                               f"{fit_range[1]:g} m)")
    for index, (channel, (z, T, dz, dT, when)) in enumerate(
            first_profiles.items()):
        ax.plot(T, z, "-", color=color(channel, index), lw=1.6,
                label=f"{channel} + shifts ({dz:+.2f} m, {dT:+.2f} K)")
    chain_depth, chain_T, chain_time = chain_first
    ax.plot(chain_T, chain_depth, "o-", color="k", ms=4, lw=1.0, mfc="none",
            label="LeXPLORE chain")
    ax.set_xlabel("T (°C)")
    ax.set_ylabel("depth (m)")
    ax.set_ylim(float(chain_depth.max()) + 5, -2)
    ax.set_title(f"First fitted profile, {stamp(chain_time)} UTC",
                 fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.3)
    for index, (channel, (mean, std)) in enumerate(residuals.items()):
        c = color(channel, index)
        ax_res.plot(mean, chain_depth, "o-", color=c, ms=4, lw=1.2,
                    label=channel)
        ax_res.fill_betweenx(chain_depth, mean - std, mean + std, color=c,
                             alpha=0.15, lw=0)
    ax_res.axvline(0.0, color="k", lw=0.8)
    ax_res.set_xlabel("DTS - chain (K)")
    ax_res.set_title("Mean difference over the fitted profiles (± std)",
                     fontsize=10)
    ax_res.legend(fontsize=8, loc="lower right")
    ax_res.grid(alpha=0.3)
    fig.suptitle("Calibrated DTS vs the LeXPLORE chain")
    return fig


def scatter_vs_chain(scatter):
    fig = new_figure(5.5 * len(scatter), 5.2)
    axes = panels(fig, 1, len(scatter), sharex=True, sharey=True)[0] \
        if len(scatter) > 1 else panels(fig, 1)
    for ax, (channel, fit) in zip(axes, scatter.items()):
        points = ax.scatter(fit["T_chain"], fit["T_dts"], c=fit["depth"],
                            s=3, cmap="viridis_r", alpha=0.6, lw=0)
        span = np.array([fit["T_chain"].min(), fit["T_chain"].max()])
        ax.plot(span, span, "--", color="0.4", lw=1.0, label="1:1")
        ax.plot(span, fit["slope"] * span + fit["intercept"], "-",
                color="#D55E00", lw=1.2,
                label=f"fit {fit['slope']:.3f} T {fit['intercept']:+.2f}")
        ax.set_xlabel("T chain (°C)")
        ax.set_title(f"DTS {channel} shifted ({fit['z_shift']:+.2f} m, "
                     f"{fit['T_shift']:+.2f} K), rms {fit['rms']:.3f} K",
                     fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        ax.set_aspect("equal")
    axes[0].set_ylabel("T DTS (°C)")
    bar = fig.colorbar(points, ax=list(axes), label="depth (m)", shrink=0.9)
    bar.ax.invert_yaxis()
    fig.suptitle("Shifted DTS vs LeXPLORE chain, fitted time steps and "
                 "fitted depths")
    return fig


def calibrated_maps(calibrated, shading, cmap="seismic", chain=None):
    rows = [(channel, record["time"], record["z"], record["temperature"],
             "depth (m)", (float(record["z"].max()), 0.0))
            for channel, record in calibrated.items()]
    return _maps_with_chain(
        rows, chain, cmap, shading,
        "Calibrated temperature (depth from the water surface)", "T (°C)",
        chain_title="LeXPLORE chain")


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------
def analysis_maps(TIME, Z, T, chain, max_depth, shading, cmap="seismic",
                  instants=()):
    rows = ([("LeXPLORE chain", chain["time"], chain["depth"],
              chain["temperature"])] if chain else [])
    rows += [("Combined (mean of the channels)" if c == "Combined" else c,
              TIME[c], Z[c],
              T[c]) for c in T]
    values = np.concatenate([m[np.isfinite(m)] for *_, m in rows])
    vmin, vmax = np.percentile(values, [1, 99])
    fig = new_figure(10, 3.2 * len(rows) + 0.6)
    axes = panels(fig, len(rows), sharex=True)
    for ax, (title, time, depth, matrix) in zip(axes, rows):
        mesh = ax.pcolormesh(time, depth, matrix, cmap=cmap, vmin=vmin,
                             vmax=vmax, shading=shading)
        ax.set_ylim(max_depth, 0)
        if instants:
            mark_instants(ax, time, instants, 0.0)
        ax.set_ylabel("depth (m)")
        ax.set_title(title, fontsize=10)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label="T (°C)", shrink=0.9)
    fig.suptitle("Calibrated temperature T(depth, time)")
    return fig


def layer_maps(records, interfaces, max_depth, shading, title,
               profiles=()):
    """T(depth, time) of every record with the layer interfaces (Z1 solid,
    Z2 dashed)."""
    values = np.concatenate([T[np.isfinite(T)] for *_, T in records])
    vmin, vmax = np.percentile(values, [1, 99])
    fig = new_figure(10, 3.2 * len(records) + 0.6)
    axes = panels(fig, len(records), sharex=True)
    for ax, (name, time, depth, T) in zip(axes, records):
        mesh = ax.pcolormesh(time, depth, T, cmap="seismic", vmin=vmin,
                             vmax=vmax, shading=shading)
        if name in interfaces:
            itime, levels = interfaces[name]
            for k, z in enumerate(levels):
                ax.plot(itime, z, "-" if k == 0 else "--", color="k",
                        lw=1.2, label=f"Z{k + 1}")
            ax.legend(fontsize=8, loc="lower right")
        ax.set_ylim(max_depth, 0)
        if profiles:
            mark_instants(ax, time, profiles, 0.0)
        ax.set_ylabel("depth (m)")
        ax.set_title(name, fontsize=10)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label="T (°C)", shrink=0.9)
    fig.suptitle(title)
    return fig


def layer_profile_figure(label, when, entries, title, max_depth):
    """One individual profile: one panel per record (two columns at most)
    with the temperature profile, the interfaces at that time (dotted) and
    the layer model (dashed): for the best three-layer fit the continuous
    model of the fit (straight lines in the top and bottom layers, joined
    through the middle layer); otherwise a straight line fitted in each
    layer."""
    n = max(len(entries), 1)
    columns = min(2, n)
    rows = int(np.ceil(n / columns))
    fig = new_figure(5.0 * columns + 1.0, 5.2 * rows + 0.6)
    axes = np.atleast_1d(fig.subplots(rows, columns, sharey=True,
                                      squeeze=False)).ravel()
    for ax, (order, entry) in zip(axes, enumerate(entries)):
        name, time_at, depth, profile, levels, segments, model = entry
        colour = color(name, order)
        chain = name == "LeXPLORE chain"
        ax.plot(profile, depth, "o-" if chain else "-", color=colour,
                ms=3 if chain else 0, lw=1.0, label="profile")
        subtitle = ""
        if model is not None:
            z_model, T_model, slopes, rms = model
            ax.plot(T_model, z_model, "--", color="#D55E00", lw=2.0,
                    label="3-layer fit")
            subtitle = ("\nslopes " + " / ".join(f"{s:+.3f}"
                                                 for s in slopes) + " K/m"
                        + (f", rms {rms:.3f} K" if rms is not None else ""))
        else:
            first = True
            for segment in segments:
                if segment is None:
                    continue
                top, bottom, T_top, T_bottom = segment
                ax.plot([T_top, T_bottom], [top, bottom], "--",
                        color="#D55E00", lw=2.0,
                        label="line fitted in each layer" if first else None)
                first = False
        for k, z in enumerate(levels):
            if np.isfinite(z):
                ax.axhline(z, color="0.4", lw=0.9, ls=":")
                ax.text(1.0, z, f"Z{k + 1} = {z:.1f} m ",
                        transform=ax.get_yaxis_transform(), ha="right",
                        va="bottom", fontsize=8, color="0.3")
        ax.set_title(f"{name} ({str(time_at)[11:16]} UTC){subtitle}",
                     fontsize=9)
        ax.set_xlabel("T (°C)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="lower right")
    for ax in axes[len(entries):]:
        ax.set_visible(False)
    for ax in axes[::columns]:
        ax.set_ylabel("depth (m)")
    axes[0].set_ylim(max_depth, 0)
    fig.suptitle(f"{label} – {str(when)[:16].replace('T', ' ')} UTC – "
                 f"{title}")
    return fig


def raw_and_resampled(S, created, profiles, max_depth):
    """One panel per individual profile: every resampled channel (dashed)
    with its source channel (solid), at the profiles nearest in time."""
    n = len(profiles)
    columns = min(3, n)
    rows = int(np.ceil(n / columns))
    fig = new_figure(4.0 * columns + 1.0, 4.6 * rows + 0.6)
    axes = np.atleast_1d(fig.subplots(rows, columns, sharey=True,
                                      squeeze=False)).ravel()
    for ax, (label, when) in zip(axes, profiles):
        for order, name in enumerate(created):
            source = name[:-len("-resampled")]
            colour = color(source, order)
            for channel, style, width in ((source, "-", 1.0),
                                          (name, "--", 1.6)):
                if channel not in S["A_T"]:
                    continue
                index = nearest_index(S["A_TIME"][channel], when)
                ax.plot(S["A_T"][channel][:, index], S["A_Z"][channel],
                        style, color=colour, lw=width,
                        label=f"{channel} "
                              f"({str(S['A_TIME'][channel][index])[11:16]})")
        ax.set_title(f"{label}\n{str(when)[:16].replace('T', ' ')} UTC",
                     fontsize=9)
        ax.set_xlabel("T (°C)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    for ax in axes[n:]:
        ax.set_visible(False)
    for ax in axes[::columns]:
        ax.set_ylabel("depth (m)")
    axes[0].set_ylim(max_depth, 0)
    fig.suptitle("Raw (solid) and resampled (dashed) profiles")
    return fig


def individual_profiles(TIME, Z, T, chain, profiles, max_depth):
    """One panel per individual profile T(z) (three columns at most): every
    channel at its profile nearest in time, and the chain when shown."""
    n = len(profiles)
    columns = min(3, n)
    rows = int(np.ceil(n / columns))
    fig = new_figure(4.0 * columns + 1.0, 4.6 * rows + 0.6)
    axes = np.atleast_1d(fig.subplots(rows, columns, sharey=True,
                                      squeeze=False)).ravel()
    for ax, (label, when) in zip(axes, profiles):
        for order, channel in enumerate(T):
            index = nearest_index(TIME[channel], when)
            ax.plot(T[channel][:, index], Z[channel], "-",
                    color=color(channel, order), lw=1.3,
                    label=f"{channel} "
                          f"({str(TIME[channel][index])[11:16]})")
        if chain:
            index = nearest_index(chain["time"], when)
            ax.plot(chain["temperature"][:, index], chain["depth"], "o-",
                    color="k", ms=3, lw=0.8,
                    label=f"LeXPLORE ({str(chain['time'][index])[11:16]})")
        ax.set_title(f"{label}\n{str(when)[:16].replace('T', ' ')} UTC",
                     fontsize=9)
        ax.set_xlabel("T (°C)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    for ax in axes[n:]:
        ax.set_visible(False)
    for ax in axes[::columns]:
        ax.set_ylabel("depth (m)")
    axes[0].set_ylim(max_depth, 0)
    fig.suptitle("Individual profiles T(z)")
    return fig


def n_mean_profiles(N_mean, N_std, N_depth, max_depth):
    fig = new_figure(7, 8)
    ax = fig.subplots()
    for index, name in enumerate(N_mean):
        c = color(name, index)
        ax.plot(N_mean[name], N_depth[name], "-", color=c, lw=1.5, label=name)
        ax.fill_betweenx(N_depth[name],
                         np.maximum(N_mean[name] - N_std[name], 0.0),
                         N_mean[name] + N_std[name], color=c, alpha=0.2,
                         lw=0)
    ax.set_ylim(max_depth, 0)
    ax.set_xlabel("N (Hz)")
    ax.set_ylabel("depth (m)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.suptitle("Time-average Brunt-Väisälä frequency (mean ± std)")
    return fig


def n_maps(N_profiles, N_time, N_depth, max_depth, shading):
    values = np.concatenate([m[np.isfinite(m)] for m in N_profiles.values()])
    top = float(np.percentile(values, 99.5))
    fig = new_figure(10, 3.2 * len(N_profiles) + 0.6)
    axes = panels(fig, len(N_profiles), sharex=True)
    for ax, name in zip(axes, N_profiles):
        mesh = ax.pcolormesh(N_time[name], N_depth[name], N_profiles[name],
                             cmap="viridis", vmin=0.0, vmax=top,
                             shading=shading)
        ax.set_ylim(max_depth, 0)
        ax.set_ylabel("depth (m)")
        ax.set_title(name, fontsize=10)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label="N (Hz)", shrink=0.9)
    fig.suptitle("Brunt-Väisälä frequency N(depth, time)")
    return fig


def isotherm_depth(curves, T_iso, window=(None, None)):
    fig = new_figure(10, 4.2)
    ax = fig.subplots()
    for index, (name, time, depth, uncertainty) in enumerate(curves):
        c = color(name, index)
        ax.plot(time, depth, "-", color=c, lw=1.0, label=name)
        ax.fill_between(time, depth - uncertainty, depth + uncertainty,
                        color=c, alpha=0.2, lw=0)
    start, end = window
    if start is not None or end is not None:
        all_times = np.concatenate([c[1] for c in curves])
        ax.axvspan(start if start is not None else all_times.min(),
                   end if end is not None else all_times.max(),
                   color="0.85", zorder=0, label="FFT window")
    ax.invert_yaxis()
    ax.set_xlabel("time (UTC)")
    ax.set_ylabel("depth (m)")
    format_time_axis(ax)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.suptitle(f"Depth of the {T_iso:g} °C isotherm")
    return fig


def fft_depth_maps(rows, vmin, vmax, f_coriolis, max_depth, shading,
                   x_axis="frequency", x_scale="log",
                   value_label="FFT amplitude (K)", title=None):
    """x_axis 'frequency' (Hz) or 'period' (hours); x_scale 'log' or
    'linear'."""
    def x_of(f):
        f = np.asarray(f, dtype=float)
        if x_axis == "frequency":
            return f
        with np.errstate(divide="ignore"):
            return np.where(f > 0, 1.0 / f / 3600.0, np.nan)

    fig = new_figure(10, 3.2 * len(rows) + 0.6)
    axes = panels(fig, len(rows))
    for ax, (name, frequency, depth, amplitude, overlay) in zip(axes, rows):
        x = x_of(frequency)
        order = np.argsort(x)
        mesh = ax.pcolormesh(x[order], depth, amplitude[:, order],
                             cmap="viridis",
                             norm=LogNorm(vmin=vmin, vmax=vmax),
                             shading=shading)
        ax.set_xscale(x_scale)
        if overlay is not None:
            ax.plot(x_of(overlay[0]), overlay[1], "-", color="w", lw=1.5,
                    label="time-average N")
        ax.axvline(float(x_of(f_coriolis)), color="w", ls="--", lw=1.2,
                   label="f (Coriolis)")
        ax.legend(fontsize=8, loc="lower right")
        ax.set_xlim(float(np.nanmin(x)), float(np.nanmax(x)))
        ax.set_ylim(max_depth, 0)
        ax.set_ylabel("depth (m)")
        ax.set_title(name, fontsize=10)
    axes[-1].set_xlabel("frequency (Hz)" if x_axis == "frequency"
                        else "period (hours)")
    fig.colorbar(mesh, ax=list(axes), label=value_label, shrink=0.9)
    fig.suptitle(title or "Amplitude of the FFT over time at each depth")
    return fig


def isotherm_spectrum(spectra, T_pick, marks, axis, x_scale="log",
                      value_label="FFT amplitude (m)"):
    fig = new_figure(10, 4.2)
    ax = fig.subplots()

    def x_of(f):
        return f if axis == "frequency" else 1.0 / np.asarray(f) / 3600.0

    for index, (name, (frequency, amplitude)) in enumerate(spectra.items()):
        ax.plot(x_of(frequency), amplitude, "-", color=color(name, index),
                lw=1.0, label=name)
    ax.set_xscale(x_scale)
    ax.set_yscale("log")
    ax.axvline(x_of(marks["f_coriolis"]), color="0.3", ls="--", lw=1.2,
               label="f (Coriolis)")
    if marks["poincare"]:
        low, high = sorted(x_of(np.array(marks["poincare"])))
        ax.axvspan(low, high, color="#CC79A7", alpha=0.3, zorder=0,
                   label="Poincaré V1")
    if marks["N_band"]:
        low, high = sorted(x_of(np.array(marks["N_band"])))
        ax.axvspan(low, high, color="0.85", zorder=0,
                   label="N at the isotherm")
    if marks.get("dz"):                  # amplitude only
        ax.axhline(marks["dz"], color="0.3", ls=":", lw=1.2,
                   label="DTS vertical resolution")
    if marks.get("floor"):
        ax.set_ylim(bottom=marks["floor"])
    if axis == "frequency":
        ax.set_xlabel("frequency (Hz)")
        period_axis(ax)
    else:
        ax.set_xlabel("period (hours)")
    ax.set_ylabel(value_label)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.suptitle(f"Spectrum of the {T_pick:g} °C isotherm depth"
                 + ("" if axis == "frequency" else " vs period"))
    return fig


def vertical_fft_maps(rows, instants, vmin, vmax, vertical_axis, shading,
                      value_label="FFT amplitude (K)", title=None):
    """Maps time × k_z (or wavelength) of every record, the individual
    profiles marked by dotted lines."""
    label = ("wavenumber (1/m)" if vertical_axis == "wavenumber"
             else "wavelength (m)")
    fig = new_figure(10, 3.2 * len(rows) + 0.6)
    axes = panels(fig, len(rows), sharex=True)
    for ax_map, (name, time, wavenumber, amplitude) in zip(axes, rows):
        values = wavenumber if vertical_axis == "wavenumber" \
            else 1.0 / wavenumber
        mesh = ax_map.pcolormesh(time, values, amplitude, cmap="turbo",
                                 norm=LogNorm(vmin=vmin, vmax=vmax),
                                 shading=shading)
        ax_map.set_yscale("log")
        ax_map.set_ylabel(label)
        ax_map.set_title(name, fontsize=10)
        for order, (instant, when) in enumerate(instants):
            index = nearest_index(time, when)
            ax_map.axvline(time[index], color=INSTANT_COLORS[order % 6],
                           lw=2.0, ls=":")
            if ax_map is axes[0]:
                ax_map.text(time[index], 0.97, f" {instant}",
                            color="white", fontweight="bold",
                            transform=ax_map.get_xaxis_transform(),
                            ha="left", va="top", fontsize=8)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label=value_label, shrink=0.9)
    fig.suptitle(title or "Amplitude of the vertical FFT of each profile")
    return fig


def vertical_fft_profiles(rows, instants, vertical_axis, k_range=(None,
                          None), fits=None, value_label="FFT amplitude (K)",
                          quantity="T"):
    """Vertical FFT of the individual profiles: one panel per record (three
    columns at most), one curve per profile; the wavenumber range chosen is
    shaded, and the scaling laws a k^b fitted in it are drawn dashed."""
    label = ("wavenumber (1/m)" if vertical_axis == "wavenumber"
             else "wavelength (m)")
    n = len(rows)
    columns = min(3, n)
    lines = int(np.ceil(n / columns))
    fig = new_figure(4.2 * columns + 1.0, 3.8 * lines + 0.6)
    axes = np.atleast_1d(fig.subplots(lines, columns, sharex=True,
                                      sharey=True, squeeze=False)).ravel()
    for ax, (name, time, wavenumber, amplitude) in zip(axes, rows):
        values = wavenumber if vertical_axis == "wavenumber" \
            else 1.0 / wavenumber
        for order, (instant, when) in enumerate(instants):
            index = nearest_index(time, when)
            ax.plot(values, amplitude[:, index], "-",
                    color=INSTANT_COLORS[order % 6], lw=1.1,
                    label=f"{instant} ({str(time[index])[5:16]})"
                    .replace("T", " "))
        k_min, k_max = k_range
        if k_min or k_max:                 # wavenumber range chosen
            lo = k_min or float(wavenumber.min())
            hi = k_max or float(wavenumber.max())
            span = (lo, hi) if vertical_axis == "wavenumber" else \
                (1.0 / hi, 1.0 / lo)
            ax.axvspan(*span, color="0.85", alpha=0.6, zorder=0)
        for order, (fit_label, a, b, k_used) in enumerate(
                (fits or {}).get(name, [])):
            if not np.isfinite(b) or k_used.size < 2:
                continue
            k_line = np.array([k_used.min(), k_used.max()])
            x_line = k_line if vertical_axis == "wavenumber" else 1 / k_line
            ax.plot(x_line, a * k_line ** b, "--", lw=2.0,
                    color=INSTANT_COLORS[order % 6],
                    label=f"{fit_label}: {a:.2e} k^{b:+.2f}")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(name, fontsize=10)
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=7)
    for ax in axes[n:]:
        ax.set_visible(False)
    for ax in axes[:n]:
        ax.set_xlabel(label)
    for ax in axes[::columns]:
        ax.set_ylabel(value_label)
    fig.suptitle(f"Vertical spectrum of the individual profiles – "
                 f"{quantity}")
    return fig


def fft2_maps(rows, vmin, vmax, title, vertical_axis, time_axis, shading,
              columns=3, value_label="FFT amplitude (K)"):
    """2D FFT maps (frequency or period × k_z or wavelength), one panel per
    row (records or layers; ``columns`` at most), common colour scale."""
    n = len(rows)
    columns = min(columns, n)
    lines = int(np.ceil(n / columns))
    fig = new_figure(4.6 * columns + 1.4, 4.2 * lines + 0.8)
    axes = np.atleast_1d(fig.subplots(lines, columns, sharex=True,
                                      sharey=True, squeeze=False)).ravel()
    for ax, (name, frequency, k_z, amplitude) in zip(axes, rows):
        x = frequency if time_axis == "frequency" else \
            1.0 / frequency / 3600.0
        y = k_z if vertical_axis == "wavenumber" else 1.0 / k_z
        mesh = ax.pcolormesh(x, y, amplitude, cmap="turbo",
                             norm=LogNorm(vmin=vmin, vmax=vmax),
                             shading=shading)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(name, fontsize=10)
    for ax in axes[n:]:
        ax.set_visible(False)
    for ax in axes[:n]:
        ax.set_xlabel("frequency (Hz)" if time_axis == "frequency"
                      else "period (hours)")
    for ax in axes[::columns]:
        ax.set_ylabel("$k_z$ (1/m)" if vertical_axis == "wavenumber"
                      else "wavelength (m)")
    fig.colorbar(mesh, ax=list(axes[:n]), label=value_label,
                 shrink=0.9)
    fig.suptitle(title)
    return fig


def interfaces(time, layers, name):
    fig = new_figure(10, 4.2)
    ax = fig.subplots()
    ax.plot(time, layers["Z1"], "-", color="#0072B2", lw=1.0,
            label="Z1 (bottom of the mixed layer)")
    ax.plot(time, layers["Z2"], "-", color="#D55E00", lw=1.0,
            label="Z2 (bottom of the stratified layer)")
    ax.invert_yaxis()
    ax.set_xlabel("time (UTC)")
    ax.set_ylabel("depth (m)")
    format_time_axis(ax)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.suptitle(f"Three-layer interfaces ({name})")
    return fig


def staircases(profile_panels, layer="Whole column"):
    """One panel per individual profile (two columns at most), each with
    its own depth axis spanning the layer at that time: the
    temperature profile of every channel (thin line) and the detected steps
    as vertical segments at their mean temperature (thick, same colour)."""
    n = len(profile_panels)
    columns = min(2, n)
    rows = int(np.ceil(n / columns))
    fig = new_figure(5.0 * columns + 1.0, 5.0 * rows + 0.6)
    axes = np.atleast_1d(fig.subplots(rows, columns,
                                      squeeze=False)).ravel()
    for ax, (label, when, channels, extent) in zip(axes, profile_panels):
        top, bottom = np.inf, -np.inf
        counts = []
        for order, (name, time_at, stairs) in enumerate(channels):
            colour = color(name, order)
            if stairs is None:
                counts.append(f"{name}: –")
                continue
            ax.plot(stairs["T"], stairs["z"], "-", color=colour, lw=0.8,
                    alpha=0.8, label=f"{name} ({str(time_at)[11:16]})")
            for z_top, z_bottom, T_step in zip(stairs["step_top"],
                                               stairs["step_bottom"],
                                               stairs["step_T"]):
                ax.plot([T_step, T_step], [z_top, z_bottom], "-",
                        color=colour, lw=3.0, solid_capstyle="butt")
            counts.append(f"{name}: {stairs['step_T'].size}")
            top = min(top, float(stairs["z"][0]))
            bottom = max(bottom, float(stairs["z"][-1]))
        ax.set_title(f"{label} – {str(when)[:16].replace('T', ' ')} UTC\n"
                     f"steps: {', '.join(counts)}", fontsize=9)
        ax.set_xlabel("T (°C)")
        ax.grid(alpha=0.3)
        if np.isfinite(extent[0]) and np.isfinite(extent[1]) \
                and extent[1] > extent[0]:
            top, bottom = extent             # the layer at this time
        if np.isfinite(top) and np.isfinite(bottom) and bottom > top:
            ax.set_ylim(bottom, top)
        else:
            ax.invert_yaxis()
        if ax.lines:
            ax.legend(fontsize=7, loc="lower right")
        else:
            ax.text(0.5, 0.5, "layer too thin\nor not found",
                    transform=ax.transAxes, ha="center")
    for ax in axes[n:]:
        ax.set_visible(False)
    for ax in axes[:n]:
        ax.set_ylabel("depth (m)")
    fig.suptitle(f"Staircase detection - {layer} (thick segments: detected "
                 "steps at their mean temperature)")
    return fig


def _gray():
    cmap = matplotlib.colormaps["gray"].copy()
    cmap.set_bad("#cfe4f2")                    # masked region: pale blue
    return cmap


def gradient_maps(records, instants, title, shading):
    """dT/dz(depth, time) of every record on one figure (one panel per
    record, the chain first, common colour scale)."""
    records = ([r for r in records if r[0] == "LeXPLORE chain"]
               + [r for r in records if r[0] != "LeXPLORE chain"])
    values = np.concatenate([g[np.isfinite(g)] for *_, g in records])
    vmin, vmax = np.percentile(values, [1, 99])
    fig = new_figure(10, 3.2 * len(records) + 0.6)
    axes = panels(fig, len(records), sharex=True)
    max_depth = max(float(np.nanmax(depth)) for _, _, depth, _ in records)
    for ax, (name, time, depth, gradient) in zip(axes, records):
        mesh = ax.pcolormesh(time, depth, gradient, cmap=_gray(), vmin=vmin,
                             vmax=vmax, shading=shading)
        ax.set_ylim(max_depth, float(min(d[0] for _, _, d, _ in records)))
        mark_instants(ax, time, instants, float(depth[0]), style=":",
                      labels=False)
        ax.set_ylabel("depth (m)")
        ax.set_title("Combined (mean of the channels)" if name == "Combined"
                     else name, fontsize=10)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label="dT/dz (K/m)", shrink=0.9)
    fig.suptitle(title)
    return fig


def gradient_profiles(records, profiles, interfaces=None):
    """One panel per individual profile (three columns at most): dT/dz of
    every record at its profile nearest in time; Z1, Z2 (dashed) when the
    Multi-layer decomposition gave them (interfaces: (time, levels))."""
    n = len(profiles)
    columns = min(3, n)
    rows = int(np.ceil(n / columns))
    fig = new_figure(4.0 * columns + 1.0, 4.6 * rows + 0.6)
    axes = np.atleast_1d(fig.subplots(rows, columns, sharey=True,
                                      squeeze=False)).ravel()
    max_depth = max(float(np.nanmax(depth)) for _, _, depth, _ in records)
    for ax, (label, when) in zip(axes, profiles):
        for order, (name, time, depth, gradient) in enumerate(records):
            index = nearest_index(time, when)
            chain = name == "LeXPLORE chain"
            ax.plot(gradient[:, index], depth, "o-" if chain else "-",
                    color=color(name, order), ms=3 if chain else 0,
                    lw=0.8 if chain else 1.1,
                    label=f"{name} ({str(time[index])[11:16]})")
        if interfaces is not None:
            itime, levels = interfaces
            index = nearest_index(itime, when)
            for k, z in enumerate(levels):
                if np.isfinite(z[index]):
                    ax.axhline(z[index], color="0.4", lw=0.8, ls="--")
                    ax.text(1.0, z[index], f"Z{k + 1} = {z[index]:.1f} m ",
                            transform=ax.get_yaxis_transform(), ha="right",
                            va="bottom", fontsize=8, color="0.3")
        ax.axvline(0.0, color="0.6", lw=0.5)
        ax.set_title(f"{label}\n{str(when)[:16].replace('T', ' ')} UTC",
                     fontsize=9)
        ax.set_xlabel("dT/dz (K/m)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="lower left")
    for ax in axes[n:]:
        ax.set_visible(False)
    for ax in axes[::columns]:
        ax.set_ylabel("depth (m)")
    axes[0].set_ylim(max_depth, 0)
    fig.suptitle("Vertical temperature gradient, individual profiles")
    return fig


def waterfall(time, depth, T, layers, indices, spacing, title):
    fig = new_figure(12, 6)
    ax = fig.subplots()
    colours = matplotlib.colormaps["viridis"](
        np.linspace(0.0, 1.0, max(indices.size, 2)))
    for order, index in enumerate(indices):
        Z1, Z2 = layers["Z1"][index], layers["Z2"][index]
        inside = (depth >= Z1) & (depth <= Z2)
        layer_T = T[inside, index]
        if np.isfinite(layer_T).sum() < 2:
            continue
        offset = order * spacing
        x = layer_T - np.nanmean(layer_T) + offset
        z = depth[inside]
        ax.plot(x, z, "-", color=colours[order], lw=0.9)
        # label just above the top of its own curve
        first = int(np.argmax(np.isfinite(x)))
        ax.annotate(stamp(time[index])[-8:-3], (x[first], z[first]),
                    xytext=(0, 3), textcoords="offset points", rotation=90,
                    ha="center", va="bottom", fontsize=7,
                    color=colours[order], annotation_clip=False)
    ax.margins(y=0.12)                    # room for the labels
    ax.invert_yaxis()
    ax.set_xlabel(f"T anomaly, shifted by {spacing:g} K per profile (K)")
    ax.set_ylabel("depth (m)")
    ax.grid(alpha=0.3)
    ax.set_title(title + "; labels: UTC time", fontsize=10)
    return fig


# ---------------------------------------------------------------------------
# Advanced: sound speed
# ---------------------------------------------------------------------------
def sound_speed_maps(records, marks, shading, title):
    """c(depth, time) of every channel on one figure (common colour scale);
    marks: [(label, time)] of the STC profiles (dashed vertical lines)."""
    values = np.concatenate([c[np.isfinite(c)] for *_, c in records])
    vmin, vmax = np.percentile(values, [0.5, 99.5])
    fig = new_figure(10, 3.2 * len(records) + 0.6)
    axes = panels(fig, len(records), sharex=True)
    max_depth = max(float(np.nanmax(depth)) for _, _, depth, _ in records)
    for ax, (name, time, depth, c) in zip(axes, records):
        mesh = ax.pcolormesh(time, depth, c, cmap="viridis", vmin=vmin,
                             vmax=vmax, shading=shading)
        ax.set_ylim(max_depth, float(min(d[0] for _, _, d, _ in records)))
        for order, (label, when) in enumerate(marks):
            ax.axvline(when, color=INSTANT_COLORS[order % 6], lw=1.4,
                       ls="--")
            ax.text(when, float(depth[0]), f"STC {label} ", rotation=90,
                    ha="right", va="top", fontsize=8, color="k")
        ax.set_ylabel("depth (m)")
        ax.set_title("Combined (mean of the channels)" if name == "Combined"
                     else name, fontsize=10)
    axes[-1].set_xlabel("time (UTC)")
    format_time_axis(axes[-1])
    fig.colorbar(mesh, ax=list(axes), label="c (m/s)", shrink=0.9)
    fig.suptitle(title)
    return fig


def stc_profile_figure(profile, c_recalculated, dts, flag_text, formula,
                       rms_T=(), rms_c=(), rms_width=None):
    """One STC profile: temperature (left) and sound speed (right) vs
    depth with the DTS and the LéXPLORE chain (top row), and the RMS of
    their differences over depth windows (bottom row).  Every label of a
    DTS or chain curve carries its time shift."""
    fig = new_figure(11, 11)
    (ax_T, ax_c), (ax_rT, ax_rc) = fig.subplots(2, 2, sharey=True)
    z = profile["depth"]
    resolution = profile.get("resolution", "")
    extra = f" ({resolution})" if resolution else ""
    ax_T.plot(profile["temperature"], z, "k-", lw=1.4, label="STC" + extra)
    ax_c.plot(profile["sound_speed"], z, "k-", lw=1.4,
              label="STC measured" + extra)
    ax_c.plot(c_recalculated, z, "k:", lw=1.4,
              label="STC recalculated (from the STC T)")
    max_depth = float(np.nanmax(z))
    colours = {"STC": "0.4", "LeXPLORE chain": "#CC79A7"}
    for order, entry in enumerate(dts):
        chain = entry["name"] == "LeXPLORE chain"     # the STC is black:
        colour = "#CC79A7" if chain else color(entry["name"], order)
        colours.setdefault(entry["name"], colour)
        label = f"{entry['name']} ({entry['how']})"
        for ax, mean, std in ((ax_T, entry["T"], entry["T_std"]),
                              (ax_c, entry["c"], entry["c_std"])):
            ax.plot(mean, entry["depth"], "o-" if chain else "-",
                    color=colour, lw=1.0 if chain else 1.2,
                    ms=3.5 if chain else 0,
                    label=label if ax is ax_T else
                    f"{entry['name']} recalculated ({entry['how']})")
            if std is not None:
                ax.fill_betweenx(entry["depth"], mean - std, mean + std,
                                 color=colour, alpha=0.25, lw=0)
        max_depth = max(max_depth, float(np.nanmax(entry["depth"])))
    for ax, curves, unit in ((ax_rT, rms_T, "K"), (ax_rc, rms_c, "m/s")):
        for label, key, centres, values in curves:
            if values.size:
                ax.plot(values, centres, "o-", ms=3, lw=1.1,
                        color=colours.get(key, "0.3"),
                        ls=":" if key == "STC" else "-", label=label)
        ax.set_xlabel(f"RMS difference ({unit})")
        ax.set_xlim(left=0)
        if not curves:
            ax.text(0.5, 0.5, "no curve to compare", ha="center",
                    transform=ax.transAxes, color="0.5")
    ax_T.set_ylim(max_depth, 0)
    ax_T.set_xlabel("T (°C)")
    ax_c.set_xlabel("c (m/s)")
    for ax in (ax_T, ax_rT):
        ax.set_ylabel("depth (m)")
    for ax in (ax_T, ax_c, ax_rT, ax_rc):
        ax.grid(alpha=0.3)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=7, loc="lower right")
    ax_T.set_title("Temperature", fontsize=10)
    ax_c.set_title(f"Sound speed ({formula}; {flag_text})", fontsize=9)
    window = f"{rms_width:g} m windows" if rms_width else ""
    ax_rT.set_title(f"RMS of the temperature differences ({window})",
                    fontsize=9)
    ax_rc.set_title(f"RMS of the sound-speed differences ({window})",
                    fontsize=9)
    fig.suptitle(f"STC profile {profile['name']} — "
                 f"{stamp(profile['start'])} → "
                 f"{stamp(profile['end'])[11:]} UTC")
    return fig


def stc_position_map(outline, lexplore, points):
    """Positions of the STC profiles and of LéXPLORE: the whole lake (left)
    and a zoom around the profiles (right).  outline: [(lon, lat, is_hole)]
    rings (holes: islands, left white);
    lexplore: (lat, lon); points: [(label, lat, lon)]."""
    fig = new_figure(12, 5.6)
    ax_lake, ax_zoom = fig.subplots(1, 2, width_ratios=[1.6, 1])
    lat0 = lexplore[0]
    lats = [lexplore[0]] + [p[1] for p in points if np.isfinite(p[1])]
    lons = [lexplore[1]] + [p[2] for p in points if np.isfinite(p[2])]
    # zoom box: the profiles and the platform, at least 2.4 km wide (the shore near Pully shows)
    metre_lat = 1.0 / 111_195.0
    metre_lon = metre_lat / np.cos(np.deg2rad(lat0))
    half = max(1200.0, 0.6 * max((max(lats) - min(lats)) / metre_lat,
                                (max(lons) - min(lons)) / metre_lon))
    centre = (0.5 * (max(lats) + min(lats)), 0.5 * (max(lons) + min(lons)))
    box = (centre[1] - half * metre_lon, centre[1] + half * metre_lon,
           centre[0] - half * metre_lat, centre[0] + half * metre_lat)
    for ax in (ax_lake, ax_zoom):
        for lon, lat, hole in outline:             # water, then islands
            if not hole:
                ax.fill(lon, lat, color="#DCEBF5", zorder=0, lw=0)
        for lon, lat, hole in outline:
            if hole:
                ax.fill(lon, lat, color="white", zorder=0.5, lw=0)
            ax.plot(lon, lat, color="#4A7FA8", lw=0.6, zorder=1)
        ax.plot(lexplore[1], lexplore[0], marker="s", color="k", ms=8,
                ls="none", zorder=4, label="LéXPLORE")
        for order, (label, lat, lon) in enumerate(points):
            if np.isfinite(lat):
                ax.plot(lon, lat, marker="o", ms=7, ls="none", zorder=5,
                        color=INSTANT_COLORS[order % 6],
                        markeredgecolor="k", markeredgewidth=0.5,
                        label=f"STC {label}")
        ax.set_aspect(1.0 / np.cos(np.deg2rad(lat0)))
        ax.set_xlabel("longitude (°E)")
        ax.grid(alpha=0.3)
    ax_lake.set_ylabel("latitude (°N)")
    if outline:
        all_lon = np.concatenate([lon for lon, _, _ in outline])
        all_lat = np.concatenate([lat for _, lat, _ in outline])
        ax_lake.set_xlim(all_lon.min() - 0.03, all_lon.max() + 0.03)
        ax_lake.set_ylim(all_lat.min() - 0.02, all_lat.max() + 0.02)
    ax_lake.add_patch(matplotlib.patches.Rectangle(
        (box[0], box[2]), box[1] - box[0], box[3] - box[2], fill=False,
        ec="#D55E00", lw=1.2, zorder=6))
    ax_lake.set_title("Lake Geneva" + ("" if outline else
                                       " (no lake outline in the STC "
                                       "folder)"), fontsize=10)
    ax_zoom.set_xlim(box[0], box[1])
    ax_zoom.set_ylim(box[2], box[3])
    # scale bar of 500 m
    x0 = box[0] + 0.08 * (box[1] - box[0])
    y0 = box[2] + 0.07 * (box[3] - box[2])
    ax_zoom.plot([x0, x0 + 500 * metre_lon], [y0, y0], "k-", lw=2.5)
    ax_zoom.text(x0 + 250 * metre_lon, y0 + 0.02 * (box[3] - box[2]),
                 "500 m", ha="center", va="bottom", fontsize=8)
    ax_zoom.set_title("Zoom (orange box)", fontsize=10)
    ax_zoom.legend(fontsize=7, loc="upper right")
    ax_zoom.ticklabel_format(useOffset=False)
    fig.suptitle("Positions of the STC profiles and of LéXPLORE")
    return fig
