"""Names of the channels shown by the GUI.

The XT writes each channel in a folder 'channel n'; the GUI calls it 'CHn'.
The profile-by-profile mean of the channels, built at the concatenation, is
'Combined' (it was 'mean' in the files written before version 2.37)."""

import re

COMBINED = "Combined"


def display_name(name):
    """'channel 3' -> 'CH3', 'mean' -> 'Combined'; other names unchanged
    (also inside derived names such as 'mean-resampled')."""
    name = str(name)
    match = re.fullmatch(r"channel\s*(\d+)(.*)", name)
    if match:
        return f"CH{match.group(1)}{match.group(2)}"
    if name == "mean" or name.startswith("mean-"):
        return COMBINED + name[4:]
    return name


def folder_name(name):
    """'CH3' -> 'channel 3' (the folder of the XT); other names unchanged."""
    match = re.fullmatch(r"CH(\d+)", str(name))
    return f"channel {match.group(1)}" if match else str(name)


def rename_keys(mapping):
    """Copy of a dict with the keys renamed by display_name."""
    return {display_name(key): value for key, value in mapping.items()}
