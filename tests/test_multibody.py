"""Meshing several bodies: labelling, concatenation, boundary transfer per body."""
import numpy as np
import pytest

from pvp.meshing.TetMesher import MeshingResult
from pvp.services import multibody


def _bodies(F):
    half = len(F) // 2
    return [(0, np.arange(half)), (1, np.arange(half, len(F)))]


def test_body_faces_only_checked_components():
    labels = np.array([0, 1, 1, 2, 0])
    got = multibody.body_faces(labels, [True, False, True])
    assert [c for c, _ in got] == [0, 2]
    assert got[0][1].tolist() == [0, 4] and got[1][1].tolist() == [3]


def test_concat_meshes_offsets_and_labels(two_cubes):
    V, T, F, regions = two_cubes
    n, nt, nf = len(V) // 2, len(T) // 2, len(F) // 2
    parts = [(3, V[:n], F[:nf], T[:nt]), (7, V[n:], F[nf:] - n, T[nt:] - n)]
    V2, F2, T2, r, tri_label = multibody.concat_meshes(parts)
    assert np.array_equal(V2, V) and np.array_equal(T2, T) and np.array_equal(F2, F)
    assert r.tolist() == [3] * nt + [7] * nt
    assert tri_label.tolist() == [3] * nf + [7] * nf


def test_winding_number_labels_each_tet_with_its_body(two_cubes):
    V, T, F, regions = two_cubes
    got = multibody.label_tets_by_winding(V, T, V, F, _bodies(F))
    assert np.array_equal(got, regions)


def test_boundary_regions(two_cubes):
    V, T, F, regions = two_cubes
    got = multibody.boundary_regions(T, regions, F)
    assert got.tolist() == [0] * (len(F) // 2) + [1] * (len(F) // 2)
    with pytest.raises(ValueError):
        multibody.boundary_regions(T, regions, np.array([[0, 1, len(V) - 1]]))


def test_contact_faces_take_the_partition_of_their_own_body(two_cubes):
    """The top of A and the bottom of B coincide: each must map to a triangle
    of its own body, which a plain closest search can't guarantee."""
    V, T, F, regions = two_cubes
    tri_label = multibody.boundary_regions(T, regions, F)
    face_map = multibody.face_map_per_body(V, F, _bodies(F), V, F, tri_label)
    assert np.array_equal(face_map, np.arange(len(F)))


class _FakeMesher:
    """Returns the unit-cube tet mesh moved onto the input's bbox; per call."""
    def __init__(self, unit_cube):
        self.P, self.T, self.F = unit_cube
        self.calls = 0

    def mesh(self, V, F, params, progress=None):
        self.calls += 1
        if progress:
            progress("tetrahedralizing", float("nan"), float("nan"), -1, -1)
        lo, hi = V.min(axis=0), V.max(axis=0)
        if hi[2] - lo[2] > 1.5:          # both cubes at once: two stacked copies
            n = len(self.P)
            P = np.vstack([self.P, self.P + [0, 0, 1]]) + lo
            return MeshingResult(P, np.vstack([self.F, self.F + n]),
                                 np.vstack([self.T, self.T + n]))
        return MeshingResult(self.P + lo, self.F, self.T)


@pytest.mark.parametrize("mode,calls", [(multibody.PER_BODY, 2), (multibody.CONFORMING, 1)])
def test_mesh_bodies(two_cubes, unit_cube, mode, calls):
    V, T, F, regions = two_cubes
    mesher, stages = _FakeMesher(unit_cube), []
    result, face_map, got = multibody.mesh_bodies(
        mesher, V, F, _bodies(F), {}, mode, progress=lambda s, *a: stages.append(s))
    assert mesher.calls == calls
    assert np.array_equal(got, regions)
    assert len(face_map) == len(result.triangles)
    # every boundary triangle maps into its own body's input triangles
    tri_label = multibody.boundary_regions(result.tetrahedra, got, result.triangles)
    assert np.array_equal(face_map >= len(F) // 2, tri_label == 1)
    if mode == multibody.PER_BODY:
        assert stages[0] == "Part 1/2: tetrahedralizing"


def test_single_body_has_no_regions(unit_cube):
    P, T, F = unit_cube
    result, face_map, regions = multibody.mesh_bodies(
        _FakeMesher(unit_cube), P, F, [(0, np.arange(len(F)))], {}, multibody.PER_BODY)
    assert regions is None and np.array_equal(face_map, np.arange(len(F)))


def test_cancel_between_bodies(two_cubes, unit_cube):
    from pvp.meshing.FTetWildMesher import MeshingCancelled
    V, T, F, _ = two_cubes
    mesher = _FakeMesher(unit_cube)
    with pytest.raises(MeshingCancelled):
        multibody.mesh_bodies(mesher, V, F, _bodies(F), {}, multibody.PER_BODY,
                              cancelled=lambda: mesher.calls >= 1)
    assert mesher.calls == 1
