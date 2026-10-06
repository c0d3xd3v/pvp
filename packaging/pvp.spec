# PyInstaller spec: one-folder build of pvp.
#   pyinstaller packaging/pvp.spec --noconfirm
# The compiled fTetWild module (+ its TBB library) is taken from PVP_EXT_DIR
# (a `cmake --install --component pyfloattetwildwrapper` prefix) if set,
# otherwise from wherever Python finds it.
import os
import sys
from PyInstaller.utils.hooks import collect_all

# Don't strip: it corrupts manylinux wheels' libraries that were patched with
# patchelf (e.g. numpy's bundled OpenBLAS: "ELF load command ... not
# page-aligned"). PyPI binaries are already stripped anyway.
STRIP = False
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
EXT_DIR = os.environ.get("PVP_EXT_DIR")

pathex = [ROOT] + ([EXT_DIR] if EXT_DIR else [])
datas, binaries, hiddenimports = [], [], ["smoke_test", "resources.resources"]

# Netgen/NGSolve ship shared libraries and data next to their Python packages.
# ngsolve_openblas (PyPI builds of ngsolve) is imported dynamically and preloads
# its OpenBLAS (libopenblasp-r*.so, soname libopenblas.so.0) from its own folder,
# so it has to be bundled as a package, not just as a library.
import importlib.util
for pkg in ("netgen", "ngsolve", "ngsolve_openblas"):
    if importlib.util.find_spec(pkg) is None:
        continue
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h + [pkg]

# Binary companion packages of netgen/ngsolve install their shared libraries
# into the environment's data dir (<prefix>/lib on Linux, <prefix>/bin or
# Library/bin on Windows) where PyInstaller's dependency analysis does not
# look. Bundle every shared library they list. netgen additionally loads the
# OpenCascade ones by absolute path; rthook_netgen.py disables that lookup.
import importlib.metadata as _md
_COMPANIONS = ["netgen-occt", "mkl", "intel-openmp", "tbb"]
for _dist in _COMPANIONS:
    try:
        _files = _md.files(_dist) or []
    except _md.PackageNotFoundError:
        continue   # e.g. a self-built netgen/ngsolve without these packages
    _n = 0
    for f in _files:
        p = str(f.locate())
        # keep symlinked sonames too (libTKernel.so.7.8 -> .so.7.8.1): that is
        # the name other libraries link against
        if (p.endswith(".dll") or ".so" in os.path.basename(p)) and os.path.exists(p):
            binaries.append((p, "."))
            _n += 1
    print(f"pvp.spec: bundling {_n} libraries of {_dist}")

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
    runtime_hooks=[os.path.join(SPECPATH, "rthook_netgen.py")],
    noarchive=False,
)
# Linux: use the system's C++ runtime. The bundled one comes from the build
# machine (Ubuntu 22.04, GLIBCXX_3.4.30); newer distros' Mesa GL drivers need a
# newer libstdc++ and fail to load against the old one ("Could not initialize
# GLX"). Every distro newer than the build machine has a compatible libstdc++.
if sys.platform.startswith("linux"):
    _system_runtime = ("libstdc++.so", "libgcc_s.so")
    a.binaries = [b for b in a.binaries if not os.path.basename(b[0]).startswith(_system_runtime)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="pvp",
    icon=os.path.join(ROOT, "resources", "icons", "pvp.ico"),   # Windows .exe icon
    console=True,          # keeps log output visible; --smoke-test needs stdout
    strip=STRIP,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="pvp", strip=STRIP, upx=False)
