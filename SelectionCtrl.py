import numpy as np

from PySide6.QtCore import Slot
from PySide6.QtCore import Signal
from PySide6.QtCore import QObject

from geometry.TriangleMeshGraph import TriangleMeshGraph


class SelectionCtrl(QObject):
    update_partition = Signal(list, int)
    mesh_geometry_modified = Signal()

    def __init__(self):
        super().__init__()
        self.__surfaceTriangleMeshGraph = None
        self.__picking_enabled = True

    def set_picking_enabled(self, enabled: bool):
        self.__picking_enabled = enabled

    def load_geometry(self, polydata):
        self.__surfaceTriangleMeshGraph = None
        self.__surfaceTriangleMeshGraph = TriangleMeshGraph(polydata)
        self.set_normal_compare_angle(10.0)

    def set_normal_compare_angle(self, angle):
        if self.__surfaceTriangleMeshGraph is not None:
            self.__surfaceTriangleMeshGraph.set_normal_compare_angle(angle)

    @Slot()
    def center_to_geometric_center(self):
        gc = self.__surfaceTriangleMeshGraph.compute_geometric_center()
        self.__surfaceTriangleMeshGraph.translate_mesh(np.array([gc]))
        self.mesh_geometry_modified.emit()

    def face_selected(self, face_id):
        if not self.__picking_enabled:
            return
        self.__surfaceTriangleMeshGraph.reset()
        flat_faces = self.__surfaceTriangleMeshGraph.BFS(face_id)
        self.update_partition.emit(flat_faces, 0)
