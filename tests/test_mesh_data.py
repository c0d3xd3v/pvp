"""Mesh container and the readers that produce it."""
import numpy as np
import pytest

from pvp.model.mesh import Mesh
from pvp.geometry.bounding_box import bounding_box_mesh
from pvp.fileio.NetgenVolWriter import write_vol
from pvp.fileio.readers import read_mesh, read_surface, read_volume
from pvp.fileio.export_model import ExportMesh, BCGroup


def test_normalizes_arrays(unit_cube):
    P, T, F = unit_cube
    m = Mesh(vertices=P.tolist(), triangles=F.tolist(), tetrahedra=T.tolist())
    assert m.vertices.dtype == np.float64 and m.vertices.shape == P.shape
    assert m.triangles.dtype == np.int64 and m.tetrahedra.shape == T.shape
    assert m.has_tetrahedra
    assert m.bc_names == {} and m.triangle_bcs.shape == (0,)


def test_surface_only_has_empty_tets(unit_cube):
    P, _, F = unit_cube
    for m in (Mesh(vertices=P, triangles=F), Mesh(vertices=P, triangles=F, tetrahedra=np.empty((0, 4)))):
        assert not m.has_tetrahedra and m.tetrahedra.shape == (0, 4)
    assert Mesh(vertices=P, triangles=F).bbox_diagonal() == pytest.approx(np.sqrt(3))


def test_read_surface_scales_to_mm(tmp_path, unit_cube):
    P, _, F = unit_cube
    import igl
    path = str(tmp_path / "cube.stl")
    igl.write_triangle_mesh(path, P, F)
    m = read_surface(path, scale=10.0)
    assert len(m.triangles) == len(F) and not m.has_tetrahedra
    assert m.bbox_diagonal() == pytest.approx(10 * np.sqrt(3))
    assert isinstance(read_mesh(path), Mesh)


def test_bounding_box_is_closed_and_consistently_oriented(unit_cube):
    P, *_ = unit_cube
    box = bounding_box_mesh(P, scale=1.0)
    assert len(box.vertices) == 8 and len(box.triangles) == 12
    v, f = box.vertices, box.triangles
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    outward = (v[f].mean(axis=1) - v.mean(axis=0))
    assert np.all(np.einsum("ij,ij->i", n, outward) < 0)     # all inward
    edges = np.sort(f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    assert np.all(np.unique(edges, axis=0, return_counts=True)[1] == 2)


def test_read_volume(tmp_path, unit_cube):
    P, T, F = unit_cube
    path = str(tmp_path / "cube.vol")
    write_vol(path, ExportMesh(nodes=P, tets=T, surface_tri=F,
                               bc_groups=[BCGroup("wall", np.arange(len(F)))]))
    m = read_volume(path)
    assert m.has_tetrahedra
    assert m.bc_names == {1: "wall"}
    assert len(m.triangle_bcs) == len(m.triangles)
