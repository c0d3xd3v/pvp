"""Round trip of the .pvp project file (fileio/project_h5.py)."""
import h5py
import numpy as np
import pytest

from fileio.project_h5 import ProjectState, load_project, save_project
from geometry.Partition import Partition


@pytest.fixture
def state(unit_cube):
    P, T, F = unit_cube
    ids = np.zeros(len(F), dtype=np.int32)
    ids[:3], ids[3:5] = 1, 3
    return ProjectState(
        surface_vertices=P, surface_triangles=F, partition_ids=ids,
        partitions=[Partition(1, "inlet", (0.1, 0.2, 0.3)), Partition(3, "wall", (1.0, 0.5, 0.0))],
        next_partition_id=4, current_partition=3, normal_angle=17.5,
        volume_vertices=P, volume_triangles=F, volume_tetrahedra=T,
        source_name="cube.stl", source_bytes=b"solid cube\x00\x01",
        mesher_name="FloatTetwild", mesher_params={"eps": 0.05, "stop_energy": 10.0},
    )


def test_round_trip(tmp_path, state):
    path = tmp_path / "p.pvp"
    save_project(str(path), state)
    got = load_project(str(path))
    for name in ("surface_vertices", "surface_triangles", "partition_ids",
                 "volume_vertices", "volume_triangles", "volume_tetrahedra"):
        assert np.array_equal(getattr(got, name), getattr(state, name)), name
    assert got.partitions == state.partitions
    assert (got.next_partition_id, got.current_partition, got.normal_angle) == (4, 3, 17.5)
    assert (got.source_name, got.source_bytes) == ("cube.stl", b"solid cube\x00\x01")
    assert (got.mesher_name, got.mesher_params) == ("FloatTetwild", state.mesher_params)


def test_surface_only_project(tmp_path, state):
    state.volume_vertices = state.volume_triangles = state.volume_tetrahedra = None
    state.source_bytes, state.mesher_name, state.current_partition = None, "", None
    path = tmp_path / "s.pvp"
    save_project(str(path), state)
    got = load_project(str(path))
    assert not got.has_volume and got.source_bytes is None and got.current_partition is None


def test_rejects_foreign_and_newer_files(tmp_path, state):
    foreign = tmp_path / "x.pvp"
    with h5py.File(foreign, "w") as f:
        f.attrs["format"] = "something-else"
    with pytest.raises(ValueError, match="not a pvp project"):
        load_project(str(foreign))

    newer = tmp_path / "n.pvp"
    save_project(str(newer), state)
    with h5py.File(newer, "a") as f:
        f.attrs["format_version"] = 99
    with pytest.raises(ValueError, match="v99"):
        load_project(str(newer))
