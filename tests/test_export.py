"""PreProcCtrl.exportVolume: boundary-condition groups from the scene partitions."""
from dataclasses import dataclass

import numpy as np
import ngsolve as ngs
import pytest

from controllers.PreProcCtrl import PreProcCtrl


@dataclass
class Partition:
    id: int
    name: str


class FakePartitions:
    def __init__(self):
        self.part_ids = None
        self.list = []
        self.on_changed = None

    def ids_per_cell(self): return self.part_ids
    def all(self): return self.list


class FakeSceneCtrl:
    """Just the part of SceneCtrl that PreProcCtrl needs for meshing + export."""
    def __init__(self):
        self.partitions = FakePartitions()

    def add_surface_geometry(self, vertices, triangles):
        self.partitions.part_ids = np.zeros(len(triangles), dtype=int)   # 0 = unassigned
        return None

    def add_volume_unstructured_mesh(self, vertices, tetrahedra): pass


@pytest.fixture
def ctrl(unit_cube):
    P, T, F = unit_cube
    scene = FakeSceneCtrl()
    c = PreProcCtrl()
    c.set_controllers(scene, None)
    assert not c.canExportVolume()
    c.replace_project_with_mesh(P, F, T, name="cube")
    return c, scene, P, F


def test_unassigned_faces_go_to_default(tmp_path, ctrl):
    c, scene, P, F = ctrl
    on_x0 = np.all(np.isclose(P[F][:, :, 0], 0.0), axis=1)
    scene.partitions.list = [Partition(1, "inlet")]
    scene.partitions.part_ids[on_x0] = 1

    assert c.canExportVolume()
    assert c.getExportSummary()["boundaries"] == 1
    assert c.getExportSummary()["unassigned"] == int((~on_x0).sum())

    path = tmp_path / "out"                       # suffix gets added
    assert c.exportVolume(str(path)) == ""
    mesh = ngs.Mesh(str(path) + ".vol")
    assert set(mesh.GetBoundaries()) == {"inlet", "default"}
    assert ngs.Integrate(1, mesh, ngs.BND, definedon=mesh.Boundaries("inlet")) == pytest.approx(1.0)


def test_surface_mismatch_is_reported(tmp_path, ctrl):
    c, scene, P, F = ctrl
    scene.partitions.part_ids = scene.partitions.part_ids[:-1]          # surface no longer matches the volume
    err = c.exportVolume(str(tmp_path / "x.vol"))
    assert "triangles" in err
    assert not (tmp_path / "x.vol").exists()
