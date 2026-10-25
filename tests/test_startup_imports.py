"""Startup must not pull in heavy packages that are only needed for specific
files or actions (they cost ~1 s together, see visualization/vtk/vtklib.py)."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PROBE = """
import json, sys, time
t = time.perf_counter()
from pvp.controllers.MainCtrl import MainCtrl
from pvp.visualization.qtquick.VTKItem import VTKItem
dt = time.perf_counter() - t
heavy = ["igl", "netgen", "ngsolve", "meshio", "scipy", "h5py",
         "vtkmodules.all", "vtkmodules.vtkFiltersHyperTree"]
print(json.dumps({"loaded": [m for m in heavy if m in sys.modules], "seconds": dt}))
"""


def test_startup_does_not_import_heavy_packages():
    out = subprocess.run([sys.executable, "-c", _PROBE], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    result = json.loads(out.strip().splitlines()[-1])
    assert result["loaded"] == []
    assert result["seconds"] < 3.0     # ~0.65 s locally; generous for slow CI runners
