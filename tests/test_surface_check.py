import numpy as np

from pvp.geometry.surface_check import surface_stats

TETRA_V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
TETRA_F = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]])


def test_closed_tetrahedron():
    s = surface_stats(TETRA_V, TETRA_F)
    assert (s.vertices, s.triangles, s.open_edges, s.nonmanifold_edges) == (4, 4, 0, 0)
    assert s.closed


def test_open_and_nonmanifold():
    s = surface_stats(TETRA_V, TETRA_F[:3])
    assert s.open_edges == 3 and not s.closed
    # a fifth triangle on edge (0, 1) makes it non-manifold
    V = np.vstack((TETRA_V, [[0, -1, 0]]))
    s = surface_stats(V, np.vstack((TETRA_F, [[0, 1, 4]])))
    assert s.nonmanifold_edges == 1 and not s.closed


def test_empty():
    assert not surface_stats(np.zeros((0, 3)), np.zeros((0, 3), dtype=int)).closed


def test_components_sorted_by_size_with_stats():
    from pvp.geometry.surface_check import component_labels, component_stats
    F = np.vstack((TETRA_F[:3] + 4, TETRA_F + 8, TETRA_F, [[12, 13, 14], [12, 14, 15]]))
    labels = component_labels(F)
    # two closed tets (4 tris, first-seen first), open tet (3), quad (2)
    assert list(labels) == [2] * 3 + [0] * 4 + [1] * 4 + [3] * 2
    stats = component_stats(F, labels)
    assert [(s.triangles, s.closed) for s in stats] == [(4, True), (4, True), (3, False), (2, False)]
    assert stats[2].open_edges == 3 and stats[3].open_edges == 4 and stats[3].vertices == 4
