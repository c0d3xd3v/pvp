"""PreProcCtrl: carry boundary assignments across the tet-mesher step.

The core guarantee tested here: after `replace_project_with_mesh` with a
`bc_transfer` snapshot of a pre-meshing surface, every new-surface triangle
is assigned to the partition that owned the closest cell of the old
surface. Partitions are recreated with the original names.
"""
import numpy as np
import pytest

from controllers.PreProcCtrl import PreProcCtrl


class _FakePartitions:
    """Just enough of BoundaryPartitions for the transfer path:
    add(name)->new id, assign_faces(ids, pid), all(), ids_per_cell()."""

    def __init__(self):
        self._next = 1
        self._names: dict[int, str] = {}
        self._ids_per_cell: np.ndarray | None = None
        self.on_changed = None

    # BC-transfer path
    def add(self, name: str) -> int:
        pid = self._next
        self._next += 1
        self._names[pid] = name
        return pid

    def assign_faces(self, face_ids, pid: int):
        if self._ids_per_cell is None:
            return
        self._ids_per_cell[list(face_ids)] = pid

    # Introspection
    def all(self):
        from types import SimpleNamespace
        return [SimpleNamespace(id=pid, name=n) for pid, n in sorted(self._names.items())]

    def ids_per_cell(self):
        return self._ids_per_cell


class _FakeSceneCtrl:
    def __init__(self):
        self.partitions = _FakePartitions()

    def add_surface_geometry(self, vertices, triangles):
        self.partitions._ids_per_cell = np.zeros(len(triangles), dtype=np.int32)
        return None

    def add_volume_unstructured_mesh(self, *_): pass
    def reset_view_toggles(self): pass


def _two_triangle_square():
    """Unit square at z=0 split along the (0,0)-(1,1) diagonal."""
    V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float64)
    F = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    return V, F


def _subdivided_square():
    """Same unit square, each half-triangle split into four smaller ones by
    inserting edge midpoints. Centroids stay inside the parent triangle."""
    V = np.array([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],   # corners (0..3)
        [0.5, 0, 0], [1, 0.5, 0], [0.5, 0.5, 0],      # midpoints on tri 0  (4..6)
        [0.5, 1, 0], [0, 0.5, 0],                     # midpoints on tri 1  (7..8)
    ], dtype=np.float64)
    # tri 0 = (0,1,2) subdivided
    F0 = [(0, 4, 6), (4, 1, 5), (6, 5, 2), (4, 5, 6)]
    # tri 1 = (0, 2, 3) subdivided
    F1 = [(0, 6, 8), (6, 2, 7), (8, 7, 3), (6, 7, 8)]
    return V, np.array(F0 + F1, dtype=np.int64)


@pytest.fixture
def preproc_with_cube(unit_cube):
    P, T, F = unit_cube
    scene = _FakeSceneCtrl()
    c = PreProcCtrl()
    c.set_controllers(scene, None)
    c.replace_project_with_mesh(P, F, T, name="cube")
    return c, scene


def test_transfer_assigns_each_new_triangle_to_the_right_old_label():
    old_V, old_F = _two_triangle_square()
    new_V, new_F = _subdivided_square()

    scene = _FakeSceneCtrl()
    c = PreProcCtrl()
    c.set_controllers(scene, None)

    snap = {
        "vertices":     old_V,
        "triangles":    old_F,
        "ids_per_cell": np.array([1, 2], dtype=np.int32),   # tri0=inlet, tri1=wall
        "names":        {1: "inlet", 2: "wall"},
    }
    T = np.zeros((0, 4), dtype=np.int64)
    c.replace_project_with_mesh(new_V, new_F, T, name="meshed", bc_transfer=snap)

    assigned = scene.partitions.ids_per_cell()
    name_of = {p.id: p.name for p in scene.partitions.all()}

    # Partitions recreated by name (ids may differ from the old 1/2 pair).
    assert set(name_of.values()) == {"inlet", "wall"}
    inlet_id = next(pid for pid, n in name_of.items() if n == "inlet")
    wall_id  = next(pid for pid, n in name_of.items() if n == "wall")

    # First 4 new triangles came from tri0 (inlet), next 4 from tri1 (wall).
    assert list(assigned[:4]) == [inlet_id] * 4
    assert list(assigned[4:]) == [wall_id]  * 4


def test_snapshot_returns_none_when_nothing_is_assigned(preproc_with_cube):
    c, _ = preproc_with_cube
    assert c.snapshot_boundary_assignments() is None


def test_no_transfer_keeps_partitions_empty():
    old_V, old_F = _two_triangle_square()
    new_V, new_F = _subdivided_square()

    scene = _FakeSceneCtrl()
    c = PreProcCtrl()
    c.set_controllers(scene, None)

    c.replace_project_with_mesh(new_V, new_F, np.zeros((0, 4), dtype=np.int64),
                                name="meshed", bc_transfer=None)

    assert scene.partitions.all() == []
    assert np.all(scene.partitions.ids_per_cell() == 0)
