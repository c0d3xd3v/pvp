
from PySide6.QtCore import Signal
from PySide6.QtCore import QObject

from geometry.TriangleMeshGraph import TriangleMeshGraph


class SelectionCtrl(QObject):
    update_partition = Signal(list, int)

    def __init__(self):
        super().__init__()
        self.__surfaceTriangleMeshGraph = None
        self.__picking_enabled = True
        self.__scene_ctrl = None

    def set_scene_ctrl(self, scene_ctrl):
        self.__scene_ctrl = scene_ctrl

    def set_picking_enabled(self, enabled: bool):
        self.__picking_enabled = enabled

    def load_geometry(self, polydata):
        self.__surfaceTriangleMeshGraph = None
        self.__surfaceTriangleMeshGraph = TriangleMeshGraph(polydata)
        self.set_normal_compare_angle(10.0)

    def set_normal_compare_angle(self, angle):
        if self.__surfaceTriangleMeshGraph is not None:
            self.__surfaceTriangleMeshGraph.set_normal_compare_angle(angle)

    def face_selected(self, face_id):
        if not self.__picking_enabled:
            return
        pid = self.__scene_ctrl.partitions.current_id() if self.__scene_ctrl else None
        if pid is None:
            return
        self.__surfaceTriangleMeshGraph.reset()
        flat_faces = self.__surfaceTriangleMeshGraph.BFS(face_id)
        self.update_partition.emit(flat_faces, pid)
