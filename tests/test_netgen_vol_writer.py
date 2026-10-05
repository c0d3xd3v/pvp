import numpy as np
import ngsolve as ngs
import pytest

from fileio.NetgenVolWriter import write_vol
from fileio.VolumeMeshGeometryFile import TetrahedralVolumeMeshGeometryFile


def scrambled(T, F):
    """Flip the orientation of every other tet and boundary face, so the
    writer has to fix it."""
    T, F = T.copy(), F.copy()
    T[::2, [2, 3]] = T[::2, [3, 2]]
    F[::2, [1, 2]] = F[::2, [2, 1]]
    return T, F


def split_groups(P, F):
    on_x0 = np.where(np.all(np.isclose(P[F][:, :, 0], 0.0), axis=1))[0]
    rest = np.setdiff1d(np.arange(len(F)), on_x0)
    return [("inlet", on_x0.tolist()), ("wall", rest.tolist())]


@pytest.fixture
def written(tmp_path, unit_cube):
    P, T, F = unit_cube
    T, F = scrambled(T, F)
    groups = split_groups(P, F)
    path = str(tmp_path / "cube.vol")
    write_vol(path, P, T, F, groups)
    return path, P, T, F, groups


def test_volume_and_outward_normals(written):
    path, *_ = written
    mesh = ngs.Mesh(path)
    assert ngs.Integrate(1, mesh) == pytest.approx(1.0)
    # divergence theorem: int_dOmega x.n = 3 |Omega| only holds for outward normals
    n = ngs.specialcf.normal(3)
    flux = ngs.Integrate(ngs.CF((ngs.x, ngs.y, ngs.z)) * n, mesh, ngs.BND)
    assert flux == pytest.approx(3.0)


def test_tets_have_netgen_orientation(written):
    path, *_ = written
    m = ngs.Mesh(path).ngmesh
    P = np.array([[p[0], p[1], p[2]] for p in m.Points()])
    T = np.array([[int(v.nr) - 1 for v in e.vertices] for e in m.Elements3D()])
    d = np.einsum('ij,ij->i', np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]),
                  P[T[:, 3]] - P[T[:, 0]])
    assert np.all(d < 0)   # netgen's own meshes use this orientation


def test_boundary_names_and_areas(written):
    path, *_ = written
    mesh = ngs.Mesh(path)
    assert set(mesh.GetBoundaries()) == {"inlet", "wall"}
    inlet = ngs.Integrate(1, mesh, ngs.BND, definedon=mesh.Boundaries("inlet"))
    wall = ngs.Integrate(1, mesh, ngs.BND, definedon=mesh.Boundaries("wall"))
    assert inlet == pytest.approx(1.0)
    assert wall == pytest.approx(5.0)


def test_reimport(written):
    path, P, T, F, groups = written
    data = TetrahedralVolumeMeshGeometryFile(path)
    assert len(data.get_vertices()) == len(P)
    assert len(data.get_tetrahedra()) == len(T)
    assert len(data.get_triangles()) == len(F)
    assert data.get_bc_names() == {1: "inlet", 2: "wall"}
    bcs = np.array(data.get_triangle_bcs())
    assert (bcs == 1).sum() == len(groups[0][1])


def test_triangle_not_on_a_tet_is_rejected(tmp_path, unit_cube):
    P, T, F = unit_cube
    bad = np.array([[T[0, 0], T[1, 1], T[2, 2]]])
    if any(set(bad[0]) <= set(t) for t in T):
        pytest.skip("random triangle happens to be a tet face")
    with pytest.raises(ValueError):
        write_vol(str(tmp_path / "bad.vol"), P, T, bad, [("x", [0])])
