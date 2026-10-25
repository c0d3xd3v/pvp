from pathlib import Path

import numpy as np
from visualization.vtk import vtklib as vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from PySide6.QtCore import Slot, Signal, QObject, QUrl

from controllers.FileIOCtrl import FileIOCtrl
from geometry.PreProcSession import PreProcSession, PreProcMesh
from geometry.MeshRole import MeshRole
from geometry.AbstractMeshData import AbstractGeometryData
from geometry.InMemoryMeshData import InMemoryMeshData
from fileio.NetgenVolWriter import write_vol
from fileio.MshWriter import write_msh_v2, write_msh_v4
from fileio.InpWriter import write_inp_calculix, write_inp_abaqus
from fileio.export_model import ExportMesh, BCGroup
from fileio import project_h5


# Supported export formats. Each entry carries the file extension, a writer
# callable, and whether the writer honours the quadratic (Tet10) flag.
_EXPORT_FORMATS = {
    "vol":          {"ext": ".vol", "writer": write_vol,          "quadratic": False},
    "msh2":         {"ext": ".msh", "writer": write_msh_v2,       "quadratic": True},
    "msh4":         {"ext": ".msh", "writer": write_msh_v4,       "quadratic": True},
    "inp_calculix": {"ext": ".inp", "writer": write_inp_calculix, "quadratic": True},
    "inp_abaqus":   {"ext": ".inp", "writer": write_inp_abaqus,   "quadratic": True},
}


