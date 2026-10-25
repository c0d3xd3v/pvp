# pvp

**pre / view / post** — a viewer for pre- and post-processing of FEM
simulations (structural mechanics and dynamics).

- Load surface meshes (`.stl`, `.obj`), volume meshes (`.vol`, `.msh`) and results (`.vtk`)
- Tetrahedral meshing of surfaces with [fTetWild](https://github.com/wildmeshing/fTetWild)
- Define boundary conditions by clicking surface faces, with a hover preview
  and undo/redo
- Export the volume mesh with boundary-condition labels (Netgen `.vol`,
  Gmsh `.msh`, CalculiX/Abaqus `.inp`, optionally with Tet10 elements)
- Save everything as a single project file (`.pvp`)
- Result visualisation (scalar fields, displacement animation)

Built with Python, PySide6 (Qt Quick, Material Dark style) and VTK.

## Download

Ready-to-run builds for **Windows** and **Linux** are attached to each
[release](https://github.com/c0d3xd3v/pvp/releases): unpack the archive and
start `pvp` (Linux) or `pvp.exe` (Windows). No install step, no Python
needed on the target machine.

Builds of the latest `master` are available as artifacts of the
[build workflow](https://github.com/c0d3xd3v/pvp/actions/workflows/build.yml).

The Linux build needs a distribution at least as new as Ubuntu 22.04 (it
uses the system's C++ runtime and graphics drivers) and runs through X11
(XWayland on Wayland desktops).

## Workflow

1. **Open a surface mesh** — folder icon in the toolbar, or drag & drop onto
   the window. STL/OBJ files prompt for the unit convention so the geometry
   lands in millimetres regardless of the source file.
2. **Meshing** tab — pick the mesher parameters and press **Run**:
   - *Edge Length (mm)* is the target edge length; the default is 5 % of the
     bounding-box diagonal.
   - *Epsilon (mm)* is how far the tet surface may deviate from the input
     (smaller = more surface detail, more tets).
   - Boundaries assigned before meshing are carried over to the new surface.
3. **Boundaries** tab — create boundary conditions and assign faces:
   - With a boundary selected, hovering highlights the region a click would
     paint. Left-click paints it into the active boundary; right-click
     removes it from whatever boundary it was in.
   - *Pick angle* sets the tolerance between neighbouring triangle normals
     that still counts as one region.
   - **Ctrl+Z** / **Ctrl+Shift+Z** undo and redo boundary edits.
4. **Export** (download icon) — writes `.vol`, `.msh` or `.inp` with volume
   plus boundary faces. Every face carries the name of its boundary;
   unassigned faces are written as `default`. Tet10 is optional for the
   formats that support it.
5. **Save project** (disk icon) — writes a `.pvp` file (HDF5) with the
   original input file, surface, boundaries, volume mesh and mesher
   parameters. Open it again like any other file (folder icon, drag & drop
   or on the command line).

The orientation gizmo in the lower-right corner snaps the camera to any
of the ±X / ±Y / ±Z views. Left-click rotates, middle-drag pans,
mouse-wheel zooms. The scene toggles (triangle outline, clip plane) live
in the sidebar.

## Project status

**0.1.0-alpha** — the pre-processing chain (surface → tet mesh → boundaries →
export) works end to end, but expect rough edges and breaking changes,
including in the project file format.

### Roadmap

- **Gmsh as an optional second mesher** — used when installed
  (`pip install gmsh`), not shipped in the release packages because Gmsh is
  GPL-licensed. Brings STEP/IGES import with CAD faces as selection units.
- **Local mesh size per boundary** — click a boundary, set a target edge
  length in mm.
- **Mesh quality view** — histogram, colouring by element quality together
  with the clip plane, jump to the worst element.

## Building from source

See [BUILD.md](BUILD.md) if you want to develop or build pvp yourself —
system packages, CMake toolchain, Python dependencies, packaging and the
test suite are documented there.

## License

pvp is licensed under the [Mozilla Public License 2.0](LICENSE) (MPL-2.0).

In short: you may use pvp for any purpose, including commercial and
closed-source projects, and combine it with code under other licenses. If
you distribute modified versions of pvp's own files, those modifications
must be made available under the MPL-2.0 as well. That way, improvements
find their way back into the project.

Third-party components keep their own licenses, e.g. fTetWild and libigl
(MPL-2.0), Qt/PySide6 (LGPLv3), Netgen/NGSolve (LGPL-2.1), VTK (BSD).
