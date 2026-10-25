"""PreProcCtrl.exportVolume: boundary-condition groups from the project's partitions."""
import numpy as np
import ngsolve as ngs
import pytest

from pvp.controllers.PreProcCtrl import PreProcCtrl
from pvp.model.mesh import Mesh
from pvp.model.project import Project


@pytest.fixture
def ctrl(unit_cube):
    P, T, F = unit_cube
    project = Project()
    c = PreProcCtrl(project, scene_ctrl=None, selection_ctrl=None)   # export needs no scene
    assert not c.canExportVolume()
    mesh = Mesh(vertices=P, triangles=F, tetrahedra=T)
    project.start("cube", mesh, volume=mesh)
    return c, project, P, F


def test_unassigned_faces_go_to_default(tmp_path, ctrl):
    c, project, P, F = ctrl
    on_x0 = np.all(np.isclose(P[F][:, :, 0], 0.0), axis=1)
    project.partitions.assign_faces(np.flatnonzero(on_x0), project.partitions.add("inlet"))

    assert c.canExportVolume()
    assert c.getExportSummary()["boundaries"] == 1
    assert c.getExportSummary()["unassigned"] == int((~on_x0).sum())

    path = tmp_path / "out"                       # suffix gets added
    assert c.exportVolume(str(path)) == ""
    mesh = ngs.Mesh(str(path) + ".vol")
    assert set(mesh.GetBoundaries()) == {"inlet", "default"}
    assert ngs.Integrate(1, mesh, ngs.BND, definedon=mesh.Boundaries("inlet")) == pytest.approx(1.0)


def test_surface_mismatch_is_reported(tmp_path, ctrl):
    c, project, P, F = ctrl
    v = project.volume
    project.volume = Mesh(vertices=v.vertices, triangles=v.triangles[:-1], tetrahedra=v.tetrahedra)
    err = c.exportVolume(str(tmp_path / "x.vol"))
    assert "triangles" in err
    assert not (tmp_path / "x.vol").exists()
