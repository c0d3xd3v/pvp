import vtk
import numpy as np
from vtkmodules.util import numpy_support

from PySide6.QtCore import Slot
from PySide6.QtCore import QUrl
from PySide6.QtCore import Signal
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine

from FileIOCtrl import FileIOCtrl
from MeshCtrl import MeshCtrl
from SceneCtrl import SceneCtrl
from qml.vtk.VTKItem import VTKItem


class MainCtrl(QObject):
    meshLoaded = Signal()

    def __init__(self):
        super().__init__()
        self.__fileio_ctrl = FileIOCtrl()
        self.__mesh_ctrl = MeshCtrl()
        self.__scene_ctrl = SceneCtrl()

        self.__mesh_ctrl.update_partition.connect(self.__scene_ctrl.interactive_select)

    def get_scene_ctrl(self):
        return self.__scene_ctrl

    def set_cmd_args(self, args):
        if len(args) > 1:
            self.__fileio_ctrl.load_file(args[1])
            geometry = self.__fileio_ctrl.get_geometry()
            polydata = self.__scene_ctrl.add_surface_geometry(geometry.get_vertices(), geometry.get_triangles())
            self.__mesh_ctrl.load_geometry(polydata)

    def setupInternal(self, engine: QQmlApplicationEngine, item : VTKItem):
        self.__scene_ctrl.set_vtk_item(item)
        ctxt = engine.rootContext()
        ctxt.setContextProperty("MainCtrl", self)
        ctxt.setContextProperty("SceneCtrl", self.__scene_ctrl)
        ctxt.setContextProperty("MeshCtrl", self.__mesh_ctrl)
        item.mouse_interactor.qt_signals.cell_picked.connect(self.__mesh_ctrl.face_selected)

    @Slot(str)
    def loadMesh(self, file_path):
        file_path = QUrl(file_path).toLocalFile()
        self.__fileio_ctrl.load_file(file_path)
        geometry = self.__fileio_ctrl.get_geometry()
        polydata = self.__scene_ctrl.add_surface_geometry(geometry.get_vertices(), geometry.get_triangles())
        self.__mesh_ctrl.load_geometry(polydata)
        self.meshLoaded.emit()
