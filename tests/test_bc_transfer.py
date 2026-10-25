"""Carry boundary assignments across the tet-mesher step.

The core guarantee tested here: after take_mesh_result with a snapshot of
the pre-meshing surface, every new-surface triangle is assigned to the
partition that owned the closest cell of the old surface. Partitions are
recreated with the original names.
"""
import numpy as np

from pvp.model.mesh import Mesh
from pvp.model.project import Project
from pvp.services.boundary_transfer import closest_cell_ids, snapshot_boundaries
from pvp.services.project_ops import take_mesh_result


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


def _project_with(V, F, labels: dict[str, list[int]]) -> Project:
    p = Project()
    p.start("before", Mesh(vertices=V, triangles=F))
    for name, faces in labels.items():
        p.partitions.assign_faces(faces, p.partitions.add(name))
    return p


def test_closest_cell_ids_maps_children_to_their_parent():
    old_V, old_F = _two_triangle_square()
    new_V, new_F = _subdivided_square()
    ids = closest_cell_ids(old_V, old_F, np.array([5, 7]), new_V, new_F)
    assert list(ids) == [5] * 4 + [7] * 4


def test_transfer_assigns_each_new_triangle_to_the_right_old_label():
    p = _project_with(*_two_triangle_square(), {"inlet": [0], "wall": [1]})
    snap = snapshot_boundaries(p)
    new_V, new_F = _subdivided_square()
    take_mesh_result(p, new_V, new_F, np.zeros((0, 4)), "meshed", snap)

    assigned = p.partitions.ids_per_cell()
    name_of = {q.id: q.name for q in p.partitions.all()}
    assert sorted(name_of.values()) == ["inlet", "wall"]
    inlet_id = next(pid for pid, n in name_of.items() if n == "inlet")
    wall_id = next(pid for pid, n in name_of.items() if n == "wall")
    # First 4 new triangles came from tri0 (inlet), next 4 from tri1 (wall).
    assert list(assigned[:4]) == [inlet_id] * 4
    assert list(assigned[4:]) == [wall_id] * 4
    assert not p.partitions.undo()                 # the transfer is not an undo step


def test_snapshot_is_none_without_assignments(unit_cube):
    P, _, F = unit_cube
    assert snapshot_boundaries(Project()) is None
    assert snapshot_boundaries(_project_with(P, F, {})) is None
    assert snapshot_boundaries(_project_with(P, F, {"inlet": []})) is None


def test_no_transfer_keeps_partitions_empty():
    p = _project_with(*_two_triangle_square(), {"inlet": [0]})
    new_V, new_F = _subdivided_square()
    take_mesh_result(p, new_V, new_F, np.zeros((0, 4)), "meshed", None)
    assert p.partitions.all() == []
    assert not np.any(p.partitions.ids_per_cell())
