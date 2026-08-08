import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from geometry.AbstractMeshData import AbstractGeometryData


class OBBMeshGenerator(AbstractGeometryData):
    """
    Generates an axis-aligned bounding box (AABB) as a triangle surface mesh
    from the bounds of a given point cloud. Later: OBB via PCA.
    """

    def __init__(self, vertices, scale: float = 1.1):
        verts = np.array(vertices)
        mn, mx = verts.min(axis=0), verts.max(axis=0)
        center = (mn + mx) / 2
        half = (mx - mn) / 2 * scale

        # 8 corners of the box
        self.__vertices = np.array([
            center + np.array([ s0,  s1,  s2]) * half
            for s0 in (-1, 1)
            for s1 in (-1, 1)
            for s2 in (-1, 1)
        ])

        # 12 triangles (2 per face, 6 faces)
        # Vertex index layout: (s0, s1, s2) → index = s0*4 + s1*2 + s2
        def idx(s0, s1, s2):
            return ((s0 + 1) // 2) * 4 + ((s1 + 1) // 2) * 2 + ((s2 + 1) // 2)

        faces = []
        for face in [
            # -x face
            [idx(-1,-1,-1), idx(-1, 1,-1), idx(-1, 1, 1)],
            [idx(-1,-1,-1), idx(-1, 1, 1), idx(-1,-1, 1)],
            # +x face
            [idx( 1,-1,-1), idx( 1, 1, 1), idx( 1, 1,-1)],
            [idx( 1,-1,-1), idx( 1,-1, 1), idx( 1, 1, 1)],
            # -y face
            [idx(-1,-1,-1), idx( 1,-1, 1), idx( 1,-1,-1)],
            [idx(-1,-1,-1), idx(-1,-1, 1), idx( 1,-1, 1)],
            # +y face
            [idx(-1, 1,-1), idx( 1, 1,-1), idx( 1, 1, 1)],
            [idx(-1, 1,-1), idx( 1, 1, 1), idx(-1, 1, 1)],
            # -z face
            [idx(-1,-1,-1), idx( 1,-1,-1), idx( 1, 1,-1)],
            [idx(-1,-1,-1), idx( 1, 1,-1), idx(-1, 1,-1)],
            # +z face
            [idx(-1,-1, 1), idx( 1, 1, 1), idx( 1,-1, 1)],
            [idx(-1,-1, 1), idx(-1, 1, 1), idx( 1, 1, 1)],
        ]:
            faces.append(face)

        self.__triangles = np.array(faces, dtype=np.int64)

    def get_vertices(self):
        return self.__vertices

    def get_triangles(self):
        return self.__triangles

    def get_vtk_polydata(self) -> vtk.vtkPolyData:
        polydata = vtk.vtkPolyData()
        points_array = numpy_to_vtk(self.__vertices, deep=True)
        _sf = self.__triangles.copy()
        nbpts = np.full(_sf.shape[0], 3)
        _sf = np.column_stack((nbpts, _sf))
        triangles_array = numpy_to_vtk(_sf, deep=True, array_type=vtk.VTK_ID_TYPE)
        points = vtk.vtkPoints()
        points.SetData(points_array)
        cells = vtk.vtkCellArray()
        cells.SetCells(triangles_array.GetNumberOfTuples(), triangles_array)
        polydata.SetPoints(points)
        polydata.SetPolys(cells)
        return polydata
