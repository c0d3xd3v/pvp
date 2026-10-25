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
    p.start("cube", mesh, volume=mesh)
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
    assert q.surface is q.volume                   # one shared mesh, as before saving
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