class PreProcCtrl(QObject):
    sessionChanged = Signal()
    partitionsChanged = Signal()

    def __init__(self):
        super().__init__()
        self.__session = PreProcSession()
        self.__fileio_ctrl = FileIOCtrl()
        self.__scene_ctrl = None
        self.__selection_ctrl = None

    def set_controllers(self, scene_ctrl, selection_ctrl):
        self.__scene_ctrl = scene_ctrl
        self.__selection_ctrl = selection_ctrl
        self.__scene_ctrl.partitions.on_changed = self.partitionsChanged.emit

    def get_session(self) -> PreProcSession:
        return self.__session

    def __start_new_project(self, source_path: str):
        """A freshly loaded geometry invalidates everything derived from the
        previous one (volume, background, mesher parameters in mm)."""
        for role in MeshRole:
            self.__session.clear(role)
        self.__session.set_source(source_path)
        self.__session.mesher_name = ""
        self.__session.mesher_params = {}

    @Slot(str, float)
    @Slot(str)
    def loadSurface(self, file_path: str, scale: float = 1.0):
        self.__fileio_ctrl.load_file(file_path, scale=scale)
        data = self.__fileio_ctrl.get_geometry()
        self.__start_new_project(file_path)
        self.__session.set(PreProcMesh(
            role=MeshRole.SURFACE,
            data=data,
            name=Path(file_path).name
        ))
        if self.__scene_ctrl:
            self.__scene_ctrl.reset_view_toggles()
            polydata = self.__scene_ctrl.add_surface_geometry(
                data.get_vertices(), data.get_triangles()
            )
            if self.__selection_ctrl:
                self.__selection_ctrl.set_picking_enabled(True)
                self.__selection_ctrl.load_geometry(polydata)
        self.sessionChanged.emit()

    @Slot(str)
    def loadVolume(self, file_path: str):
        self.__fileio_ctrl.load_file(file_path)
        data = self.__fileio_ctrl.get_geometry()

        # A .vol carries surface + volume + boundary info — treat as fresh project.
        self.__start_new_project(file_path)

        name = Path(file_path).name
        self.__session.set(PreProcMesh(role=MeshRole.VOLUME,  data=data, name=name))
        self.__session.set(PreProcMesh(role=MeshRole.SURFACE, data=data, name=name))

        if self.__scene_ctrl:
            self.__scene_ctrl.reset_view_toggles()
            # Build surface (also resets partitions, sets up FaceSelectionActor)
            polydata = self.__scene_ctrl.add_surface_geometry(
                data.get_vertices(), data.get_triangles()
            )
            if self.__selection_ctrl:
                self.__selection_ctrl.set_picking_enabled(True)
                self.__selection_ctrl.load_geometry(polydata)

            # Build volume
            if data.has_tetrahedra():
                self.__scene_ctrl.add_volume_unstructured_mesh(
                    data.get_vertices(), data.get_tetrahedra()
                )
            else:
                self.__scene_ctrl.add_volume_geometry(
                    data.get_vertices(), data.get_triangles()
                )

            # Populate partitions from BC info if the file carries any
            self.__populate_partitions_from_bcs(data)

        self.sessionChanged.emit()

    def __populate_partitions_from_bcs(self, data):
        bc_names = data.get_bc_names()
        triangle_bcs = data.get_triangle_bcs()
        if not bc_names or not triangle_bcs:
            return
        # Group triangle indices by BC number
        bc_to_triangles: dict[int, list[int]] = {}
        for tri_idx, bc in enumerate(triangle_bcs):
            bc_to_triangles.setdefault(bc, []).append(tri_idx)
        # Skip empty and "default" names — the latter is our sentinel written by
        # exportVolume for unassigned triangles. Treating it as unassigned again on
        # load makes the round-trip idempotent (no duplicate "default" entries).
        for bc_idx, bc_name in bc_names.items():
            name = (bc_name or "").strip()
            if not name or name.lower() == "default" or bc_idx not in bc_to_triangles:
                continue
            pid = self.__scene_ctrl.partitions.add(name, record=False)
            self.__scene_ctrl.partitions.assign_faces(bc_to_triangles[bc_idx], pid, record=False)

    @Slot()
    def createBackgroundMesh(self):
        surface = self.__session.surface
        if surface is None:
            return
        from geometry.OBBMeshGenerator import OBBMeshGenerator
        generator = OBBMeshGenerator(surface.data.get_vertices())
        polydata = generator.get_vtk_polydata()
        self.__session.set(PreProcMesh(
            role=MeshRole.BACKGROUND,
            data=generator,
            name="OBB"
        ))
        if self.__scene_ctrl:
            self.__scene_ctrl.add_background_geometry(polydata)
        self.sessionChanged.emit()

    def snapshot_boundary_assignments(self) -> dict | None:
        """Capture the current surface + partition state so a subsequent call
        to replace_project_with_mesh can port the boundary assignments onto
        the new tet-mesher boundary. Returns None if there is nothing to
        transfer (no surface, no named partitions, or every triangle
        unassigned)."""
        if self.__scene_ctrl is None:
            return None
        surface = self.__session.surface
        if surface is None or surface.data is None:
            return None
        part_ids = self.__scene_ctrl.partitions.ids_per_cell()
        if part_ids is None or not np.any(part_ids):
            return None
        names = {p.id: p.name for p in self.__scene_ctrl.partitions.all()}
        if not names:
            return None
        return {
            "vertices": np.asarray(surface.data.get_vertices(), dtype=np.float64),
            "triangles": np.asarray(surface.data.get_triangles(), dtype=np.int64),
            "ids_per_cell": np.asarray(part_ids, dtype=np.int32),
            "names": names,
        }

    def replace_project_with_mesh(self, vertices, triangles, tetrahedra,
                                  name: str, bc_transfer: dict | None = None):
        """Called by MeshingCtrl after a mesher finishes. Takes the mesher's
        output arrays and treats them as a complete new project — surface is
        the tet boundary, volume is the tet set. When bc_transfer is given,
        boundary assignments from before the meshing step are projected onto
        the new surface via nearest-cell lookup against the pre-meshing
        geometry (fTetWild emits a surface close to the input, so centroids
        map reliably back to their original triangles)."""
        V = np.asarray(vertices).tolist()
        tris = np.asarray(triangles).tolist()
        tets = np.asarray(tetrahedra).tolist()
        data = InMemoryMeshData(vertices=V, triangles=tris, tetrahedra=tets)

        # Treat as fresh project
        self.__session.clear(MeshRole.BACKGROUND)
        self.__session.set(PreProcMesh(role=MeshRole.VOLUME,  data=data, name=name))
        self.__session.set(PreProcMesh(role=MeshRole.SURFACE, data=data, name=name))

        if self.__scene_ctrl:
            # Rebuild surface actor; this also resets partitions via __prepare_rendering
            polydata = self.__scene_ctrl.add_surface_geometry(V, tris)
            if self.__selection_ctrl:
                self.__selection_ctrl.set_picking_enabled(True)
                self.__selection_ctrl.load_geometry(polydata)
            # Add volume
            self.__scene_ctrl.add_volume_unstructured_mesh(vertices, tetrahedra)
            if bc_transfer is not None:
                self.__transfer_boundaries(bc_transfer, vertices, triangles)

        self.sessionChanged.emit()

    def __transfer_boundaries(self, snap: dict, new_vertices, new_triangles):
        """Rebuild partitions on the new surface by nearest-cell projection
        onto the pre-meshing surface."""
        old_V = snap["vertices"]
        old_F = snap["triangles"]
        old_part_ids = snap["ids_per_cell"]
        old_names = snap["names"]

        # vtkPolyData for the old surface (cell locator target)
        pts = vtk.vtkPoints()
        pts.SetData(numpy_to_vtk(old_V, deep=True))
        conn = np.column_stack(
            (np.full(len(old_F), 3, dtype=np.int64), old_F)
        ).ravel()
        cells = vtk.vtkCellArray()
        cells.SetCells(len(old_F), numpy_to_vtk(conn, deep=True,
                                                array_type=vtk.VTK_ID_TYPE))
        old_pd = vtk.vtkPolyData()
        old_pd.SetPoints(pts)
        old_pd.SetPolys(cells)

        locator = vtk.vtkCellLocator()
        locator.SetDataSet(old_pd)
        locator.BuildLocator()

        new_V = np.asarray(new_vertices, dtype=np.float64)
        new_F = np.asarray(new_triangles, dtype=np.int64)
        centroids = new_V[new_F].mean(axis=1)

        closest = [0.0, 0.0, 0.0]
        cell_id = vtk.reference(0)
        sub_id = vtk.reference(0)
        dist2 = vtk.reference(0.0)
        new_part_ids = np.zeros(len(new_F), dtype=np.int32)
        for i, c in enumerate(centroids):
            locator.FindClosestPoint(c.tolist(), closest, cell_id, sub_id, dist2)
            cid = int(cell_id)
            if 0 <= cid < len(old_part_ids):
                new_part_ids[i] = int(old_part_ids[cid])

        # Recreate partitions by name (in original id order so colours stay stable)
        id_map: dict[int, int] = {}
        for old_pid in sorted(old_names.keys()):
            id_map[old_pid] = self.__scene_ctrl.partitions.add(old_names[old_pid], record=False)

        for old_pid, new_pid in id_map.items():
            indices = np.where(new_part_ids == old_pid)[0]
            if indices.size:
                self.__scene_ctrl.partitions.assign_faces(indices, new_pid, record=False)

    # --- project file ------------------------------------------------------

    @Slot(result=bool)
    def canSaveProject(self) -> bool:
        s = self.__session.surface
        return s is not None and s.data is not None

    @Slot(str, result=str)
    def saveProject(self, file_path: str) -> str:
        """Write the whole session to a .pvp file. Returns "" or an error message."""
        if file_path.startswith("file:"):
            file_path = QUrl(file_path).toLocalFile()
        if not file_path.endswith(project_h5.EXTENSION):
            file_path += project_h5.EXTENSION
        if not self.canSaveProject() or self.__scene_ctrl is None:
            return "Nothing to save: no geometry loaded."
        s = self.__session
        parts = self.__scene_ctrl.partitions
        surf = s.surface.data
        tris = np.asarray(surf.get_triangles(), dtype=np.int64)
        ids = parts.ids_per_cell()
        state = project_h5.ProjectState(
            surface_vertices=np.asarray(surf.get_vertices(), dtype=np.float64),
            surface_triangles=tris,
            partition_ids=ids if ids is not None else np.zeros(len(tris), dtype=np.int32),
            partitions=parts.all(),
            next_partition_id=parts.next_id(),
            current_partition=parts.current_id(),
            normal_angle=self.__selection_ctrl.getNormalCompareAngle() if self.__selection_ctrl else 10.0,
            source_name=s.source_name,
            source_bytes=s.source_bytes,
            mesher_name=s.mesher_name,
            mesher_params=dict(s.mesher_params),
        )
        if s.volume is not None and s.volume.data is not None and s.volume.data.has_tetrahedra():
            vol = s.volume.data
            state.volume_vertices = np.asarray(vol.get_vertices(), dtype=np.float64)
            state.volume_triangles = np.asarray(vol.get_triangles(), dtype=np.int64)
            state.volume_tetrahedra = np.asarray(vol.get_tetrahedra(), dtype=np.int64)
        try:
            project_h5.save_project(file_path, state)
        except Exception as e:
            print(f"saveProject failed: {e}")
            return str(e)
        print(f"Saved project {file_path}")
        return ""

    def loadProject(self, file_path: str) -> str:
        """Replace the session with a .pvp file. Returns "" or an error message."""
        try:
            state = project_h5.load_project(file_path)
        except Exception as e:
            print(f"loadProject failed: {e}")
            return str(e)

        for role in MeshRole:
            self.__session.clear(role)
        name = Path(file_path).stem
        surface = InMemoryMeshData(vertices=state.surface_vertices.tolist(),
                                   triangles=state.surface_triangles.tolist())
        if state.has_volume:
            volume = InMemoryMeshData(vertices=state.volume_vertices.tolist(),
                                      triangles=state.volume_triangles.tolist(),
                                      tetrahedra=state.volume_tetrahedra.tolist())
            if (np.array_equal(state.volume_vertices, state.surface_vertices)
                    and np.array_equal(state.volume_triangles, state.surface_triangles)):
                surface = volume    # as after meshing / loading a .vol: one shared mesh
            self.__session.set(PreProcMesh(role=MeshRole.VOLUME, data=volume, name=name))
        self.__session.set(PreProcMesh(role=MeshRole.SURFACE, data=surface, name=name))
        self.__session.source_name = state.source_name
        self.__session.source_bytes = state.source_bytes
        self.__session.mesher_name = state.mesher_name
        self.__session.mesher_params = dict(state.mesher_params)

        if self.__scene_ctrl:
            self.__scene_ctrl.reset_view_toggles()
            polydata = self.__scene_ctrl.add_surface_geometry(surface.get_vertices(),
                                                              surface.get_triangles())
            if self.__selection_ctrl:
                self.__selection_ctrl.set_picking_enabled(True)
                self.__selection_ctrl.set_normal_compare_angle(state.normal_angle)
                self.__selection_ctrl.load_geometry(polydata)
            if state.has_volume:
                self.__scene_ctrl.add_volume_unstructured_mesh(state.volume_vertices,
                                                               state.volume_tetrahedra)
            self.__scene_ctrl.partitions.restore(state.partitions, state.partition_ids,
                                                 state.next_partition_id,
                                                 state.current_partition)
        self.sessionChanged.emit()
        print(f"Loaded project {file_path}")
        return ""

    # --- undo / redo of boundary edits --------------------------------------

    @Slot()
    def undo(self):
        if self.__scene_ctrl:
            self.__scene_ctrl.partitions.undo()

    @Slot()
    def redo(self):
        if self.__scene_ctrl:
            self.__scene_ctrl.partitions.redo()

    @Slot(bool)
    def setPickingEnabled(self, enabled: bool):
        if self.__selection_ctrl:
            self.__selection_ctrl.set_picking_enabled(enabled)

    @Slot(str, result=int)
    def createPartition(self, name: str) -> int:
        if not self.__scene_ctrl or not name.strip():
            return -1
        return self.__scene_ctrl.partitions.add(name.strip())

    @Slot(int)
    def deletePartition(self, pid: int):
        if self.__scene_ctrl:
            self.__scene_ctrl.partitions.delete(pid)

    @Slot(int)
    def selectPartition(self, pid: int):
        if self.__scene_ctrl:
            self.__scene_ctrl.partitions.set_current(pid if pid > 0 else None)

    @Slot(result='QVariantList')
    def getPartitions(self) -> list:
        if not self.__scene_ctrl:
            return []
        current = self.__scene_ctrl.partitions.current_id()
        result = []
        for p in self.__scene_ctrl.partitions.all():
            r, g, b = p.color
            hex_color = "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
            result.append({
                "id": p.id,
                "name": p.name,
                "color": hex_color,
                "selected": p.id == current,
            })
        return result

    @Slot(result=bool)
    def canExportVolume(self) -> bool:
        vol_mesh = self.__session.volume
        if vol_mesh is None or vol_mesh.data is None:
            return False
        return vol_mesh.data.has_tetrahedra() and len(vol_mesh.data.get_triangles()) > 0

    def __collect_bc_groups(self, n_triangles: int) -> list[BCGroup]:
        """Map the current partitions to triangle groups via the FaceSelectionActor's
        PartitionIds cell array (the source of truth for who owns what). Every
        triangle must end up in some group, otherwise the exported surface has
        holes; unassigned triangles go into a "default" group."""
        part_ids = self.__scene_ctrl.partitions.ids_per_cell() if self.__scene_ctrl else None
        if part_ids is None:
            return [BCGroup("default", np.arange(n_triangles, dtype=np.int64))]
        if part_ids.shape[0] != n_triangles:
            raise ValueError(f"surface has {part_ids.shape[0]} triangles but the volume mesh "
                             f"boundary has {n_triangles}; they must be the same surface")

        groups = []
        assigned = np.zeros(n_triangles, dtype=bool)
        for p in self.__scene_ctrl.partitions.all():
            indices = np.where(part_ids == p.id)[0]
            if indices.size:
                groups.append(BCGroup(p.name, indices.astype(np.int64)))
                assigned[indices] = True
        unassigned = np.where(~assigned)[0]
        if unassigned.size:
            groups.append(BCGroup("default", unassigned.astype(np.int64)))
        return groups

    def __build_export_mesh(self) -> ExportMesh:
        data = self.__session.volume.data
        tris = data.get_triangles()
        groups = self.__collect_bc_groups(len(tris))
        return ExportMesh(
            nodes=data.get_vertices(),
            tets=data.get_tetrahedra(),
            surface_tri=tris,
            bc_groups=groups,
        )

    @Slot(result='QVariantMap')
    def getExportSummary(self) -> dict:
        """Numbers shown in the export dialog."""
        vol_mesh = self.__session.volume
        if not self.canExportVolume():
            return {"boundaries": 0, "unassigned": 0, "tets": 0}
        data = vol_mesh.data
        try:
            groups = self.__collect_bc_groups(len(data.get_triangles()))
        except ValueError:
            groups = []
        named = [g for g in groups if g.name != "default"]
        unassigned = sum(len(g.triangles) for g in groups if g.name == "default")
        return {"boundaries": len(named), "unassigned": unassigned,
                "tets": len(data.get_tetrahedra())}

    @Slot(result='QVariantList')
    def getExportFormats(self) -> list:
        """List exposed in the export dialog; QML drives the picker from it."""
        return [
            {"key": "vol",          "label": "Netgen volume mesh (.vol)",
             "ext": ".vol", "quadratic": False},
            {"key": "msh2",         "label": "Gmsh mesh v2 ASCII (.msh)",
             "ext": ".msh", "quadratic": True},
            {"key": "msh4",         "label": "Gmsh mesh v4 ASCII (.msh)",
             "ext": ".msh", "quadratic": True},
            {"key": "inp_calculix", "label": "CalculiX (.inp)",
             "ext": ".inp", "quadratic": True},
            {"key": "inp_abaqus",   "label": "Abaqus (.inp)",
             "ext": ".inp", "quadratic": True},
        ]

    @Slot(str, result=str)
    @Slot(str, str, bool, result=str)
    def exportVolume(self, file_path: str, format_key: str = "vol",
                     quadratic: bool = False) -> str:
        """Write the volume mesh incl. boundary-condition labels in the chosen
        format. Returns "" on success, otherwise an error message for the UI."""
        fmt = _EXPORT_FORMATS.get(format_key)
        if fmt is None:
            return f"Unknown export format: {format_key!r}"

        # QML passes a QUrl-like string (e.g. "file:///...") from the FileDialog
        if file_path.startswith('file:'):
            file_path = QUrl(file_path).toLocalFile()
        if not file_path.endswith(fmt["ext"]):
            file_path += fmt["ext"]
        if not self.canExportVolume():
            return "No volume mesh to export."

        try:
            mesh = self.__build_export_mesh()
            if fmt["quadratic"]:
                fmt["writer"](file_path, mesh, quadratic=bool(quadratic))
            else:
                fmt["writer"](file_path, mesh)
        except Exception as e:
            print(f"exportVolume failed: {e}")
            return str(e)
        print(f"Exported {file_path} ({format_key}, quadratic={quadratic}): "
              + ", ".join(f"{g.name} ({len(g.triangles)})" for g in mesh.bc_groups))
        return ""

    @Slot(result='QVariantList')
    def getMeshRoles(self) -> list:
        result = []
        for role, mesh in [
            ("surface",    self.__session.surface),
            ("volume",     self.__session.volume),
            ("background", self.__session.background),
        ]:
            result.append({
                "role": role,
                "name": mesh.name if mesh and mesh.data else "",
                "loaded": bool(mesh and mesh.data),
            })
        return result
