"""gui_export.py -- 'Save data' of the figures and Advanced > Save variables.

Two sources, one writer:

* figure_data(figure): the data drawn on a matplotlib figure, read back
  from its artists (lines, maps, shaded areas, points, images), one group
  per panel, with the axis labels and the panel title.  Time axes come back
  as datetime64 (UTC).
* the session variables (nested dicts of arrays, lists, numbers, text).

write(path, format, tree) writes a nested dict in one of the formats
FORMATS: npz, netcdf, hdf5, txt, csv, mat.  Times are kept as datetime64 in
npz, as int64 milliseconds since 1970-01-01 UTC (attribute 'units') in
NetCDF and HDF5, and as ISO text (UTC) in txt, csv and mat.  Text and
CSV write one file per table (a group of 1-D arrays of the same length
becomes the columns of one table; a matrix is written as it is), named
<file name>_<path of the table>.csv, with an index file <file name>.csv
listing them.
"""

from __future__ import annotations

import os
import re

import numpy as np

FORMATS = {                       # format -> (file filter, extension)
    "npz": ("NumPy (*.npz)", ".npz"),
    "netcdf": ("NetCDF (*.nc)", ".nc"),
    "hdf5": ("HDF5 (*.h5)", ".h5"),
    "txt": ("Text (*.txt)", ".txt"),
    "csv": ("CSV (*.csv)", ".csv"),
    "mat": ("MATLAB (*.mat)", ".mat"),
}
EPOCH = "milliseconds since 1970-01-01 00:00:00 UTC"


def file_filter():
    return ";;".join(f for f, _ in FORMATS.values())


def format_of(path, chosen_filter=""):
    """Format from the filter chosen in the file dialog, else from the
    file extension."""
    for name, (flt, ext) in FORMATS.items():
        if chosen_filter == flt:
            return name
    extension = os.path.splitext(path)[1].lower()
    for name, (_, ext) in FORMATS.items():
        if extension == ext:
            return name
    return "npz"


def with_extension(path, fmt):
    extension = FORMATS[fmt][1]
    return path if path.lower().endswith(extension) else path + extension


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def _is_date_axis(axis):
    import matplotlib.dates as mdates
    converter = (axis.get_converter() if hasattr(axis, "get_converter")
                 else getattr(axis, "converter", None))
    kinds = tuple(getattr(mdates, name) for name in
                  ("DateConverter", "ConciseDateConverter",
                   "_SwitchableDateConverter") if hasattr(mdates, name))
    if converter is not None and isinstance(converter, kinds):
        return True
    return isinstance(axis.get_major_formatter(),
                      (mdates.DateFormatter, mdates.AutoDateFormatter,
                       mdates.ConciseDateFormatter))


def _as_time(values):
    """Matplotlib date numbers -> datetime64[ms] (already datetime: kept)."""
    values = np.asarray(values)
    if np.issubdtype(values.dtype, np.datetime64):
        return values.astype("datetime64[ms]")
    import matplotlib.dates as mdates
    epoch = np.datetime64(mdates.get_epoch(), "ms")
    numbers = np.asarray(values, float)
    out = np.full(numbers.shape, np.datetime64("NaT"), "datetime64[ms]")
    good = np.isfinite(numbers) & (np.abs(numbers) < 1e6)
    out[good] = epoch + (numbers[good] * 86_400_000.0).astype("int64") \
        .astype("timedelta64[ms]")
    return out


def _clean(text):
    text = re.sub(r"[^0-9A-Za-z]+", "_", str(text)).strip("_")
    return text or "item"


def _unique(group, name):
    base, k = name, 2
    while name in group:
        name = f"{base}_{k}"
        k += 1
    return name


