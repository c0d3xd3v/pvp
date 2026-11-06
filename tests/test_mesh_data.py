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


def _ascii_solid(name, V, F):
    lines = [f"solid {name}"]
    for tri in F:
        lines += ["  facet normal 0 0 0", "    outer loop"]
        lines += [f"      vertex {x} {y} {z}" for x, y, z in V[tri]]
        lines += ["    endloop", "  endfacet"]
    return "\n".join(lines + [f"endsolid {name}", ""])


def test_read_surface_keeps_touching_solids_apart(tmp_path):
    """Two boxes sharing a face, one solid each: they must stay two
    components with all their triangles (contact faces included)."""
    from pvp.geometry.surface_check import component_labels
    V = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
    F = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4],
                  [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
    path = tmp_path / "two.stl"
    path.write_text(_ascii_solid("a", V, F) + _ascii_solid("b", V + [0, 0, 1], F))
    m = read_surface(str(path))
    assert len(m.triangles) == 24 and len(m.vertices) == 16
    assert component_labels(m.triangles).max() == 1

    one = tmp_path / "one.stl"      # a single solid: coincident vertices still merge
    one.write_text(_ascii_solid("a", np.vstack([V, V + [0, 0, 1]]), np.vstack([F, F + 8])))
    assert len(read_surface(str(one)).vertices) == 12


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
