from PySide6.QtCore import Slot
from PySide6.QtCore import QObject

from pvp.geometry.TriangleMeshGraph import TriangleMeshGraph
from pvp.model.project import Project


class SelectionCtrl(QObject):
    """Turns clicks/hovers on surface cells into face regions: a left click
    paints the region into the current partition, a right click clears it,
    hovering previews it."""

    def __init__(self, project: Project, scene_ctrl):
        super().__init__()
        self.__project = project
        self.__scene_ctrl = scene_ctrl
        self.__graph = None
        self.__picking_enabled = True
        self.__hover_cell = -1
        self.__hover_label = -1

    def set_picking_enabled(self, enabled: bool):
        self.__picking_enabled = enabled
        if not enabled:
            self.__forget_hover()
            self.__scene_ctrl.clear_preview()

    def load_geometry(self, vertices, triangles):
        self.__graph = TriangleMeshGraph(vertices, triangles, self.__project.normal_angle)
        self.__forget_hover()

    @Slot(float)
    def set_normal_compare_angle(self, angle):
        self.__project.normal_angle = float(angle)
        if self.__graph is not None:
            self.__graph.set_normal_compare_angle(self.__project.normal_angle)
        self.__forget_hover()   # the region under the cursor depends on the angle

    def __forget_hover(self):
        self.__hover_cell = -1
        self.__hover_label = -1

    @Slot(result=float)
    def getNormalCompareAngle(self) -> float:
        return self.__project.normal_angle

    def __active(self) -> bool:
        return self.__picking_enabled and self.__graph is not None

    def face_selected(self, face_id):
        pid = self.__project.partitions.current_id()
        if self.__active() and pid is not None:
            self.__project.partitions.assign_faces(self.__graph.region(face_id), pid)

    def face_deselected(self, face_id):
        """Right-click: clear the picked region from whatever partition it
        currently belongs to. Independent of which partition is selected."""
        if self.__active():
            self.__project.partitions.clear_faces(self.__graph.region(face_id))

    def face_hovered(self, face_id):
        """Cursor moved onto another surface cell (-1: left the surface).
        Previews the same region a click would paint."""
        if face_id == self.__hover_cell:
            return
        self.__hover_cell = face_id
        if face_id < 0 or not self.__active():
            self.__hover_label = -1
            self.__scene_ctrl.clear_preview()
            return
        label = self.__graph.region_label(face_id)
        if label == self.__hover_label:
            return
        self.__hover_label = label
        self.__scene_ctrl.preview_faces(self.__graph.region(face_id))
