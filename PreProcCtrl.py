from pathlib import Path

import numpy as np

from PySide6.QtCore import Slot, Signal, QObject, QUrl

from FileIOCtrl import FileIOCtrl
from PreProcSession import PreProcSession, PreProcMesh
from geometry.MeshRole import MeshRole
from geometry.AbstractMeshData import AbstractGeometryData
from geometry.InMemoryMeshData import InMemoryMeshData
from fileio.NetgenVolWriter import write_vol


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
        self.__scene_ctrl.partitions_changed_cb = self.partitionsChanged.emit

    def get_session(self) -> PreProcSession:
        return self.__session

    @Slot(str)
    def loadSurface(self, file_path: str):
        self.__fileio_ctrl.load_file(file_path)
        data = self.__fileio_ctrl.get_geometry()
        # New surface = new geometry: volume/background from a previous
        # geometry are no longer valid.
        self.__session.clear(MeshRole.VOLUME)
        self.__session.clear(MeshRole.BACKGROUND)
        self.__session.set(PreProcMesh(
            role=MeshRole.SURFACE,
            data=data,
            name=Path(file_path).name
        ))
        if self.__scene_ctrl:
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
        self.__session.clear(MeshRole.SURFACE)
        self.__session.clear(MeshRole.VOLUME)
        self.__session.clear(MeshRole.BACKGROUND)

        name = Path(file_path).name
        self.__session.set(PreProcMesh(role=MeshRole.VOLUME,  data=data, name=name))
        self.__session.set(PreProcMesh(role=MeshRole.SURFACE, data=data, name=name))

        if self.__scene_ctrl:
            # Build surface (also resets partitions, sets up FaceSelectionActor)
            polydata = self.__scene_ctrl.add_surface_geometry(
                data.get_vertices(), data.get_triangles()
            )
            if self.__selection_ctrl:
                self.__selection_ctrl.set_picking_enabled(True)
                self.__selection_ctrl.load_geometry(polydata)

            # Build volume
            if hasattr(data, 'get_tetrahedra') and data.get_tetrahedra():
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
        bc_names = getattr(data, 'get_bc_names', lambda: {})()
        triangle_bcs = getattr(data, 'get_triangle_bcs', lambda: [])()
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
            pid = self.__scene_ctrl.add_partition(name)
            self.__scene_ctrl.assign_faces_to_partition(bc_to_triangles[bc_idx], pid)

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

    def replace_project_with_mesh(self, vertices, triangles, tetrahedra, name: str):
        """Called by MeshingCtrl after a mesher finishes. Takes the mesher's
        output arrays and treats them as a complete new project — surface is
        the tet boundary, volume is the tet set. Partitions get reset (the
        old partitions were on a different surface topology).
        """
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

        self.sessionChanged.emit()

    @Slot(bool)
    def setPickingEnabled(self, enabled: bool):
        if self.__selection_ctrl:
            self.__selection_ctrl.set_picking_enabled(enabled)

    @Slot(str, result=int)
    def createPartition(self, name: str) -> int:
        if not self.__scene_ctrl or not name.strip():
            return -1
        return self.__scene_ctrl.add_partition(name.strip())

    @Slot(int)
    def deletePartition(self, pid: int):
        if self.__scene_ctrl:
            self.__scene_ctrl.delete_partition(pid)

    @Slot(int)
    def selectPartition(self, pid: int):
        if self.__scene_ctrl:
            self.__scene_ctrl.set_current_partition(pid if pid > 0 else None)

    @Slot(result='QVariantList')
    def getPartitions(self) -> list:
        if not self.__scene_ctrl:
            return []
        current = self.__scene_ctrl.get_current_partition_id()
        result = []
        for p in self.__scene_ctrl.get_partitions():
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
        data = vol_mesh.data
        return len(data.get_tetrahedra() or []) > 0 and len(data.get_triangles() or []) > 0

    def __collect_bc_groups(self, n_triangles: int) -> list[tuple[str, list[int]]]:
        """Map the current partitions to triangle groups via the FaceSelectionActor's
        PartitionIds cell array (the source of truth for who owns what). Every
        triangle must end up in some group, otherwise the exported surface has
        holes; unassigned triangles go into a "default" group."""
        part_ids = self.__scene_ctrl.get_partition_ids_per_cell() if self.__scene_ctrl else None
        if part_ids is None:
            return [("default", list(range(n_triangles)))]
        if part_ids.shape[0] != n_triangles:
            raise ValueError(f"surface has {part_ids.shape[0]} triangles but the volume mesh "
                             f"boundary has {n_triangles}; they must be the same surface")

        groups = []
        assigned = np.zeros(n_triangles, dtype=bool)
        for p in self.__scene_ctrl.get_partitions():
            indices = np.where(part_ids == p.id)[0]
            if indices.size:
                groups.append((p.name, indices.tolist()))
                assigned[indices] = True
        unassigned = np.where(~assigned)[0]
        if unassigned.size:
            groups.append(("default", unassigned.tolist()))
        return groups

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
        named = [g for g in groups if g[0] != "default"]
        unassigned = sum(len(g[1]) for g in groups if g[0] == "default")
        return {"boundaries": len(named), "unassigned": unassigned,
                "tets": len(data.get_tetrahedra())}

    @Slot(str, result=str)
    def exportVolume(self, file_path: str) -> str:
        """Write the volume mesh incl. boundary-condition labels as Netgen .vol.
        Returns "" on success, otherwise an error message for the UI."""
        # QML passes a QUrl-like string (e.g. "file:///...") from the FileDialog
        if file_path.startswith('file:'):
            file_path = QUrl(file_path).toLocalFile()
        if not file_path.endswith('.vol'):
            file_path += '.vol'
        if not self.canExportVolume():
            return "No volume mesh to export."

        data = self.__session.volume.data
        try:
            groups = self.__collect_bc_groups(len(data.get_triangles()))
            write_vol(file_path, data.get_vertices(), data.get_tetrahedra(),
                      data.get_triangles(), groups)
        except Exception as e:
            print(f"exportVolume failed: {e}")
            return str(e)
        print(f"Exported {file_path}: " + ", ".join(f"{n} ({len(i)})" for n, i in groups))
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
