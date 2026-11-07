"""Needs the compiled pyFloatTetwildWrapper module (pip install -e .)."""
import numpy as np
import pytest

pytest.importorskip("pyFloatTetwildWrapper")
from pvp.meshing.FTetWildMesher import FTetWildMesher   # noqa: E402


def test_parameters_reach_ftetwild(unit_cube):
    P, T, F = unit_cube
    # Unit cube: bbox diagonal = sqrt(3). Edge lengths picked so fine << coarse
    # relative to that diagonal (the two values below match the former
    # 0.3 / 0.05 relative-to-bbox-diagonal defaults).
    import numpy as np
    bbox_diag = float(np.linalg.norm(P.max(axis=0) - P.min(axis=0)))
    coarse = FTetWildMesher().mesh(P, F, {"ideal_edge_length": 0.3 * bbox_diag})
    fine   = FTetWildMesher().mesh(P, F, {"ideal_edge_length": 0.05 * bbox_diag})
    assert len(fine.tetrahedra) > 2 * len(coarse.tetrahedra)


def test_result_is_in_input_coordinates(unit_cube):
    P, T, F = unit_cube
    r = FTetWildMesher().mesh(P, F, {})
    assert r.vertices.min(axis=0) == pytest.approx([0, 0, 0], abs=1e-3)
    assert r.vertices.max(axis=0) == pytest.approx([1, 1, 1], abs=1e-3)
    assert r.triangles.shape[1] == 3 and r.tetrahedra.shape[1] == 4


@pytest.fixture(scope="module")
def two_cube_surface(unit_cube):
    """Input surface of two unit cubes touching on z=1, one solid each."""
    P, T, F = unit_cube
    V = np.vstack([P, P + [0, 0, 1]])
    S = np.vstack([F, F + len(P)])
    return V, S, [(0, np.arange(len(F))), (1, np.arange(len(F), len(S)))]


def _volume(V, T):
    a, b, c, d = (V[T[:, i]] for i in range(4))
    return np.abs(np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a)).sum() / 6


@pytest.mark.parametrize("mode", ["conforming", "per_body"])
def test_touching_bodies_stay_apart(two_cube_surface, mode):
    from pvp.services import multibody
    V, S, bodies = two_cube_surface
    r, face_map, regions = multibody.mesh_bodies(
        FTetWildMesher(), V, S, bodies, {"ideal_edge_length": 0.3}, mode)
    X, T = r.vertices, r.tetrahedra
    for label in (0, 1):
        tets = T[regions == label]
        assert _volume(X, tets) == pytest.approx(1.0, rel=1e-3)
        z = X[tets][:, :, 2]
        assert (z.max() <= 1 + 1e-6) if label == 0 else (z.min() >= 1 - 1e-6)

    on_contact = np.abs(X[:, 2] - 1) < 1e-6
    used_by = [np.zeros(len(X), bool) for _ in (0, 1)]
    for label in (0, 1):
        used_by[label][T[regions == label].ravel()] = True
    shared = on_contact & used_by[0] & used_by[1]
    contact_tris = np.all(on_contact[r.triangles], axis=1)
    if mode == "conforming":
        assert shared.sum() > 4 and not contact_tris.any()   # interface is interior
    else:
        assert not shared.any() and contact_tris.any()       # duplicated, on the boundary
        # each contact face maps to the input triangles of its own body
        tri_label = multibody.boundary_regions(T, regions, r.triangles)
        assert np.array_equal(face_map >= len(bodies[0][1]), tri_label == 1)
