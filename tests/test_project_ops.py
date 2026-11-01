"""Project operations without GUI: open, export, .pvp round trip."""
import numpy as np
import pytest

from pvp.model.mesh import Mesh
from pvp.model.project import Project
from pvp.services import export, project_ops


@pytest.fixture
def meshed(unit_cube):
    """A project as after meshing: shared surface/volume, two partitions."""
    P, T, F = unit_cube
    p = Project()
    mesh = Mesh(vertices=P, triangles=F, tetrahedra=T)
    p.start("cube", mesh)
    p.set_volume(mesh, np.arange(len(F)))
    p.partitions.assign_faces([0, 1, 2], p.partitions.add("inlet"))
    p.partitions.assign_faces([3], p.partitions.add("wall"))
    p.mesher_name, p.mesher_params = "FloatTetwild", {"eps": 0.01}
    return p


def test_export_summary_and_groups(meshed):
    s = export.export_summary(meshed)
    n = len(meshed.surface.triangles)
    assert s == {"boundaries": 2, "unassigned": n - 4, "tets": len(meshed.volume.tetrahedra)}
    groups = export.collect_bc_groups(meshed.partitions, n)
    assert [g.name for g in groups] == ["inlet", "wall", "default"]
    assert sum(len(g.triangles) for g in groups) == n
    with pytest.raises(ValueError):
        export.collect_bc_groups(meshed.partitions, n + 1)


def test_export_errors(meshed, tmp_path):
    with pytest.raises(ValueError, match="Unknown export format"):
        export.export_volume(meshed, str(tmp_path / "x"), "nope")
    with pytest.raises(ValueError, match="No volume mesh"):
        export.export_volume(Project(), str(tmp_path / "x"), "vol")


def test_vol_round_trip_keeps_names_and_drops_default(meshed, tmp_path):
    path, _ = export.export_volume(meshed, str(tmp_path / "cube"), "vol")
    assert path.endswith(".vol")
    q = Project()
    project_ops.open_volume(q, path)
    assert [p.name for p in q.partitions.all()] == ["inlet", "wall"]
    assert np.array_equal(q.partitions.ids_per_cell(), meshed.partitions.ids_per_cell())
    assert q.source_name == "cube.vol" and q.mesher_name == ""
    assert not q.partitions.undo()


def test_project_file_round_trip(meshed, tmp_path):
    meshed.normal_angle = 22.0
    meshed.partitions.set_current(2)
    path = project_ops.save_project_file(meshed, str(tmp_path / "proj"))
    assert path.endswith(".pvp")
    q = Project()
    project_ops.open_project_file(q, path)
    assert np.array_equal(q.volume_face_map, meshed.volume_face_map)
    assert np.array_equal(q.partitions.ids_per_cell(), meshed.partitions.ids_per_cell())
    assert [(p.id, p.name) for p in q.partitions.all()] == [(1, "inlet"), (2, "wall")]
    assert q.partitions.current_id() == 2 and q.normal_angle == 22.0
    assert q.mesher_params == {"eps": 0.01} and q.name == "proj"


def test_broken_project_file_leaves_project_alone(meshed, tmp_path):
    bad = tmp_path / "bad.pvp"
    bad.write_bytes(b"not hdf5")
    with pytest.raises(Exception):
        project_ops.open_project_file(meshed, str(bad))
    assert meshed.name == "cube" and len(meshed.partitions.all()) == 2


def test_bounding_box(meshed):
    project_ops.add_bounding_box(meshed)
    assert len(meshed.background.triangles) == 12


def test_vol_input_is_the_boundary_surface(meshed, tmp_path):
    from pvp.geometry.surface_check import surface_stats
    path, _ = export.export_volume(meshed, str(tmp_path / "cube"), "vol")
    p = Project()
    project_ops.open_volume(p, path)
    surf, vol = p.surface, p.volume
    assert not surf.has_tetrahedra and len(surf.triangles) == len(vol.triangles)
    assert len(surf.vertices) < len(vol.vertices)       # interior nodes dropped
    assert surface_stats(surf.vertices, surf.triangles).closed
    assert np.array_equal(p.volume_face_map, np.arange(len(vol.triangles)))


def test_meshing_keeps_input_and_partitions(meshed, unit_cube, tmp_path):
    """Partitions stay on the input surface; a (re-)meshing result only gets
    a face map through which export and saving carry them over."""
    P, T, F = unit_cube
    surface, ids = meshed.surface, meshed.partitions.ids_per_cell().copy()
    flipped = F[::-1]                                  # same boundary, other order
    project_ops.take_mesh_result(meshed, P, flipped, T)
    assert meshed.surface is surface and np.array_equal(meshed.partitions.ids_per_cell(), ids)
    assert np.array_equal(meshed.volume_partition_ids(), ids[::-1])
    groups = export.build_export_mesh(meshed).bc_groups
    inlet = next(g for g in groups if g.name == "inlet")
    assert sorted(inlet.triangles) == sorted(len(F) - 1 - np.array([0, 1, 2]))

    path = project_ops.save_project_file(meshed, str(tmp_path / "proj"))
    q = Project()
    project_ops.open_project_file(q, path)
    assert np.array_equal(q.volume_partition_ids(), ids[::-1])


def test_only_checked_components_get_meshed_and_saved(tmp_path):
    from pvp.geometry.surface_check import component_labels
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    F = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]])
    p = Project()
    # big tet first in the file, a small one shifted away
    p.start("two", Mesh(vertices=np.vstack((V * 2, V + 10)), triangles=np.vstack((F, F + 4))))
    assert list(p.surface_components) == [0] * 4 + [1] * 4
    assert list(p.meshed_components) == [True, True]
    p.meshed_components[0] = False
    assert list(p.meshed_faces()) == [4, 5, 6, 7]

    # a "mesh" of the second tet only: its boundary maps onto faces 4..7
    project_ops.take_mesh_result(p, V + 10, F, np.array([[0, 1, 2, 3]]))
    assert sorted(p.volume_face_map) == [4, 5, 6, 7]

    q = Project()
    project_ops.open_project_file(q, project_ops.save_project_file(p, str(tmp_path / "two")))
    assert list(q.meshed_components) == [False, True]
    assert np.array_equal(q.surface_components, component_labels(q.surface.triangles))
