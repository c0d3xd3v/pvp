"""Face regions used by click/hover selection (TriangleMeshGraph.region)."""
import numpy as np
import pytest

from pvp.geometry.TriangleMeshGraph import TriangleMeshGraph


@pytest.fixture
def cube(unit_cube):
    P, _, F = unit_cube
    return TriangleMeshGraph(P, F), P, F


def _side(P, tri):
    """(axis, 0|1) of the cube side a boundary triangle lies on."""
    c = P[tri]
    for axis in range(3):
        if np.allclose(c[:, axis], c[0, axis]):
            return axis, int(round(c[0, axis]))
    raise AssertionError("triangle not on a cube side")


def test_regions_are_the_six_sides(cube):
    g, P, F = cube
    g.set_normal_compare_angle(10.0)
    sides = [_side(P, t) for t in F]
    regions = {g.region_label(f) for f in range(len(F))}
    assert len(regions) == 6
    for f in range(len(F)):
        expected = sorted(i for i, s in enumerate(sides) if s == sides[f])
        assert sorted(g.region(f).tolist()) == expected


def test_large_angle_joins_everything_and_angle_change_recomputes(cube):
    g, _, F = cube
    g.set_normal_compare_angle(100.0)
    assert len(g.region(0)) == len(F)
    g.set_normal_compare_angle(10.0)
    assert len(g.region(0)) < len(F)


def _flood_fill(F, normals, start, angle):
    """Reference: breadth-first search across shared edges with similar normals."""
    from collections import defaultdict, deque
    by_edge = defaultdict(list)
    for f, tri in enumerate(F):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            by_edge[tuple(sorted((tri[a], tri[b])))].append(f)
    neighbours = defaultdict(set)
    for faces in by_edge.values():
        for f in faces:
            neighbours[f].update(g for g in faces if g != f)
    cos = np.cos(np.radians(angle))
    seen, queue = {start}, deque([start])
    while queue:
        f = queue.popleft()
        for g in neighbours[f]:
            if g not in seen and normals[f] @ normals[g] > cos:
                seen.add(g)
                queue.append(g)
    return sorted(seen)


def test_matches_flood_fill_on_clean_mesh(cube):
    g, P, F = cube
    g.set_normal_compare_angle(10.0)
    n = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    for f in range(len(F)):
        assert _flood_fill(F, n, f, 10.0) == sorted(g.region(f).tolist())


def test_non_manifold_edge_connects_all_its_faces():
    # three fins sharing the edge (0, 1)
    V = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0], [0.5, -1, 0], [0.5, 0, 1]], dtype=float)
    F = np.array([[0, 1, 2], [1, 0, 3], [0, 1, 4]])
    g = TriangleMeshGraph(V, F, angle=180.0)
    assert sorted(g.region(0).tolist()) == [0, 1, 2]
