from pathlib import Path

from PySide6.QtCore import Slot, Signal, QObject

from FileIOCtrl import FileIOCtrl
from PreProcSession import PreProcSession, PreProcMesh
from geometry.MeshRole import MeshRole
from geometry.AbstractMeshData import AbstractGeometryData


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
        self.__session.set(PreProcMesh(
            role=MeshRole.VOLUME,
            data=data,
            name=Path(file_path).name
        ))
        if self.__scene_ctrl:
            if hasattr(data, 'get_tetrahedra') and data.get_tetrahedra():
                self.__scene_ctrl.add_volume_unstructured_mesh(
                    data.get_vertices(), data.get_tetrahedra()
                )
            else:
                self.__scene_ctrl.add_volume_geometry(
                    data.get_vertices(), data.get_triangles()
                )
        self.sessionChanged.emit()

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
