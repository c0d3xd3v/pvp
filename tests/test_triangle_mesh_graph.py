"""Face regions used by click/hover selection (TriangleMeshGraph.region)."""
import numpy as np
import pytest

from controllers.SceneCtrl import _triangle_polydata
from geometry.TriangleMeshGraph import TriangleMeshGraph


@pytest.fixture
def cube(unit_cube):
    P, _, F = unit_cube
    return TriangleMeshGraph(_triangle_polydata(P, F)), P, F


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


def test_matches_flood_fill_on_clean_mesh(cube):
    g, _, F = cube
    g.set_normal_compare_angle(10.0)
    for f in range(len(F)):
        g.reset()
        assert sorted(g.BFS(f)) == sorted(g.region(f).tolist())