def figure_data(figure):
    """The data drawn on a figure: {panel: {artist: {x, y, values...}}}.
    A table result (pandas DataFrame) is returned column by column."""
    if hasattr(figure, "columns") and hasattr(figure, "to_dict"):
        return {"table": to_tree(figure)}
    from matplotlib.collections import PathCollection, PolyCollection, \
        QuadMesh
    from matplotlib.image import AxesImage
    from matplotlib.lines import Line2D
    tree = {"figure_title": (figure._suptitle.get_text()
                             if getattr(figure, "_suptitle", None) else "")}
    for index, ax in enumerate(figure.axes):
        if ax.get_label() == "<colorbar>":
            continue
        x_time, y_time = _is_date_axis(ax.xaxis), _is_date_axis(ax.yaxis)

        def X(values):
            return _as_time(values) if x_time else np.asarray(values, float)

        def Y(values):
            return _as_time(values) if y_time else np.asarray(values, float)

        panel = {"title": ax.get_title(), "xlabel": ax.get_xlabel(),
                 "ylabel": ax.get_ylabel()}
        for artist in ax.get_children():
            label = artist.get_label() if hasattr(artist, "get_label") \
                else ""
            label = label if isinstance(label, str) else ""
            named = label and not label.startswith("_")
            if isinstance(artist, Line2D):
                xdata, ydata = artist.get_xdata(), artist.get_ydata()
                if np.size(xdata) == 0:
                    continue
                key = _unique(panel, "line_" + (_clean(label) if named
                                                else str(len(panel))))
                panel[key] = {"label": label if named else "",
                              "x": X(xdata), "y": Y(ydata)}
            elif isinstance(artist, QuadMesh):
                coordinates = artist.get_coordinates()      # (ny+1, nx+1, 2)
                values = np.ma.filled(np.ma.asarray(artist.get_array(),
                                                    float), np.nan)
                ny, nx = coordinates.shape[0], coordinates.shape[1]
                if values.size == (ny - 1) * (nx - 1):      # cell edges
                    values = values.reshape(ny - 1, nx - 1)
                    xs = 0.5 * (coordinates[0, :-1, 0] + coordinates[0, 1:, 0])
                    ys = 0.5 * (coordinates[:-1, 0, 1] + coordinates[1:, 0, 1])
                else:                                       # gouraud: nodes
                    values = values.reshape(ny, nx)
                    xs, ys = coordinates[0, :, 0], coordinates[:, 0, 1]
                key = _unique(panel, "map")
                panel[key] = {"x": X(xs), "y": Y(ys), "values": values,
                              "colorbar": _colorbar_label(figure, artist)}
            elif isinstance(artist, AxesImage):
                values = np.ma.filled(np.ma.asarray(artist.get_array(),
                                                    float), np.nan)
                extent = artist.get_extent()
                key = _unique(panel, "image")
                panel[key] = {"values": values, "extent": np.asarray(extent)}
            elif isinstance(artist, PathCollection):
                offsets = np.asarray(artist.get_offsets())
                if offsets.size == 0:
                    continue
                key = _unique(panel, "points_" + (_clean(label) if named
                                                  else str(len(panel))))
                entry = {"label": label if named else "",
                         "x": X(offsets[:, 0]), "y": Y(offsets[:, 1])}
                array = artist.get_array()
                if array is not None and np.size(array) == len(offsets):
                    entry["values"] = np.asarray(array, float)
                panel[key] = entry
            elif isinstance(artist, PolyCollection) and \
                    not isinstance(artist, QuadMesh):
                for path_index, path in enumerate(artist.get_paths()):
                    vertices = path.vertices
                    if len(vertices) < 3:
                        continue
                    key = _unique(panel, "area_" + (_clean(label) if named
                                                    else str(len(panel))))
                    panel[key] = {"label": label if named else "",
                                  "x": X(vertices[:, 0]),
                                  "y": Y(vertices[:, 1])}
        texts = [t for t in ax.texts if t.get_text().strip()]
        if texts:
            positions = np.array([t.get_position() for t in texts], float)
            panel["texts"] = {"x": X(positions[:, 0]),
                              "y": Y(positions[:, 1]),
                              "text": np.array([t.get_text().strip()
                                                for t in texts])}
        name = _clean(ax.get_title()) if ax.get_title() else ""
        tree[_unique(tree, f"panel{index + 1}" + (f"_{name}" if name
                                                  else ""))] = panel
    return tree


def _colorbar_label(figure, mappable):
    colorbar = getattr(mappable, "colorbar", None)
    if colorbar is not None:
        return colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel()
    return ""


