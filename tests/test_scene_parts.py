"""BoundaryPartitions on a real FaceSelectionActor, and ClipPlane basics (no window)."""
import numpy as np
import pytest

from controllers.SceneCtrl import _triangle_polydata
from visualization.vtk.BoundaryPartitions import BoundaryPartitions, UNASSIGNED
from visualization.vtk.ClipPlane import ClipPlane
from visualization.vtk.FaceSelectionActor import FaceSelectionActor


@pytest.fixture
def parts(unit_cube):
    P, T, F = unit_cube
    actor = FaceSelectionActor()
    actor.setPolyData(_triangle_polydata(P, F), np.zeros(len(F), dtype=np.int32))
    renders, changes = [], []
    bp = BoundaryPartitions(request_render=lambda: renders.append(1))
    bp.on_changed = lambda: changes.append(1)
    bp.attach(actor)
    return bp, len(F), renders, changes


def test_starts_unassigned(parts):
    bp, n, *_ = parts
    assert bp.all() == [] and bp.current_id() is None
    assert np.all(bp.ids_per_cell() == UNASSIGNED) and len(bp.ids_per_cell()) == n


def test_add_assign_delete(parts):
    bp, n, renders, changes = parts
    a, b = bp.add("inlet"), bp.add("wall")
    assert [p.name for p in bp.all()] == ["inlet", "wall"]
    assert bp.all()[0].color != bp.all()[1].color

    bp.assign_faces([0, 1, 2], a)
    bp.assign_faces([2, 3], b)                     # reassigning a face moves it
    ids = bp.ids_per_cell()
    assert list(ids[:4]) == [a, a, b, b] and renders

    bp.set_current(a)
    bp.delete(a)                                   # its faces become unassigned
    ids = bp.ids_per_cell()
    assert list(ids[:4]) == [UNASSIGNED, UNASSIGNED, b, b]
    assert bp.current_id() is None and [p.name for p in bp.all()] == ["wall"]
    assert changes


def test_unknown_partition_is_ignored(parts):
    bp, *_ = parts
    bp.assign_faces([0], 42)
    bp.set_current(42)
    assert np.all(bp.ids_per_cell() == UNASSIGNED) and bp.current_id() is None


def test_attach_starts_over(parts, unit_cube):
    bp, *_ = parts
    bp.add("inlet")
    P, T, F = unit_cube
    actor = FaceSelectionActor()
    actor.setPolyData(_triangle_polydata(P, F), np.zeros(len(F), dtype=np.int32))
    bp.attach(actor)
    assert bp.all() == []
    bp.detach()
    assert bp.ids_per_cell() is None


def test_clip_axis_and_volume_filter(unit_cube):
    import vtk
    from vtkmodules.util.numpy_support import numpy_to_vtk
    P, T, F = unit_cube
    clip = ClipPlane()
    assert clip.set_axis("-y") and clip.plane.GetNormal() == (0, -1, 0)
    assert not clip.set_axis("w")

    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(P, deep=True))
    ug = vtk.vtkUnstructuredGrid(); ug.SetPoints(pts)
    conn = np.column_stack((np.full(len(T), 4), T)).ravel().astype(np.int64)
    ca = vtk.vtkCellArray(); ca.SetCells(len(T), numpy_to_vtk(conn, deep=True, array_type=vtk.VTK_ID_TYPE))
    ug.SetCells(vtk.VTK_TETRA, ca)

    clip.set_axis("x"); clip.plane.SetOrigin(0.5, 0.5, 0.5)
    f = clip.volume_filter(ug); f.Update()
    kept = f.GetOutput().GetNumberOfCells()
    assert 0 < kept < len(T)          # roughly half the tets, whole cells only
