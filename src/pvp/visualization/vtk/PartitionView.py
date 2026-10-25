from pvp.model.partitions import Partitions
from pvp.visualization.vtk.scene_lock import scene_locked


class PartitionView:
    """Shows a Partitions model on the surface's FaceSelectionActor: colors
    per triangle, and the hover preview tinted with the current partition's
    color. Holds no state of its own besides the actor."""

    def __init__(self, partitions: Partitions, request_render=lambda: None,
                 set_hover_enabled=lambda _enabled: None):
        self.__model = partitions
        self.__actor = None
        self.__request_render = request_render
        # hover preview only makes sense while a partition is current
        self.__set_hover_enabled = set_hover_enabled
        partitions.subscribe(self.__on_model_changed)

    @scene_locked
    def attach(self, actor):
        self.__actor = actor
        self.__on_model_changed(True, True)

    @scene_locked
    def detach(self):
        self.__actor = None
        self.__set_hover_enabled(False)

    @scene_locked
    def __on_model_changed(self, ids_changed: bool, _list_changed: bool):
        current = self.__model.current_id()
        self.__set_hover_enabled(self.__actor is not None and current is not None)
        if self.__actor is None:
            return
        ids = self.__model.ids_per_cell()
        if ids_changed and ids is not None and len(ids) == self.__actor.full_polydata.GetNumberOfCells():
            self.__actor.set_partition_ids(ids)
        self.__actor.set_partition_colors(self.__model.colors())
        if current is None:
            self.__actor.clear_preview()
        else:
            self.__actor.set_preview_color(self.__preview_color())
        self.__request_render()

    @scene_locked
    def preview_faces(self, face_ids):
        """Hover preview: highlight the region a click would paint."""
        if self.__actor is None or len(face_ids) == 0:
            self.clear_preview()
            return
        self.__actor.set_preview(face_ids, self.__preview_color())
        self.__request_render()

    @scene_locked
    def clear_preview(self):
        if self.__actor is None:
            return
        self.__actor.clear_preview()
        self.__request_render()

    def __preview_color(self):
        color = self.__model.colors().get(self.__model.current_id())
        if self.__model.current_id() is None or color is None:
            return (1.0, 1.0, 1.0)
        mix = 0.55   # blend toward white so it stands out on a face already in that color
        return tuple(c + (1.0 - c) * mix for c in color)
