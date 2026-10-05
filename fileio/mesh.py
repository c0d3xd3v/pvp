import locale

import vtk
import igl
import numpy as np

from fileio.hdf5 import read_pde_dataset_from_hdf5

from visualization.vtk.vtkhelper import iglToVtkPolydata
from visualization.vtk.vtkhelper import addScalarCellData
from visualization.vtk.vtkhelper import read_unstructured_grid

from fileio.MeshGeometryFile import TetrahedralVolumeMeshGeometryFile

try:
    import mhno.point_cloud_tools_pybind11 as pct
except:
    pct = None

try:
    import ngsolve as ngs
    import netgen.meshing as nm
except:
    ngs = None


def read_mesh_file(file_path):
    function_names = []
    poly_mesh = None
    mesh_file = None
    print("READ : ", file_path)
    if file_path.endswith(".vtk") or file_path.endswith(".vtu"):
        poly_mesh:vtk.vtkUnstructuredGrid = read_unstructured_grid(file_path)

        pointData = poly_mesh.GetPointData()
        n = pointData.GetNumberOfArrays()

        pointData = poly_mesh.GetPointData()
        function_names = []
        for k in range(n):
            array_name = pointData.GetArrayName(k)
            function_names.append(array_name)

    elif file_path.endswith(".h5"):
        old_locale = locale.getlocale(locale.LC_NUMERIC)
        locale.setlocale(locale.LC_NUMERIC, "C")
        train_data, vertices, triangles = read_pde_dataset_from_hdf5(file_path)
        vertices, triangles = vertices.T, triangles.T
        locale.setlocale(locale.LC_NUMERIC, old_locale)

        poly_mesh = iglToVtkPolydata(triangles, vertices)

        n = len(train_data)
        function_names = []
        for k in range(n):
            array_name = "y"+str(k)
            addScalarCellData(poly_mesh, train_data[k]['y'], array_name)
            function_names.append(array_name)

    elif file_path.endswith(".obj") or file_path.endswith(".stl"):
        old_locale = locale.getlocale(locale.LC_NUMERIC)
        locale.setlocale(locale.LC_NUMERIC, "C")
        sv, sf = igl.read_triangle_mesh(file_path)
        (SV, SVI, SVJ, SF) = igl.remove_duplicate_vertices(sv, sf, epsilon=1e-7)
        locale.setlocale(locale.LC_NUMERIC, old_locale)
        function_names = []
        poly_mesh = iglToVtkPolydata(SF, SV)

    elif file_path.endswith(".vol"):
        if ngs is not None:
            mesh_file = NgMeshGeometryFile(file_path)
            poly_mesh = iglToVtkPolydata(mesh_file.get_triangles(), mesh_file.get_vertices())

    return function_names, poly_mesh, mesh_file
