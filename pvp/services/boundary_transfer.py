"""Carry boundary partitions across the meshing step: the mesher's boundary
is a new surface close to the input, so each new triangle takes the
partition of the closest old triangle."""
from dataclasses import dataclass

import numpy as np
from vtkmodules.util.numpy_support import numpy_to_vtk

from pvp.model.project import Project
from pvp.visualization.vtk import vtklib as vtk


@dataclass(frozen=True)
class BoundarySnapshot:
    vertices: np.ndarray       # surface before meshing
    triangles: np.ndarray
    ids_per_cell: np.ndarray   # partition id per triangle
    names: dict[int, str]      # partition id -> name


def snapshot_boundaries(project: Project) -> BoundarySnapshot | None:
    """The surface + partitions to transfer, or None if nothing is assigned
    (no surface, no named partitions, or every triangle unassigned)."""
    ids = project.partitions.ids_per_cell()
    names = {p.id: p.name for p in project.partitions.all()}
    if project.surface is None or ids is None or not np.any(ids) or not names:
        return None
    return BoundarySnapshot(project.surface.vertices, project.surface.triangles, ids, names)


def closest_cell_ids(old_vertices, old_triangles, old_ids, new_vertices, new_triangles) -> np.ndarray:
    """old_ids of the old triangle closest to each new triangle's centroid."""
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
    result = np.zeros(len(centroids), dtype=np.int32)
    for i, c in enumerate(centroids):
        locator.FindClosestPoint(c.tolist(), closest, cell_id, sub_id, dist2)
        cid = int(cell_id)
        if 0 <= cid < len(old_ids):
            result[i] = old_ids[cid]
    return result


def apply_snapshot(project: Project, snap: BoundarySnapshot):
    """Recreate the snapshot's partitions (by name, in original id order so
    colors stay stable) on the project's current surface."""
    new_ids = closest_cell_ids(snap.vertices, snap.triangles, snap.ids_per_cell,
                               project.surface.vertices, project.surface.triangles)
    parts = project.partitions
    for old_pid in sorted(snap.names):
        pid = parts.add(snap.names[old_pid], record=False)
        faces = np.flatnonzero(new_ids == old_pid)
        if faces.size:
            parts.assign_faces(faces, pid, record=False)
