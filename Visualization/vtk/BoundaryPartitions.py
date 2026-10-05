import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy

from geometry.Partition import Partition


UNASSIGNED = 0
_UNASSIGNED_COLOR = (0.7, 0.7, 0.7)
# Tab10-ish palette. Wraps around for many partitions.
_PALETTE = [
    (0.12, 0.47, 0.71), (1.00, 0.50, 0.05), (0.17, 0.63, 0.17),
    (0.84, 0.15, 0.16), (0.58, 0.40, 0.74), (0.55, 0.34, 0.29),
    (0.89, 0.47, 0.76), (0.50, 0.50, 0.50), (0.74, 0.74, 0.13),
    (0.09, 0.75, 0.81),
]


class BoundaryPartitions:
    """The boundary-condition partitions of the surface mesh.

    Which face belongs to which partition is stored on the FaceSelectionActor
    (cell array "PartitionIds", 0 = unassigned) — that array is the single
    source of truth; this class keeps names/colors and the current selection
    and keeps the actor's colors in sync.
    """

    def __init__(self, request_render=lambda: None):
        self.__actor = None
        self.__partitions: dict[int, Partition] = {}
        self.__current_id: int | None = None
        self.__next_id = 1
        self.__request_render = request_render
        self.on_changed = None   # called after any change of names/colors/selection

    def attach(self, actor):
        """Start over on a new surface actor (all faces unassigned)."""
        self.__actor = actor
        self.__partitions.clear()
        self.__current_id = None
        self.__next_id = 1
        self.__sync_colors()
        self.__notify()

    def detach(self):
        self.__actor = None

    def add(self, name: str) -> int:
        pid = self.__next_id
        self.__next_id += 1
        color = _PALETTE[(pid - 1) % len(_PALETTE)]
        self.__partitions[pid] = Partition(id=pid, name=name, color=color)
        self.__sync_colors()
        self.__notify()
        return pid

    def delete(self, pid: int):
        if pid not in self.__partitions:
            return
        ids = self.ids_per_cell()
        if ids is not None:
            cells = np.where(ids == pid)[0].tolist()
            if cells:
                self.__actor.updatePartitions(cells, UNASSIGNED)
        del self.__partitions[pid]
        if self.__current_id == pid:
            self.__current_id = None
        self.__sync_colors()
        self.__notify()
        self.__request_render()

    def set_current(self, pid: int | None):
        self.__current_id = pid if pid in self.__partitions else None
        self.__notify()

    def current_id(self) -> int | None:
        return self.__current_id

    def all(self) -> list[Partition]:
        return sorted(self.__partitions.values(), key=lambda p: p.id)

    def assign_faces(self, face_ids, pid: int):
        """Assign cells (indices into the surface triangles) to a partition."""
        if self.__actor is None or pid not in self.__partitions or len(face_ids) == 0:
            return
        self.__actor.updatePartitions(face_ids, pid)
        self.__request_render()

    def ids_per_cell(self):
        """Partition id per surface triangle (copy), or None without a surface."""
        if self.__actor is None or self.__actor.full_polydata is None:
            return None
        arr = self.__actor.full_polydata.GetCellData().GetArray("PartitionIds")
        return None if arr is None else vtk_to_numpy(arr).copy()

    def __sync_colors(self):
        if self.__actor is None:
            return
        colors = {UNASSIGNED: _UNASSIGNED_COLOR}
        colors.update({pid: p.color for pid, p in self.__partitions.items()})
        self.__actor.set_partition_colors(colors)

    def __notify(self):
        if self.on_changed is not None:
            self.on_changed()
