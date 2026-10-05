# PyInstaller runtime hook (runs before the app).
#
# netgen's __init__ loads the OpenCascade libraries of the `netgen-occt`
# package by absolute path, looked up from that package's installed file list
# (importlib.metadata). Those paths point into the build machine's Python
# environment. In the bundle the libraries sit next to everything else
# (see pvp.spec) and the system loader finds them there, so make netgen skip
# its lookup by reporting the package as not installed.
import importlib.metadata as _md

_original_metadata = _md.metadata


def _metadata(name):
    if name.lower().replace("_", "-") == "netgen-occt":
        raise _md.PackageNotFoundError(name)
    return _original_metadata(name)


_md.metadata = _metadata
