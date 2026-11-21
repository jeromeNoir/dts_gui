"""Example script (Advanced > Python script): reproduces the results of the
step Data analysis > Temperature-gradient maps (ana.4.2.6) EXACTLY, written
out step by step with the GUI's own library, then checks them against the
step itself.

What it does, in the order of the step:
  1. reads the inputs of the Temperature-gradient maps panel as they are
     now (channels, LeXPLORE chain, time window, layer, smoothing, profiles);
  2. selects the data as the GUI does: the whole record, or one time window
     W1, W2, ... (steps.windowed_data), or one individual profile
     (steps.profile_data); then one layer (steps.layered_data); the chain,
     when ticked, is interpolated onto a 1 m grid and added as one more
     channel (steps.chain_on_grid);
  3. computes dT/dz of every channel with dts_core.vertical_gradient
     (centred differences; with "Smooth T before dT/dz" the temperature is
     first averaged over depth windows);
  4. draws the same two figures (gui_figures.gradient_maps and
     gui_figures.gradient_profiles);
  5. runs the GUI's step on the same inputs and prints the largest
     difference with the result computed here (it must be 0).

Before: Load data and analysis settings (Data analysis), and choose the inputs in
Temperature-gradient maps (you do not need to Run it).
After: the figures are shown under Advanced > Python script, and the arrays
are in SCRIPT_RESULTS > reproduce_temperature_gradient (Save variables).

Names used (given to every script): S, np, core, steps, figs, params,
run_step, results, show, log.  See Claude_for_developer.md.
"""

STEP = "ana.4.2.6"          # the step reproduced (Temperature-gradient maps)
CHECK = True                # True: run the GUI's step too and compare

if "A_T" not in S:
    raise RuntimeError("load the data first: Data analysis > Load "
                       "preprocessed data")

# 1. the inputs of the step, as they are in its panel now --------------------
p = dict(params(STEP))
print("inputs:", {k: p[k] for k in ("CHANNELS", "INCLUDE_CHAIN",
                                    "TIME_WINDOW", "LAYER",
                                    "IS_GRADIENT_SMOOTHING",
                                    "GRADIENT_SMOOTH_WIDTH",
                                    "GRADIENT_SMOOTH_STEP") if k in p})

# 2. the data used: record, time window or profile, layer, chain -------------
data = {key: S.get(key) for key in steps.WINDOWED_KEYS}   # A_TIME, A_Z, A_T,
window = steps.parse_window(p.get("TIME_WINDOW"))         # A_LEXPLORE
profile = steps.parse_profile_choice(p.get("TIME_WINDOW"))
if window is not None:
    data.update(steps.windowed_data(S, window))
elif profile is not None:
    data.update(steps.profile_data(S, *profile))
layer = p.get("LAYER") or steps.WHOLE_COLUMN
if layer != steps.WHOLE_COLUMN:
    view = dict(S, **data)                   # the layer of the data selected
    data.update(steps.layered_data(view, layer.split(":")[0], window))

TIME, Z, T = dict(data["A_TIME"]), dict(data["A_Z"]), dict(data["A_T"])
channels = steps.selected(p, list(T))        # the channels ticked
chain = data.get("A_LEXPLORE") or {}
if p.get("INCLUDE_CHAIN") and S.get("A_IS_LEXPLORE") and chain:
    grid, T_chain = steps.chain_on_grid(chain)          # uniform 1 m grid
    TIME[steps.CHAIN_NAME] = chain["time"]
    Z[steps.CHAIN_NAME] = grid
    T[steps.CHAIN_NAME] = T_chain
    channels.append(steps.CHAIN_NAME)

# 3. dT/dz of every channel ----------------------------------------------------
width = p.get("GRADIENT_SMOOTH_WIDTH") if p.get("IS_GRADIENT_SMOOTHING") \
    else None
step = p.get("GRADIENT_SMOOTH_STEP") or width
maps = []
for channel in channels:
    depth_grid, gradient = core.vertical_gradient(Z[channel], T[channel],
                                                  width, step)
    maps.append((channel, TIME[channel], depth_grid, gradient))
    results[f"dTdz_{channel}"] = gradient                   # K/m (z, t)
    results[f"depth_{channel}"] = depth_grid                # m
    results[f"time_{channel}"] = TIME[channel]              # UTC
    print(f"{channel}: dT/dz {gradient.shape} (depth x time), "
          f"min {np.nanmin(gradient):.3f}, max {np.nanmax(gradient):.3f} K/m")

# 4. the same figures ----------------------------------------------------------
profiles = (steps.instants(p.get("GRADIENT_PROFILES") or [])
            or list(S.get("A_PROFILE_TIMES") or []))
show("Maps (reproduced)", figs.gradient_maps(
    maps, profiles, "Vertical temperature gradient dT/dz (reproduced)",
    steps.shading(p)))
if profiles:
    layers = S.get("A_LAYERS") or {}
    interfaces = layers.get("interfaces") or {}
    key = next((k for k in ["Combined"] + [m[0] for m in maps]
                if k in interfaces), None)
    show("Individual profiles (reproduced)", figs.gradient_profiles(
        maps, profiles, interfaces.get(key) if key else None))
results["profiles"] = [(label, str(when)) for label, when in profiles]

# 5. check against the GUI's own step ------------------------------------------
if CHECK:
    run_step(STEP, p)                        # writes S["A_GRADIENT"]
    worst = 0.0
    for channel, _, depth_grid, gradient in maps:
        gui = S["A_GRADIENT"][channel]["dTdz_K_per_m"]
        same_nan = np.array_equal(np.isnan(gui), np.isnan(gradient))
        diff = float(np.nanmax(np.abs(gui - gradient))) \
            if np.isfinite(gradient).any() else 0.0
        worst = max(worst, diff)
        print(f"check {channel}: max |GUI - script| = {diff:.3g} K/m, "
              f"same NaN: {same_nan}")
    results["max_difference_K_per_m"] = worst
    log(f"reproduction of {STEP}: largest difference {worst:.3g} K/m")
