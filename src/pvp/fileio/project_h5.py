"""pvp project file (.pvp): one HDF5 file with everything needed to continue
working — the original input file, the surface, the boundary partitions, the
volume mesh, mesher parameters and UI settings. Layout (format_version 1):

    /            attrs: format, format_version, app_version, units
    /source      attrs: name; dataset "bytes" = original input file (optional)
    /surface     vertices (N,3) f8, triangles (M,3) i8, partition_ids (M,) i4
    /partitions/<id>   attrs: name, color
    /volume      vertices, triangles, tetrahedra (optional)
    /mesher      attrs: name; group "params" with one attr per parameter
    /settings    attrs: normal_angle, current_partition (0 = none), next_partition_id
"""
from dataclasses import dataclass, field

import numpy as np

from pvp.model.partitions import Partition

FORMAT = "pvp-project"
FORMAT_VERSION = 1
EXTENSION = ".pvp"


@dataclass
class ProjectState:
    surface_vertices: np.ndarray
    surface_triangles: np.ndarray
    partition_ids: np.ndarray
    partitions: list[Partition] = field(default_factory=list)
    next_partition_id: int = 1
    current_partition: int | None = None
    normal_angle: float = 10.0
    volume_vertices: np.ndarray | None = None
    volume_triangles: np.ndarray | None = None
    volume_tetrahedra: np.ndarray | None = None
    source_name: str = ""
    source_bytes: bytes | None = None
    mesher_name: str = ""
    mesher_params: dict = field(default_factory=dict)

    @property
    def has_volume(self) -> bool:
        return self.volume_tetrahedra is not None and len(self.volume_tetrahedra) > 0


def _app_version() -> str:
    from importlib import metadata      # ~20 ms, only needed when saving
    try:
        return metadata.version("pvp")
    except metadata.PackageNotFoundError:
        return "unknown"


def _put(group, name, data, dtype):
    group.create_dataset(name, data=np.asarray(data, dtype=dtype), compression="gzip")


def save_project(path: str, state: ProjectState):
    import h5py     # imported on use to keep startup fast
    with h5py.File(path, "w") as f:
        f.attrs.update(format=FORMAT, format_version=FORMAT_VERSION,
                       app_version=_app_version(), units="mm")

        if state.source_bytes is not None:
            src = f.create_group("source")
            src.attrs["name"] = state.source_name
            src.create_dataset("bytes", data=np.frombuffer(state.source_bytes, dtype=np.uint8),
                               compression="gzip")

        surf = f.create_group("surface")
        _put(surf, "vertices", state.surface_vertices, np.float64)
        _put(surf, "triangles", state.surface_triangles, np.int64)
        _put(surf, "partition_ids", state.partition_ids, np.int32)

        parts = f.create_group("partitions")
        for p in state.partitions:
            g = parts.create_group(str(p.id))
            g.attrs["name"] = p.name
            g.attrs["color"] = np.asarray(p.color, dtype=np.float64)

        if state.has_volume:
            vol = f.create_group("volume")
            _put(vol, "vertices", state.volume_vertices, np.float64)
            _put(vol, "triangles", state.volume_triangles, np.int64)
            _put(vol, "tetrahedra", state.volume_tetrahedra, np.int64)

        if state.mesher_name:
            m = f.create_group("mesher")
            m.attrs["name"] = state.mesher_name
            m.create_group("params").attrs.update(
                {k: float(v) for k, v in state.mesher_params.items()})

        f.create_group("settings").attrs.update(
            normal_angle=float(state.normal_angle),
            current_partition=int(state.current_partition or 0),
            next_partition_id=int(state.next_partition_id))


def load_project(path: str) -> ProjectState:
    import h5py
    with h5py.File(path, "r") as f:
        if f.attrs.get("format") != FORMAT:
            raise ValueError(f"{path} is not a pvp project file")
        version = int(f.attrs.get("format_version", 0))
        if version > FORMAT_VERSION:
            raise ValueError(f"{path} uses project format v{version}; this pvp "
                             f"reads up to v{FORMAT_VERSION} — please update pvp")

        surf = f["surface"]
        state = ProjectState(
            surface_vertices=surf["vertices"][()],
            surface_triangles=surf["triangles"][()],
            partition_ids=surf["partition_ids"][()],
        )
        if len(state.partition_ids) != len(state.surface_triangles):
            raise ValueError(f"{path}: {len(state.partition_ids)} partition ids for "
                             f"{len(state.surface_triangles)} surface triangles")

        state.partitions = sorted(
            (Partition(id=int(pid), name=str(g.attrs["name"]),
                       color=tuple(float(c) for c in g.attrs["color"]))
             for pid, g in f["partitions"].items()),
            key=lambda p: p.id)

        if "volume" in f:
            vol = f["volume"]
            state.volume_vertices = vol["vertices"][()]
            state.volume_triangles = vol["triangles"][()]
            state.volume_tetrahedra = vol["tetrahedra"][()]

        if "source" in f:
            state.source_name = str(f["source"].attrs["name"])
            state.source_bytes = f["source"]["bytes"][()].tobytes()

        if "mesher" in f:
            state.mesher_name = str(f["mesher"].attrs["name"])
            state.mesher_params = {k: float(v) for k, v in f["mesher"]["params"].attrs.items()}

        s = f["settings"].attrs
        state.normal_angle = float(s["normal_angle"])
        state.current_partition = int(s["current_partition"]) or None
        state.next_partition_id = int(s["next_partition_id"])
        return state
