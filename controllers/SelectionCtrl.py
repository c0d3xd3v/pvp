
from PySide6.QtCore import Signal, Slot
from PySide6.QtCore import QObject

from geometry.TriangleMeshGraph import TriangleMeshGraph


class SelectionCtrl(QObject):
    update_partition = Signal(list, int)
    clear_partition = Signal(list)

    _DEFAULT_NORMAL_ANGLE = 10.0

    def __init__(self):
        super().__init__()
        self.__surfaceTriangleMeshGraph = None
        self.__picking_enabled = True
        self.__scene_ctrl = None
        self.__normal_angle = self._DEFAULT_NORMAL_ANGLE

    def set_scene_ctrl(self, scene_ctrl):
        self.__scene_ctrl = scene_ctrl

    def set_picking_enabled(self, enabled: bool):
        self.__picking_enabled = enabled

    def load_geometry(self, polydata):
        self.__surfaceTriangleMeshGraph = None
        self.__surfaceTriangleMeshGraph = TriangleMeshGraph(polydata)
        self.set_normal_compare_angle(self.__normal_angle)

    @Slot(float)
    def set_normal_compare_angle(self, angle):
        self.__normal_angle = float(angle)
        if self.__surfaceTriangleMeshGraph is not None:
            self.__surfaceTriangleMeshGraph.set_normal_compare_angle(self.__normal_angle)

    @Slot(result=float)
    def getNormalCompareAngle(self) -> float:
        return self.__normal_angle

    def face_selected(self, face_id):
        if not self.__picking_enabled:
            return
        pid = self.__scene_ctrl.partitions.current_id() if self.__scene_ctrl else None
        if pid is None:
            return
        self.__surfaceTriangleMeshGraph.reset()
        flat_faces = self.__surfaceTriangleMeshGraph.BFS(face_id)
        self.update_partition.emit(flat_faces, pid)

    def face_deselected(self, face_id):
        """Right-click flood-fill: clear the picked contiguous region from
        whatever partition it currently belongs to. Independent of which
        partition is selected — picking is enough to identify the region."""
        if not self.__picking_enabled or self.__surfaceTriangleMeshGraph is None:
            return
        self.__surfaceTriangleMeshGraph.reset()
        flat_faces = self.__surfaceTriangleMeshGraph.BFS(face_id)
        self.clear_partition.emit(flat_faces)
