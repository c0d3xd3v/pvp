"""Boundary-condition partitions of the surface: which triangle belongs to
which named partition, plus the current partition and undo/redo. Pure data,
no Qt/VTK; the scene shows it through PartitionView."""
from dataclasses import dataclass, replace
from typing import Callable

import numpy as np

UNASSIGNED = 0
UNASSIGNED_COLOR = (0.7, 0.7, 0.7)
# Tab10-ish palette. Wraps around for many partitions.
_PALETTE = [
    (0.12, 0.47, 0.71), (1.00, 0.50, 0.05), (0.17, 0.63, 0.17),
    (0.84, 0.15, 0.16), (0.58, 0.40, 0.74), (0.55, 0.34, 0.29),
    (0.89, 0.47, 0.76), (0.50, 0.50, 0.50), (0.74, 0.74, 0.13),
    (0.09, 0.75, 0.81),
]


@dataclass
class Partition:
    id: int
    name: str
    color: tuple[float, float, float]


class Partitions:
    """`ids` holds one partition id per surface triangle (0 = unassigned), or
    is None while there is no surface.

    Listeners are called after every change as fn(ids_changed, list_changed):
    ids_changed when triangle assignments may have changed, list_changed
    when the partitions themselves (names, colors) or the current one did.
    """

    _UNDO_LIMIT = 50

    def __init__(self):
        self.__ids: np.ndarray | None = None
        self.__partitions: dict[int, Partition] = {}
        self.__current_id: int | None = None
        self.__next_id = 1
        self.__undo: list[tuple] = []
        self.__redo: list[tuple] = []
        self.__listeners: list[Callable[[bool, bool], None]] = []

    def subscribe(self, fn: Callable[[bool, bool], None]):
        self.__listeners.append(fn)

    def __notify(self, ids_changed: bool, list_changed: bool):
        for fn in self.__listeners:
            fn(ids_changed, list_changed)

    # --- state ---------------------------------------------------------------

    def reset(self, n_faces: int | None):
        """Start over on a new surface with n_faces triangles, all unassigned
        (None: no surface)."""
        self.__ids = None if n_faces is None else np.zeros(n_faces, dtype=np.int32)
        self.__partitions.clear()
        self.__current_id = None
        self.__next_id = 1
        self.__undo.clear()
        self.__redo.clear()
        self.__notify(True, True)

    def restore(self, partitions: list[Partition], ids_per_cell, next_id: int,
                current: int | None):
        """Take over a saved state 1:1 (ids, names, colors); clears undo/redo."""
        self.__apply((np.asarray(ids_per_cell, dtype=np.int32).copy(),
                      {p.id: replace(p) for p in partitions}, next_id, current))
        self.__undo.clear()
        self.__redo.clear()

    def ids_per_cell(self) -> np.ndarray | None:
        """Partition id per surface triangle (copy), or None without a surface."""
        return None if self.__ids is None else self.__ids.copy()

    def current_id(self) -> int | None:
        return self.__current_id

    def next_id(self) -> int:
        return self.__next_id

    def all(self) -> list[Partition]:
        return sorted(self.__partitions.values(), key=lambda p: p.id)

    def colors(self) -> dict[int, tuple]:
        """Color per partition id, including UNASSIGNED."""
        return {UNASSIGNED: UNASSIGNED_COLOR, **{pid: p.color for pid, p in self.__partitions.items()}}

    # --- undo / redo ---------------------------------------------------------
    # Snapshots of the whole state: one int per triangle, cheap enough for the
    # mesh sizes we handle, and immune to subtle inverse-operation bugs.

    def __snapshot(self) -> tuple:
        return (self.ids_per_cell(), {pid: replace(p) for pid, p in self.__partitions.items()},
                self.__next_id, self.__current_id)

    def __record(self):
        self.__undo.append(self.__snapshot())
        del self.__undo[:-self._UNDO_LIMIT]
        self.__redo.clear()

    def __apply(self, snap: tuple):
        ids, partitions, next_id, current = snap
        if ids is not None:
            self.__ids = ids
        self.__partitions = dict(partitions)
        self.__next_id = max([next_id, *(pid + 1 for pid in partitions)])
        self.__current_id = current if current in self.__partitions else None
        self.__notify(True, True)

    def undo(self) -> bool:
        if not self.__undo:
            return False
        self.__redo.append(self.__snapshot())
        self.__apply(self.__undo.pop())
        return True

    def redo(self) -> bool:
        if not self.__redo:
            return False
        self.__undo.append(self.__snapshot())
        self.__apply(self.__redo.pop())
        return True

    # --- edits ---------------------------------------------------------------

    def add(self, name: str, record: bool = True) -> int:
        if record:
            self.__record()
        pid = self.__next_id
        self.__next_id += 1
        self.__partitions[pid] = Partition(id=pid, name=name, color=_PALETTE[(pid - 1) % len(_PALETTE)])
        self.__notify(False, True)
        return pid

    def delete(self, pid: int, record: bool = True):
        """Remove a partition; its triangles become unassigned."""
        if pid not in self.__partitions:
            return
        if record:
            self.__record()
        if self.__ids is not None:
            self.__ids[self.__ids == pid] = UNASSIGNED
        del self.__partitions[pid]
        if self.__current_id == pid:
            self.__current_id = None
        self.__notify(True, True)

    def set_current(self, pid: int | None):
        self.__current_id = pid if pid in self.__partitions else None
        self.__notify(False, True)

    def assign_faces(self, face_ids, pid: int, record: bool = True):
        """Assign triangles (indices into the surface) to a partition."""
        if pid in self.__partitions:
            self.__set_faces(face_ids, pid, record)

    def clear_faces(self, face_ids, record: bool = True):
        """Reset triangles to unassigned, whichever partition they belong to."""
        self.__set_faces(face_ids, UNASSIGNED, record)

    def __set_faces(self, face_ids, pid: int, record: bool):
        faces = np.asarray(face_ids, dtype=np.int64)
        if self.__ids is None or faces.size == 0 or np.all(self.__ids[faces] == pid):
            return      # nothing changes: no redraw, no empty undo step
        if record:
            self.__record()
        self.__ids[faces] = pid
        self.__notify(True, False)
