"""BoundaryPartitions on a real FaceSelectionActor, and ClipPlane basics (no window)."""
import numpy as np
import pytest

from pvp.controllers.SceneCtrl import _triangle_polydata
from pvp.visualization.vtk.BoundaryPartitions import BoundaryPartitions, UNASSIGNED
from pvp.visualization.vtk.ClipPlane import ClipPlane
from pvp.visualization.vtk.FaceSelectionActor import FaceSelectionActor


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


def test_undo_redo_assignments(parts):
    bp, n, *_ = parts
    a = bp.add("inlet")
    bp.assign_faces([0, 1, 2], a)
    bp.assign_faces([0, 1, 2], a)                  # no change -> no extra undo step
    bp.clear_faces([1])
    assert list(bp.ids_per_cell()[:3]) == [a, UNASSIGNED, a]

    assert bp.undo() and list(bp.ids_per_cell()[:3]) == [a, a, a]
    assert bp.undo() and np.all(bp.ids_per_cell() == UNASSIGNED)
    assert bp.undo() and bp.all() == []            # the add itself
    assert not bp.undo()

    assert bp.redo() and [p.name for p in bp.all()] == ["inlet"]
    assert bp.redo() and list(bp.ids_per_cell()[:3]) == [a, a, a]
    bp.assign_faces([5], a)                        # a new edit drops the redo branch
    assert not bp.redo()


def test_undo_delete_restores_name_color_and_faces(parts):
    bp, *_ = parts
    a = bp.add("inlet")
    bp.assign_faces([0, 1], a)
    color = bp.all()[0].color
    bp.set_current(a)
    bp.delete(a)
    assert bp.all() == [] and bp.current_id() is None
    assert bp.undo()
    assert [(p.id, p.name, p.color) for p in bp.all()] == [(a, "inlet", color)]
    assert list(bp.ids_per_cell()[:2]) == [a, a] and bp.current_id() == a
    assert bp.add("next") == a + 1                 # ids are not reused after undo


def test_undo_limit_and_unrecorded_edits(parts):
    bp, n, *_ = parts
    a = bp.add("inlet", record=False)
    bp.assign_faces([0], a, record=False)
    assert not bp.undo()
    for k in range(60):                            # 60 real changes on face 1
        if k % 2 == 0:
            bp.assign_faces([1], a)
        else:
            bp.clear_faces([1])
    steps = 0
    while bp.undo():
        steps += 1
    assert steps == 50


def test_restore_takes_ids_and_colors_verbatim(parts):
    bp, n, *_ = parts
    from pvp.geometry.Partition import Partition
    ids = np.zeros(n, dtype=np.int32)
    ids[:4] = 7
    bp.restore([Partition(7, "outlet", (0.3, 0.4, 0.5))], ids, next_id=8, current=7)
    assert [(p.id, p.name, p.color) for p in bp.all()] == [(7, "outlet", (0.3, 0.4, 0.5))]
    assert np.array_equal(bp.ids_per_cell(), ids) and bp.current_id() == 7
    assert not bp.undo()
    assert bp.add("next") == 8


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