# ---------------------------------------------------------------------------
# variables -> plain tree
# ---------------------------------------------------------------------------
def to_tree(value, depth=0):
    """Session value -> nested dict of arrays / numbers / text (anything
    else becomes its text)."""
    if depth > 8:
        return str(value)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out[_unique(out, _clean(key))] = to_tree(item, depth + 1)
        return out
    if isinstance(value, np.ma.MaskedArray):
        value = np.ma.filled(value.astype(float), np.nan) \
            if value.dtype.kind in "iuf" else np.asarray(value)
    if isinstance(value, np.ndarray):
        if value.dtype == object:
            return to_tree(list(value), depth + 1)
        return value
    if hasattr(value, "to_dict") and hasattr(value, "columns"):   # pandas
        out = {"row": np.asarray(value.index).astype(str)}
        for column in value.columns:
            data = value[column].to_numpy()
            if data.dtype == object:
                data = data.astype(str)
            out[_unique(out, _clean(column))] = data
        return out
    if isinstance(value, (list, tuple)):
        if not value:
            return np.array([], float)
        try:
            array = np.asarray(value)
            if array.dtype != object:
                return array
        except (ValueError, TypeError):
            pass
        return {f"item{k}": to_tree(item, depth + 1)
                for k, item in enumerate(value)}
    if isinstance(value, (bool, np.bool_)):
        return np.int8(bool(value))
    if value is None:
        return ""
    if isinstance(value, (int, float, np.integer, np.floating, str,
                          np.datetime64, np.timedelta64)):
        return value
    return str(value)


def _leaves(tree, path=()):
    for key, value in tree.items():
        if isinstance(value, dict):
            yield from _leaves(value, path + (key,))
        else:
            yield path + (key,), value


def _time_ms(array):
    return np.asarray(array).astype("datetime64[ms]").astype("int64")


def _iso(array):
    return np.datetime_as_string(np.asarray(array).astype("datetime64[ms]"),
                                 unit="ms")


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------
def write(path, fmt, tree, title=""):
    """Write the nested dict ``tree``; returns the list of files written."""
    path = with_extension(path, fmt)
    return {"npz": _write_npz, "netcdf": _write_netcdf,
            "hdf5": _write_hdf5, "mat": _write_mat,
            "csv": lambda p, t, h: _write_tables(p, t, h, ","),
            "txt": lambda p, t, h: _write_tables(p, t, h, "\t")}[fmt](
                path, tree, title)


def _write_npz(path, tree, title):
    arrays = {"/".join(key): np.asarray(value) for key, value in _leaves(tree)}
    arrays["_title"] = np.asarray(title)
    np.savez_compressed(path, **arrays)
    return [path]


def _write_hdf5(path, tree, title):
    try:
        import h5py
    except ImportError:
        raise RuntimeError("the module h5py is needed for HDF5 "
                           "(pip install h5py)") from None
    with h5py.File(path, "w") as handle:
        handle.attrs["title"] = title
        for key, value in _leaves(tree):
            name = "/".join(key)
            array = np.asarray(value)
            if np.issubdtype(array.dtype, np.datetime64):
                dataset = handle.create_dataset(name, data=_time_ms(array))
                dataset.attrs["units"] = EPOCH
            elif array.dtype.kind in "US":
                handle.create_dataset(name, data=array.astype(object),
                                      dtype=h5py.string_dtype())
            elif np.issubdtype(array.dtype, np.timedelta64):
                dataset = handle.create_dataset(
                    name, data=array.astype("timedelta64[ms]").astype("int64"))
                dataset.attrs["units"] = "milliseconds"
            else:
                handle.create_dataset(name, data=array)
    return [path]


def _write_netcdf(path, tree, title):
    import netCDF4
    with netCDF4.Dataset(path, "w", format="NETCDF4") as handle:
        handle.title = title or "DTS GUI export"
        for key, value in _leaves(tree):
            group = handle
            for part in key[:-1]:
                group = group.groups.get(part) or group.createGroup(part)
            name = key[-1]
            array = np.asarray(value)
            if array.ndim == 0 and array.dtype.kind in "US":
                group.setncattr(name, str(array))
                continue
            units = None
            if np.issubdtype(array.dtype, np.datetime64):
                array, units = _time_ms(array), EPOCH
            elif np.issubdtype(array.dtype, np.timedelta64):
                array = array.astype("timedelta64[ms]").astype("int64")
                units = "milliseconds"
            elif array.dtype == bool:
                array = array.astype("i1")
            dims = []
            for axis, size in enumerate(array.shape):
                dim = f"{name}_dim{axis}"
                if dim not in group.dimensions:
                    group.createDimension(dim, size)
                dims.append(dim)
            if array.dtype.kind in "US":
                variable = group.createVariable(name, str, tuple(dims))
                flat = array.astype(str).ravel()
                for i, text in enumerate(flat):
                    variable[np.unravel_index(i, array.shape)] = text
            else:
                variable = group.createVariable(name, array.dtype,
                                                tuple(dims))
                variable[...] = array
            if units:
                variable.units = units
    return [path]


