from pathlib import Path

from PySide6.QtCore import Slot, Signal, QObject

from FileIOCtrl import FileIOCtrl
from PreProcSession import PreProcSession, PreProcMesh
from geometry.MeshRole import MeshRole
from geometry.AbstractMeshData import AbstractGeometryData


class PreProcCtrl(QObject):
    sessionChanged = Signal()

    def __init__(self):
        super().__init__()
        self.__session = PreProcSession()
        self.__fileio_ctrl = FileIOCtrl()
        self.__scene_ctrl = None
        self.__selection_ctrl = None

    def set_controllers(self, scene_ctrl, selection_ctrl):
        self.__scene_ctrl = scene_ctrl
        self.__selection_ctrl = selection_ctrl

    def get_session(self) -> PreProcSession:
        return self.__session

    @Slot(str)
    def loadSurface(self, file_path: str):
        self.__fileio_ctrl.load_file(file_path)
        data = self.__fileio_ctrl.get_geometry()
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
