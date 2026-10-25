
from PySide6.QtCore import Signal, Slot
from PySide6.QtCore import QObject

from geometry.TriangleMeshGraph import TriangleMeshGraph


class SelectionCtrl(QObject):
    update_partition = Signal(list, int)
    clear_partition = Signal(list)
    preview_partition = Signal(list)
    clear_preview = Signal()

    _DEFAULT_NORMAL_ANGLE = 10.0

    def __init__(self):
        super().__init__()
        self.__surfaceTriangleMeshGraph = None
        self.__picking_enabled = True
        self.__scene_ctrl = None
        self.__normal_angle = self._DEFAULT_NORMAL_ANGLE
        self.__hover_cell = -1
        self.__hover_label = -1

    def set_scene_ctrl(self, scene_ctrl):
        self.__scene_ctrl = scene_ctrl

    def set_picking_enabled(self, enabled: bool):
        self.__picking_enabled = enabled
        if not enabled:
            self.__forget_hover()
            self.clear_preview.emit()

    def load_geometry(self, polydata):
        self.__surfaceTriangleMeshGraph = None
        self.__surfaceTriangleMeshGraph = TriangleMeshGraph(polydata)
        self.set_normal_compare_angle(self.__normal_angle)
        self.clear_preview.emit()

    @Slot(float)
    def set_normal_compare_angle(self, angle):
        self.__normal_angle = float(angle)
        if self.__surfaceTriangleMeshGraph is not None:
            self.__surfaceTriangleMeshGraph.set_normal_compare_angle(self.__normal_angle)
        self.__forget_hover()   # the region under the cursor depends on the angle

    def __forget_hover(self):
        self.__hover_cell = -1
        self.__hover_label = -1

    @Slot(result=float)
    def getNormalCompareAngle(self) -> float:
        return self.__normal_angle

    def face_selected(self, face_id):
        if not self.__picking_enabled:
            return
        pid = self.__scene_ctrl.partitions.current_id() if self.__scene_ctrl else None
        if pid is None or self.__surfaceTriangleMeshGraph is None:
            return
        self.update_partition.emit(self.__surfaceTriangleMeshGraph.region(face_id).tolist(), pid)

    def face_deselected(self, face_id):
        """Right-click: clear the picked region from whatever partition it
        currently belongs to. Independent of which partition is selected."""
        if not self.__picking_enabled or self.__surfaceTriangleMeshGraph is None:
            return
        self.clear_partition.emit(self.__surfaceTriangleMeshGraph.region(face_id).tolist())

    def face_hovered(self, face_id):
        """Cursor moved onto another surface cell (-1: left the surface).
        Previews the same region a click would paint."""
        if face_id == self.__hover_cell:
            return
        self.__hover_cell = face_id
        if (face_id < 0
                or not self.__picking_enabled
                or self.__surfaceTriangleMeshGraph is None):
            self.__hover_label = -1
            self.clear_preview.emit()
            return
        label = self.__surfaceTriangleMeshGraph.region_label(face_id)
        if label == self.__hover_label:
            return
        self.__hover_label = label
        self.preview_partition.emit(self.__surfaceTriangleMeshGraph.region(face_id).tolist())
