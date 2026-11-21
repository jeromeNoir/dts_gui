"""Example script (Advanced > Python script): adds an item to the Advanced
menu, 'Temperature Gradient again', an exact copy of the window of the step
Data analysis > Temperature-gradient maps (ana.4.2.6): the same boxes and
inputs (channels, LeXPLORE chain, time window, layer, smoothing, individual
profiles with the click on the map, display), the same Run and Update plot
buttons, the same figures.

How: the description of the step's panel (gui_sections) is copied for a
new id with copy_section, and the GUI's own function of the step
(steps.STEPS["ana.4.2.6"][0], with its time window, layer, chain and colour
map handling) becomes the function of the new step; add_advanced_step puts
the new item in the Advanced menu.

Execute it once: the item appears at the end of the Advanced menu and
opens. Its figures are listed under 'Temperature Gradient again'. Its table
of individual profiles is the shared list of the analysis (as in the
original step). Executing the script again replaces the item.

Note: the copy runs the same function, so it also writes the same session
variables (A_GRADIENT, A_GRADIENT_PROFILES) as the original step: the last
of the two steps run gives their values.

Names used (given to every script): steps, copy_section,
add_advanced_step, gui.  See Claude_for_developer.md.
"""

SOURCE = "ana.4.2.6"                      # the step copied
NEW_ID = "adv.gradient_again"             # the id of the new item
TITLE = "Temperature Gradient again"      # its name in the Advanced menu

# the panel: the same boxes and fields; its buttons now run NEW_ID,
# NEW_ID.replot (Update) and @update:NEW_ID (Update plot)
section = copy_section(SOURCE, NEW_ID, TITLE)
section["description"] = ("Copy of Temperature-gradient maps (made by the "
                          "script temperature_gradient_again.py). "
                          + section.get("description", ""))

# the step: the GUI's own function of Temperature-gradient maps, which needs
# the data loaded (ana.0.1) like the original
function = steps.STEPS[SOURCE][0]
add_advanced_step(section, {NEW_ID: (function, ["ana.0.1"])},
                  profile_table="GRADIENT_PROFILES",
                  profile_picker=("GRADIENT_SELECT", "GRADIENT_PROFILES"))
gui.show_section(NEW_ID)                  # open it
print(f"Advanced > {TITLE} added (id {NEW_ID})")
