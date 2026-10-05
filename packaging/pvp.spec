# PyInstaller spec: one-folder build of pvp.
#   pyinstaller packaging/pvp.spec --noconfirm
# The compiled fTetWild module (+ its TBB library) is taken from PVP_EXT_DIR
# (a `cmake --install --component pyfloattetwildwrapper` prefix) if set,
# otherwise from wherever Python finds it.
import os
import sys
from PyInstaller.utils.hooks import collect_all

STRIP = sys.platform != "win32"   # drop debug symbols from shared libraries
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
EXT_DIR = os.environ.get("PVP_EXT_DIR")

pathex = [ROOT] + ([EXT_DIR] if EXT_DIR else [])
datas, binaries, hiddenimports = [], [], ["smoke_test", "resources.resources"]

# Netgen/NGSolve ship shared libraries and data next to their Python packages.
for pkg in ("netgen", "ngsolve"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# Intel MKL (used by NGSolve) loads most of its libraries at runtime via dlopen,
# which PyInstaller cannot see. Bundle the runtime parts explicitly, from the pip
# `mkl` package (sys.prefix/lib, sys.prefix/Library/bin) or a local oneAPI install
# found on LD_LIBRARY_PATH / PATH.
import glob
_MKL_PATTERNS = ["mkl_rt", "mkl_core", "mkl_intel_lp64", "mkl_intel_thread",
                 "mkl_gnu_thread", "mkl_sequential", "mkl_def", "mkl_mc3",
                 "mkl_avx2", "mkl_avx512", "mkl_vml_def", "mkl_vml_mc3",
                 "mkl_vml_avx2", "mkl_vml_avx512", "iomp5", "libiomp5md"]
_search = [os.path.join(sys.prefix, "lib"), os.path.join(sys.prefix, "Library", "bin")]
_search += os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
_search += os.environ.get("PATH", "").split(os.pathsep) if sys.platform == "win32" else []
_found = {}
for d in filter(os.path.isdir, _search):
    for pat in _MKL_PATTERNS:
        for f in glob.glob(os.path.join(d, f"lib{pat}.so*")) + glob.glob(os.path.join(d, f"{pat}*.dll")):
            _found.setdefault(os.path.basename(f), f)   # first hit wins
binaries += [(f, ".") for f in _found.values() if not os.path.islink(f) or f.endswith((".so.2", ".so.5"))]
print("pvp.spec: bundling MKL runtime:", sorted(_found))

# TBB etc. installed next to the fTetWild module
if EXT_DIR:
    for f in os.listdir(EXT_DIR):
        if not f.startswith("pyFloatTetwildWrapper"):
            binaries.append((os.path.join(EXT_DIR, f), "."))

# Large Qt parts pvp does not use.
excludes = [
    "tkinter", "matplotlib", "IPython",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtLocation", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort",
    "PySide6.QtSerialBus", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtTextToSpeech",
    "PySide6.QtHttpServer", "PySide6.QtQuick3D",
]

a = Analysis(
    [os.path.join(ROOT, "pvp.py")],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="pvp",
    console=True,          # keeps log output visible; --smoke-test needs stdout
    strip=STRIP,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="pvp", strip=STRIP, upx=False)
