# Building pvp from source

Most users do not need this file — ready-to-run builds are attached to
each [release](https://github.com/c0d3xd3v/pvp/releases). This file is for
developers.

Tested on Debian 13 with Python 3.12, GCC 14, CMake 3.31.

## Requirements

**System packages** (for building the fTetWild extension):

```bash
sudo apt install build-essential cmake git libgmp-dev
```

- A C++17 compiler with OpenMP (GCC is fine)
- GMP (`libgmp-dev`)
- Internet access during the first build: CMake fetches Eigen, pybind11,
  TBB and fTetWild's other third-party libraries

**Python packages:**

```bash
pip install -r requirements.txt
```

`ngsolve` also installs `netgen-mesher`, which is used for reading and
writing `.vol` files.

## Build

```bash
git clone --recursive https://github.com/c0d3xd3v/pvp.git
cd pvp
# if you cloned without --recursive:
git submodule update --init --recursive

pip install -e .
```

`pip install -e .` runs CMake on `external/floattetwild-wrapper` (see
`setup.py`). That builds fTetWild and the Python module
`pyFloatTetwildWrapper`. The first build takes a while and the build
directory (`external/floattetwild-wrapper/build`) grows to about 1 GB.
Check the result with:

```bash
python3 -c "import pyFloatTetwildWrapper"
```

The app also starts without the module, but then meshing is unavailable.

## Run

```bash
./run.sh              # or: PYTHONPATH=src python3 -m pvp
./run.sh mesh.stl     # optionally load a mesh (.stl, .obj, .vol, .msh, .vtk) on start
```

QML files and icons are loaded from compiled Qt resources (`qrc:/`).
`src/pvp/__main__.py` regenerates `src/pvp/resources_rc.py` with `pyside6-rcc` on start
whenever it is missing or older than a file listed in
`src/pvp/resources/resources.qrc` (the generated file is not tracked in git). New
QML files or icons must be added to `src/pvp/resources/resources.qrc`.

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

The fTetWild tests are skipped if `pyFloatTetwildWrapper` has not been
built.

## Project structure

| Path | Contents |
|---|---|
| `src/pvp/__main__.py` | Entry point (`python -m pvp`); `smoke_test.py` next to it backs `--smoke-test` |
| `src/pvp/controllers/` | Thin QML-facing controllers (`MainCtrl` creates the project and wires them; `PreProcCtrl`, `MeshingCtrl`, `SceneCtrl`, ...) |
| `src/pvp/qml/` | User interface (Qt Quick) |
| `src/pvp/visualization/vtk/` | VTK actors, `PartitionView` (shows the partitions), clip plane, mouse interaction |
| `src/pvp/visualization/qtquick/` | `VTKItem`: VTK rendering inside Qt Quick |
| `src/pvp/meshing/` | Mesher interface (`TetMesher.py`) and fTetWild implementation |
| `src/pvp/fileio/` | `readers.py`, the writers, the project file; `formats.py` maps extensions and lists the export formats |
| `src/pvp/model/` | Data model without Qt/VTK: `Project`, `Partitions` (boundary assignment + undo), `Mesh`/`ResultMesh` |
| `src/pvp/services/` | Project operations without Qt: open/save, mesher result + boundary transfer, export |
| `src/pvp/geometry/` | Face regions for selection, bounding box |
| `src/pvp/resources/` | Qt resources: icons, colormaps (`resources.qrc`, also lists the QML files) |
| `tests/` | pytest suite |
| `external/fTetWild` | fTetWild (git submodule) |
| `external/floattetwild-wrapper` | pybind11 wrapper around fTetWild |
