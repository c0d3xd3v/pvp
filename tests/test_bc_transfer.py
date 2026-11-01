"""Carry boundary partitions from the input surface onto the tet-mesher
boundary: every new triangle maps to the closest input triangle."""
import numpy as np

from pvp.model.mesh import Mesh
from pvp.model.project import Project
from pvp.services.boundary_transfer import closest_cells
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


def test_closest_cells_maps_children_to_their_parent():
    new_V, new_F = _subdivided_square()
    assert list(closest_cells(*_two_triangle_square(), new_V, new_F)) == [0] * 4 + [1] * 4


def test_mesh_result_carries_partitions_over():
    p = Project()
    p.start("before", Mesh(*_two_triangle_square()))
    inlet, wall = p.partitions.add("inlet"), p.partitions.add("wall")
    p.partitions.assign_faces([0], inlet)
    p.partitions.assign_faces([1], wall)
    new_V, new_F = _subdivided_square()
    take_mesh_result(p, new_V, new_F, np.zeros((0, 4)))

    assert list(p.partitions.ids_per_cell()) == [inlet, wall]   # input untouched
    assert list(p.volume_partition_ids()) == [inlet] * 4 + [wall] * 4
    # later edits on the input reach the volume too
    p.partitions.assign_faces([1], inlet)
    assert list(p.volume_partition_ids()) == [inlet] * 8


def test_no_partitions():
    p = Project()
    p.start("before", Mesh(*_two_triangle_square()))
    take_mesh_result(p, *_subdivided_square(), np.zeros((0, 4)))
    assert not np.any(p.volume_partition_ids())
