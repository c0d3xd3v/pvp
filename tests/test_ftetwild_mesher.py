"""Needs the compiled pyFloatTetwildWrapper module (pip install -e .)."""
import numpy as np
import pytest

pytest.importorskip("pyFloatTetwildWrapper")
from meshing.FTetWildMesher import FTetWildMesher   # noqa: E402


def test_parameters_reach_ftetwild(unit_cube):
    P, T, F = unit_cube
    coarse = FTetWildMesher().mesh(P, F, {"ideal_edge_length_rel": 0.3})
    fine = FTetWildMesher().mesh(P, F, {"ideal_edge_length_rel": 0.05})
    assert len(fine.tetrahedra) > 2 * len(coarse.tetrahedra)


def test_result_is_in_input_coordinates(unit_cube):
    P, T, F = unit_cube
    r = FTetWildMesher().mesh(P, F, {})
    assert r.vertices.min(axis=0) == pytest.approx([0, 0, 0], abs=1e-3)
    assert r.vertices.max(axis=0) == pytest.approx([1, 1, 1], abs=1e-3)
    assert r.triangles.shape[1] == 3 and r.tetrahedra.shape[1] == 4
