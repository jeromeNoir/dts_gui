"""Default folders of the DTS GUI, read from default_paths.ini.

default_paths.ini (next to this file) holds the full path of each data
folder on your own computer; it is personal, so it is not in the git
repository (see .gitignore).  default_paths_template.ini, which is in the
repository, has the same keys with empty values: copy it to
default_paths.ini and fill in your own folders (README, section
"Default folders").  Without default_paths.ini, for a key left empty, or
for a path that does not exist on this computer, the folder field of the
GUI simply starts empty (the log says which keys were ignored).
"""

import configparser
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "default_paths.ini")
TEMPLATE = os.path.join(HERE, "default_paths_template.ini")
SECTION = "folders"
KEYS = ("xt_temperature", "lexplore", "stc", "dts")

_parser = configparser.ConfigParser(interpolation=None)
FOUND = bool(_parser.read(FILE, encoding="utf-8"))


def raw(key):
    """The path written in default_paths.ini for a key ('' when empty)."""
    if not _parser.has_section(SECTION):
        return ""
    value = _parser.get(SECTION, key, fallback="").strip().strip('"\'')
    return os.path.expanduser(value) if value else ""


def get(key):
    """Full path of one default folder; '' when it is not set or when the
    folder does not exist on this computer (then ignored)."""
    value = raw(key)
    return value if value and os.path.isdir(value) else ""


def status():
    """One line for the log at start."""
    if not FOUND:
        return ("no default_paths.ini: the folder fields start empty (copy "
                "default_paths_template.ini to default_paths.ini and enter "
                "your folders, see README)")
    empty = [k for k in KEYS if not raw(k)]
    absent = [k for k in KEYS if raw(k) and not get(k)]
    text = "default folders from default_paths.ini"
    if empty:
        text += f"; empty, ignored: {', '.join(empty)}"
    for key in absent:
        text += f"; ignored, folder not found: {key} = {raw(key)}"
    return text
