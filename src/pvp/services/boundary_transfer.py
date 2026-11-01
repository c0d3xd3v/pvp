"""Carry boundary partitions across the meshing step: the mesher's boundary
is a new surface close to the input, so each new triangle takes the
partition of the closest input triangle."""
import numpy as np
from vtkmodules.util.numpy_support import numpy_to_vtk

from pvp.visualization.vtk import vtklib as vtk


def closest_cells(old_vertices, old_triangles, new_vertices, new_triangles) -> np.ndarray:
    """Index of the old triangle closest to each new triangle's centroid."""
    old_V = np.asarray(old_vertices, dtype=np.float64)
    old_F = np.asarray(old_triangles, dtype=np.int64)
    pts = vtk.vtkPoints()
    pts.SetData(numpy_to_vtk(old_V, deep=True))
    conn = np.column_stack((np.full(len(old_F), 3, dtype=np.int64), old_F)).ravel()
    cells = vtk.vtkCellArray()
    cells.SetCells(len(old_F), numpy_to_vtk(conn, deep=True, array_type=vtk.VTK_ID_TYPE))
    old_pd = vtk.vtkPolyData()
    old_pd.SetPoints(pts)
    old_pd.SetPolys(cells)
    locator = vtk.vtkCellLocator()
    locator.SetDataSet(old_pd)
    locator.BuildLocator()

    new_V = np.asarray(new_vertices, dtype=np.float64)
    centroids = new_V[np.asarray(new_triangles, dtype=np.int64)].mean(axis=1)
    closest = [0.0, 0.0, 0.0]
    cell_id, sub_id, dist2 = vtk.reference(0), vtk.reference(0), vtk.reference(0.0)
    result = np.zeros(len(centroids), dtype=np.int64)
    for i, c in enumerate(centroids):
        locator.FindClosestPoint(c.tolist(), closest, cell_id, sub_id, dist2)
        result[i] = int(cell_id)
    return result
