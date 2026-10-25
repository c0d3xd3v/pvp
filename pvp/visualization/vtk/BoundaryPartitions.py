from dataclasses import replace

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy

from pvp.geometry.Partition import Partition
from pvp.visualization.vtk.scene_lock import scene_locked


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

    def __init__(self, request_render=lambda: None, set_hover_enabled=lambda _enabled: None):
        self.__actor = None
        self.__partitions: dict[int, Partition] = {}
        self.__current_id: int | None = None
        self.__next_id = 1
        self.__request_render = request_render
        # hover preview only makes sense while a partition is current
        self.__set_hover_enabled = set_hover_enabled
        self.on_changed = None   # called after any change of names/colors/selection
        self.__undo: list[tuple] = []
        self.__redo: list[tuple] = []

    @scene_locked
    def attach(self, actor):
        """Start over on a new surface actor (all faces unassigned)."""
        self.__actor = actor
        self.__partitions.clear()
        self.__current_id = None
        self.__next_id = 1
        self.__undo.clear()
        self.__redo.clear()
        self.__sync_colors()
        self.__set_hover_enabled(False)
        self.__notify()

    @scene_locked
    def detach(self):
        self.__actor = None
        self.__set_hover_enabled(False)

    @scene_locked
    def restore(self, partitions: list[Partition], ids_per_cell, next_id: int,
                current: int | None):
        """Take over a saved state 1:1 (ids, names, colors); clears undo/redo."""
        self.__apply((np.asarray(ids_per_cell, dtype=np.int32).copy(),
                      {p.id: replace(p) for p in partitions}, next_id, current))
        self.__undo.clear()
        self.__redo.clear()

    # --- undo / redo ---------------------------------------------------------
    # Snapshots of the whole state: one int per triangle, cheap enough for the
    # mesh sizes we handle, and immune to subtle inverse-operation bugs.
    _UNDO_LIMIT = 50

    def __snapshot(self) -> tuple:
        return (self.ids_per_cell(), {pid: replace(p) for pid, p in self.__partitions.items()},
                self.__next_id, self.__current_id)

    def __record(self):
        self.__undo.append(self.__snapshot())
        del self.__undo[:-self._UNDO_LIMIT]
        self.__redo.clear()

    def __apply(self, snap: tuple):
        ids, partitions, next_id, current = snap
        self.__partitions = dict(partitions)
        self.__next_id = max([next_id, *(pid + 1 for pid in partitions)])
        if self.__actor is not None and ids is not None:
            self.__actor.set_partition_ids(ids)
        self.__sync_colors()
        self.set_current(current)    # also hover state + preview tint, notifies
        self.__request_render()

    @scene_locked
    def undo(self) -> bool:
        if not self.__undo:
            return False
        self.__redo.append(self.__snapshot())
        self.__apply(self.__undo.pop())
        return True

    @scene_locked
    def redo(self) -> bool:
        if not self.__redo:
            return False
        self.__undo.append(self.__snapshot())
        self.__apply(self.__redo.pop())
        return True

    # --- edits ---------------------------------------------------------------

    @scene_locked
    def add(self, name: str, record: bool = True) -> int:
        if record:
            self.__record()
        pid = self.__next_id
        self.__next_id += 1
        color = _PALETTE[(pid - 1) % len(_PALETTE)]
        self.__partitions[pid] = Partition(id=pid, name=name, color=color)
        self.__sync_colors()
        self.__notify()
        return pid

    @scene_locked
    def delete(self, pid: int, record: bool = True):
        if pid not in self.__partitions:
            return
        if record:
            self.__record()
        ids = self.ids_per_cell()
        if ids is not None:
            cells = np.where(ids == pid)[0].tolist()
            if cells:
                self.__actor.updatePartitions(cells, UNASSIGNED)
        del self.__partitions[pid]
        if self.__current_id == pid:
            self.__current_id = None
            self.__set_hover_enabled(False)
            self.clear_preview()
        self.__sync_colors()
        self.__notify()
        self.__request_render()

    @scene_locked
    def set_current(self, pid: int | None):
        self.__current_id = pid if pid in self.__partitions else None
        self.__set_hover_enabled(self.__current_id is not None)
        if self.__current_id is None:
            self.clear_preview()
        elif self.__actor is not None:
            self.__actor.set_preview_color(self._preview_color())
            self.__request_render()
        self.__notify()

    def current_id(self) -> int | None:
        return self.__current_id

    def next_id(self) -> int:
        return self.__next_id

    def all(self) -> list[Partition]:
        return sorted(self.__partitions.values(), key=lambda p: p.id)

    @scene_locked
    def assign_faces(self, face_ids, pid: int, record: bool = True):
        """Assign cells (indices into the surface triangles) to a partition."""
        if self.__actor is None or pid not in self.__partitions:
            return
        self.__set_faces(face_ids, pid, record)

    @scene_locked
    def clear_faces(self, face_ids, record: bool = True):
        """Reset the given cells back to unassigned, regardless of which
        partition they currently belong to."""
        if self.__actor is None:
            return
        self.__set_faces(face_ids, UNASSIGNED, record)

    def __set_faces(self, face_ids, pid: int, record: bool):
        faces = np.asarray(face_ids, dtype=np.int64)
        ids = self.ids_per_cell()
        if faces.size == 0 or ids is None or np.all(ids[faces] == pid):
            return      # nothing changes: no redraw, no empty undo step
        if record:
            self.__record()
        self.__actor.updatePartitions(faces, pid)
        self.__request_render()

    @scene_locked
    def preview_faces(self, face_ids):
        """Hover preview: highlight the region a click would paint, tinted
        with the current partition's color."""
        if self.__actor is None or len(face_ids) == 0:
            self.clear_preview()
            return
        self.__actor.set_preview(face_ids, self._preview_color())
        self.__request_render()

    @scene_locked
    def clear_preview(self):
        if self.__actor is None:
            return
        self.__actor.clear_preview()
        self.__request_render()

    def _preview_color(self):
        if self.__current_id is None or self.__current_id not in self.__partitions:
            return (1.0, 1.0, 1.0)
        r, g, b = self.__partitions[self.__current_id].color
        mix = 0.55   # blend toward white so it stands out on a face already in that color
        return (r + (1.0 - r) * mix,
                g + (1.0 - g) * mix,
                b + (1.0 - b) * mix)

    @scene_locked
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
