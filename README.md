# pvp

**pre / view / post** — a viewer for pre- and post-processing in numerical
computational tasks (CFD/FEM).

- Load surface meshes (`.stl`, `.obj`), volume meshes (`.vol`) and results (`.vtk`)
- Tetrahedral meshing of surfaces with [fTetWild](https://github.com/wildmeshing/fTetWild)
- Define boundary conditions by selecting surface faces
- Export the volume mesh with boundary-condition labels as Netgen `.vol`
- Result visualization (scalar fields, displacement animation)

Built with Python, PySide6 (Qt Quick, Material Dark style) and VTK.

## Download

Ready-to-run builds for **Windows** and **Linux** are attached to each
[release](https://github.com/c0d3xd3v/pvp/releases): unpack the archive and start
`pvp` (Linux) or `pvp.exe` (Windows). Builds of the latest `master` are available as
artifacts of the [build workflow](https://github.com/c0d3xd3v/pvp/actions/workflows/build.yml).

The Linux build needs a distribution at least as new as Ubuntu 22.04 (it uses the
system's C++ runtime and graphics drivers) and runs through X11 (XWayland on
Wayland desktops), see `QT_QPA_PLATFORM` in `pvp.py`.

## Project status
Early, very early ...

## Requirements

Tested on Debian 13 with Python 3.12, GCC 14, CMake 3.31.

**System packages** (for building the fTetWild extension):

```bash
sudo apt install build-essential cmake git libgmp-dev
```

- A C++17 compiler with OpenMP (GCC is fine)
- GMP (`libgmp-dev`)
- Internet access during the first build: CMake fetches Eigen, pybind11, TBB
  and fTetWild's other third-party libraries

**Python packages:**

```bash
pip install -r requirements.txt
```

`ngsolve` also installs `netgen-mesher`, which is used for reading and writing `.vol` files.

## Build

```bash
git clone --recursive https://github.com/c0d3xd3v/pvp.git
cd pvp
# if you cloned without --recursive:
git submodule update --init --recursive

pip install -e .
```

`pip install -e .` runs CMake on `external/floattetwild-wrapper` (see `setup.py`).
That builds fTetWild and the Python module `pyFloatTetwildWrapper`. The first build
takes a while and the build directory (`external/floattetwild-wrapper/build`) grows
to about 1 GB. Check the result with:

```bash
python3 -c "import pyFloatTetwildWrapper"
```

The app also starts without the module, but then meshing is unavailable.

## Run

```bash
./run.sh              # or: python3 pvp.py
./run.sh mesh.stl     # optionally load a mesh (.stl, .obj, .vol, .msh, .vtk) on start
```

QML files and icons are loaded from compiled Qt resources (`qrc:/`).
`pvp.py` regenerates `resources/resources.py` with `pyside6-rcc` on start whenever
it is missing or older than a file listed in `resources/resources.qrc` (the generated
file is not tracked in git). New QML files or icons must be added to
`resources/resources.qrc`.

## Packaging

The CI (`.github/workflows/build.yml`) builds a self-contained folder with
PyInstaller for Linux and Windows. Locally:

```bash
pip install pyinstaller
# fTetWild module + its shared libraries (TBB, ...) into ext/
cmake --install external/floattetwild-wrapper/build --prefix ext --component pyfloattetwildwrapper
PVP_EXT_DIR=$PWD/ext pyinstaller packaging/pvp.spec --noconfirm
dist/pvp/pvp --smoke-test        # checks the bundle without opening a window
```

## Tests

```bash
pip install pytest
python3 -m pytest tests
```

The fTetWild tests are skipped if `pyFloatTetwildWrapper` has not been built.

## Workflow

1. Open a surface mesh: folder icon in the toolbar, or drag & drop onto the window.
2. **Meshing** tab: choose the mesher parameters and press **Run**.
   - *Epsilon (rel)* controls how closely the tet surface follows the input
     (smaller = more surface detail, more tets).
   - *Edge Length (rel)* is the target edge length relative to the bounding-box diagonal.
3. **Boundaries** tab: create boundary conditions and assign faces by selecting them
   in the 3D view.
4. **Export** (download icon in the toolbar): writes a Netgen `.vol` with volume and
   boundary faces. Every face carries the name of its boundary condition; unassigned
   faces are exported as `default`.

## Project structure

| Path | Contents |
|---|---|
| `pvp.py` | Entry point |
| `controllers/` | Controllers exposed to QML (`MainCtrl` wires them; `PreProcCtrl`, `MeshingCtrl`, `SceneCtrl`, ...) |
| `qml/` | User interface (Qt Quick) |
| `visualization/vtk/` | VTK actors, boundary partitions, clip plane, mouse interaction |
| `visualization/qtquick/` | `VTKItem`: VTK rendering inside Qt Quick |
| `meshing/` | Mesher interface (`TetMesher.py`) and fTetWild implementation |
| `fileio/` | Readers and writers (`NetgenVolWriter.py` for `.vol` export) |
| `geometry/` | Mesh data interface/containers, pre-processing session, geometry helpers |
| `resources/` | Qt resources: icons, colormaps, textures (`resources.qrc`) |
| `tests/` | pytest suite |
| `external/fTetWild` | fTetWild (git submodule) |
| `external/floattetwild-wrapper` | pybind11 wrapper around fTetWild |

## License
pvp is licensed under the [Mozilla Public License 2.0](LICENSE) (MPL-2.0).

In short: you may use pvp for any purpose, including commercial and closed-source
projects, and combine it with code under other licenses. If you distribute modified
versions of pvp's own files, those modifications must be made available under the
MPL-2.0 as well. That way, improvements find their way back into the project.

Third-party components keep their own licenses, e.g. fTetWild and libigl (MPL-2.0),
Qt/PySide6 (LGPLv3), Netgen/NGSolve (LGPL-2.1), VTK (BSD).
