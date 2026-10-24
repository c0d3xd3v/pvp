# pvp

**pre / view / post** — a viewer for pre- and post-processing in numerical
computational tasks (CFD/FEM).

- Load surface meshes (`.stl`, `.obj`), volume meshes (`.vol`) and results (`.vtk`)
- Tetrahedral meshing of surfaces with [fTetWild](https://github.com/wildmeshing/fTetWild)
- Define boundary conditions by selecting surface faces
- Export the volume mesh with boundary-condition labels (Netgen `.vol`,
  Gmsh `.msh`, CalculiX/Abaqus `.inp`, optionally with Tet10 elements)
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
   - *Epsilon (rel)* controls how closely the tet surface follows the input
     (smaller = more surface detail, more tets).
   - *Edge Length (rel)* is the target edge length relative to the
     bounding-box diagonal.
3. **Boundaries** tab — create boundary conditions and assign faces:
   - Left-click paints the clicked region into the active boundary;
     right-click removes it from whatever boundary it was in.
   - *Pick angle* sets the flood-fill tolerance between neighbouring
     triangle normals.
4. **Export** (download icon) — writes `.vol`, `.msh` or `.inp` with volume
   plus boundary faces. Every face carries the name of its boundary;
   unassigned faces are written as `default`. Tet10 is optional for the
   formats that support it.

The orientation gizmo in the lower-right corner snaps the camera to any
of the ±X / ±Y / ±Z views. Left-click rotates, middle-drag pans,
mouse-wheel zooms. The scene toggles (triangle outline, clip plane) live
in the sidebar.

## Project status

Early, very early.

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