def _matlab_tree(tree):
    out = {}
    for key, value in tree.items():
        name = _clean(key)
        if not name[0].isalpha():
            name = "v_" + name
        name = _unique(out, name[:60])
        if isinstance(value, dict):
            out[name] = _matlab_tree(value)
            continue
        array = np.asarray(value)
        if np.issubdtype(array.dtype, np.datetime64):
            array = _iso(array)
        if array.dtype.kind in "US" and array.ndim > 0:
            out[name] = array.astype(object)        # cell array of text
        elif np.issubdtype(array.dtype, np.timedelta64):
            out[name] = array.astype("timedelta64[ms]").astype("int64")
        else:
            out[name] = array
    return out


def _write_mat(path, tree, title):
    try:
        from scipy.io import savemat
    except ImportError:
        raise RuntimeError("the module scipy is needed for MATLAB files "
                           "(pip install scipy)") from None
    data = _matlab_tree(tree)
    data["title"] = title
    savemat(path, data, long_field_names=True, do_compression=True,
            oned_as="column")
    return [path]


def _text_column(array):
    array = np.asarray(array)
    if np.issubdtype(array.dtype, np.datetime64):
        return _iso(array)
    return array


def _tables(tree, path=()):
    """(path, columns dict) for groups of 1-D arrays of one length, and
    (path, array) for the other arrays; scalars and text gathered apart."""
    columns, others, scalars = {}, [], []
    for key, value in tree.items():
        if isinstance(value, dict):
            continue
        array = np.asarray(value)
        if array.ndim == 0:
            scalars.append((path + (key,), value))
        elif array.ndim == 1:
            columns.setdefault(array.size, {})[key] = array
        else:
            others.append((path + (key,), array))
    out = []
    for size, group in columns.items():
        if len(group) == 1:
            (key, array), = group.items()
            out.append((path + (key,), {key: array}))
        else:
            out.append((path, group))
    out += [(p, a) for p, a in others]
    for key, value in tree.items():
        if isinstance(value, dict):
            sub, sub_scalars = _tables(value, path + (key,))
            out += sub
            scalars += sub_scalars
    return out, scalars


def _write_tables(path, tree, title, separator):
    stem, extension = os.path.splitext(path)
    tables, scalars = _tables(tree)
    written, index = [], []
    single = len(tables) == 1
    for table_path, content in tables:
        name = path if single else \
            f"{stem}_{'_'.join(table_path) or 'table'}{extension}"
        base = name
        k = 2
        while name in written:
            name = f"{os.path.splitext(base)[0]}_{k}{extension}"
            k += 1
        with open(name, "w", encoding="utf-8", newline="") as handle:
            handle.write(f"# {title}\n# {'/'.join(table_path)}\n")
            if isinstance(content, dict):
                keys = list(content)
                handle.write(separator.join(keys) + "\n")
                data = [_text_column(content[k]) for k in keys]
                for row in zip(*data):
                    handle.write(separator.join(str(v) for v in row) + "\n")
            else:
                array = np.asarray(content)
                handle.write(f"# matrix {' x '.join(map(str, array.shape))}"
                             "\n")
                matrix = array.reshape(array.shape[0], -1)
                matrix = _text_column(matrix) if np.issubdtype(
                    matrix.dtype, np.datetime64) else matrix
                for row in matrix:
                    handle.write(separator.join(str(v) for v in row) + "\n")
        written.append(name)
        index.append((name, "/".join(table_path)))
    if not single or scalars:
        info = path if not single else f"{stem}_info{extension}"
        with open(info, "w", encoding="utf-8", newline="") as handle:
            handle.write(f"# {title}\n")
            handle.write(f"name{separator}value\n")
            for key, value in scalars:
                value = _iso(value) if isinstance(value, np.datetime64) \
                    else value
                handle.write(f"{'/'.join(key)}{separator}{value}\n")
            if not single:
                handle.write(f"# tables{separator}\n")
                for name, table in index:
                    handle.write(f"{table}{separator}"
                                 f"{os.path.basename(name)}\n")
        written.insert(0, info)
    return written
