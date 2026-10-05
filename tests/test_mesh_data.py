"""Every geometry source implements AbstractGeometryData consistently."""
import numpy as np

from geometry.AbstractMeshData import AbstractGeometryData
from geometry.InMemoryMeshData import InMemoryMeshData
from geometry.OBBMeshGenerator import OBBMeshGenerator
from fileio.NetgenVolWriter import write_vol
from fileio.VolumeMeshGeometryFile import TetrahedralVolumeMeshGeometryFile
from fileio.SurfaceMeshGeometryFile import TriangleSurfaceMeshGeometryFile


def test_surface_only_defaults(tmp_path, unit_cube):
    P, T, F = unit_cube
    import igl
    path = str(tmp_path / "cube.stl")
    igl.write_triangle_mesh(path, P, F)
    for data in (TriangleSurfaceMeshGeometryFile(path), OBBMeshGenerator(P)):
        assert isinstance(data, AbstractGeometryData)
        assert len(data.get_triangles()) > 0
        assert not data.has_tetrahedra()
        assert len(data.get_triangle_bcs()) == 0 and data.get_bc_names() == {}


def test_in_memory_volume(unit_cube):
    P, T, F = unit_cube
    data = InMemoryMeshData(vertices=P.tolist(), triangles=F.tolist(), tetrahedra=T.tolist())
    assert isinstance(data, AbstractGeometryData)
    assert data.has_tetrahedra()
    assert data.get_bc_names() == {}


def test_numpy_tetrahedra_have_no_truthiness_problem(unit_cube):
    P, T, F = unit_cube
    data = InMemoryMeshData(vertices=P, triangles=F, tetrahedra=T)   # numpy arrays
    assert data.has_tetrahedra()
    assert not InMemoryMeshData(vertices=P, triangles=F, tetrahedra=np.empty((0, 4))).has_tetrahedra()


def test_volume_file(tmp_path, unit_cube):
    P, T, F = unit_cube
    path = str(tmp_path / "cube.vol")
    write_vol(path, P, T, F, [("wall", list(range(len(F))))])
    data = TetrahedralVolumeMeshGeometryFile(path)
    assert isinstance(data, AbstractGeometryData)
    assert data.has_tetrahedra()
    assert data.get_bc_names() == {1: "wall"}
    assert len(data.get_triangle_bcs()) == len(data.get_triangles())
