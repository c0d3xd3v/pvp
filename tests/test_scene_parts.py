"""Partitions model, its view on a real FaceSelectionActor, and ClipPlane basics (no window)."""
import numpy as np
import pytest
from vtkmodules.util.numpy_support import vtk_to_numpy

from pvp.controllers.SceneCtrl import _triangle_polydata
from pvp.model.partitions import Partitions, UNASSIGNED
from pvp.visualization.vtk.ClipPlane import ClipPlane
from pvp.visualization.vtk.FaceSelectionActor import FaceSelectionActor
from pvp.visualization.vtk.PartitionView import PartitionView


@pytest.fixture
def parts(unit_cube):
    _, _, F = unit_cube
    changes = []
    bp = Partitions()
    bp.subscribe(lambda ids, listed: changes.append((ids, listed)))
    bp.reset(len(F))
    return bp, len(F), changes


def test_starts_unassigned(parts):
    bp, n, *_ = parts
    assert bp.all() == [] and bp.current_id() is None
    assert np.all(bp.ids_per_cell() == UNASSIGNED) and len(bp.ids_per_cell()) == n


def test_add_assign_delete(parts):
    bp, n, changes = parts
    a, b = bp.add("inlet"), bp.add("wall")
    assert [p.name for p in bp.all()] == ["inlet", "wall"]
    assert bp.all()[0].color != bp.all()[1].color

    bp.assign_faces([0, 1, 2], a)
    bp.assign_faces([2, 3], b)                     # reassigning a face moves it
    ids = bp.ids_per_cell()
    assert list(ids[:4]) == [a, a, b, b]
    assert changes[-1] == (True, False)            # assignments don't touch the list

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


def test_reset_starts_over(parts):
    bp, n, _ = parts
    a = bp.add("inlet")
    bp.assign_faces([0], a)
    bp.reset(n + 1)
    assert bp.all() == [] and bp.current_id() is None and not bp.undo()
    assert len(bp.ids_per_cell()) == n + 1 and not np.any(bp.ids_per_cell())
    bp.reset(None)
    assert bp.ids_per_cell() is None
    bp.clear_faces([0])                            # no surface: ignored


def test_view_follows_the_model(parts, unit_cube):
    bp, n, _ = parts
    P, _, F = unit_cube
    a = bp.add("inlet")
    bp.assign_faces([0, 1], a)
    actor = FaceSelectionActor()
    actor.setPolyData(_triangle_polydata(P, F), np.zeros(n, dtype=np.int32))
    renders, hover = [], []
    view = PartitionView(bp, request_render=lambda: renders.append(1), set_hover_enabled=hover.append)
    view.attach(actor)                             # takes over the existing assignments
    actor_ids = lambda: vtk_to_numpy(actor.full_polydata.GetCellData().GetArray("PartitionIds"))
    assert list(actor_ids()[:3]) == [a, a, UNASSIGNED]
    assert actor.lut.GetTableValue(a)[:3] == pytest.approx(bp.all()[0].color, abs=1 / 255)

    bp.assign_faces([2], a)
    assert actor_ids()[2] == a and renders
    bp.set_current(a)
    assert hover[-1] is True
    view.preview_faces([5, 6])
    assert actor.preview_actor.GetVisibility()
    bp.delete(a)                                   # current gone: no hover, no preview
    assert hover[-1] is False and not actor.preview_actor.GetVisibility()
    assert not np.any(actor_ids())
    view.detach()
    bp.assign_faces([3], bp.add("wall"))           # detached: actor untouched
    assert not np.any(actor_ids())


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
    from pvp.model.partitions import Partition
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
