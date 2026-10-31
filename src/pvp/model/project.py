"""The pre-processing project: the meshes, their boundary partitions and the
settings that belong to them (what a .pvp file stores)."""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from pvp.geometry.surface_check import component_labels
from pvp.model.mesh import Mesh
from pvp.model.partitions import Partitions

DEFAULT_NORMAL_ANGLE = 10.0


@dataclass(eq=False)
class Project:
    name: str = ""                       # shown for the loaded meshes
    surface: Mesh | None = None          # input data: gets meshed, partitions refer to its triangles
    # Connected components of the surface (label per triangle, 0 = largest)
    # and which of them get meshed
    surface_components: np.ndarray | None = None
    meshed_components: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    volume: Mesh | None = None           # tet mesh (loaded or meshed)
    # Per volume boundary triangle: the surface triangle whose partition it gets
    volume_face_map: np.ndarray | None = None
    background: Mesh | None = None       # bounding box for fTetWild's sizing field
    partitions: Partitions = field(default_factory=Partitions)
    normal_angle: float = DEFAULT_NORMAL_ANGLE   # face-region angle of the selection tool
    # Original input file, embedded in saved projects so they are self-contained
    source_name:  str = ""
    source_bytes: bytes | None = None
    # Parameters of the last mesher run (saved in the project, prefilled in the UI)
    mesher_name:   str = ""
    mesher_params: dict = field(default_factory=dict)

    def start(self, name: str, surface: Mesh, source_path: str | None = None):
        """Replace everything with a new input surface. With source_path the
        input file is embedded; without it the previous source is kept."""
        self.name = name
        self.surface, self.volume, self.volume_face_map, self.background = surface, None, None, None
        self.set_components(component_labels(surface.triangles))
        if source_path is not None:
            p = Path(source_path)
            self.source_name, self.source_bytes = p.name, p.read_bytes()
            self.mesher_name, self.mesher_params = "", {}
        self.partitions.reset(len(surface.triangles))

    def set_components(self, labels, meshed=None):
        """Component label per surface triangle; meshed: bool per component
        (default: all)."""
        self.surface_components = np.asarray(labels, dtype=np.int32).ravel()
        n = int(self.surface_components.max()) + 1 if len(self.surface_components) else 0
        self.meshed_components = (np.ones(n, dtype=bool) if meshed is None
                                  else np.asarray(meshed, dtype=bool).ravel().copy())
        if len(self.meshed_components) != n:
            raise ValueError(f"{len(self.meshed_components)} meshed flags for {n} components")

    def meshed_faces(self) -> np.ndarray:
        """Surface triangles of the components that get meshed."""
        if self.surface_components is None:
            return np.zeros(0, dtype=np.int64)
        return np.flatnonzero(self.meshed_components[self.surface_components])

    def set_volume(self, volume: Mesh, face_map):
        """Tet mesh of the surface; face_map: surface triangle per volume
        boundary triangle (how the partitions carry over)."""
        face_map = np.asarray(face_map, dtype=np.int64).ravel()
        if len(face_map) != len(volume.triangles):
            raise ValueError(f"face map has {len(face_map)} entries for "
                             f"{len(volume.triangles)} volume boundary triangles")
        self.volume, self.volume_face_map = volume, face_map

    def volume_partition_ids(self) -> np.ndarray | None:
        """Partition id per volume boundary triangle (None: no partitions)."""
        ids = self.partitions.ids_per_cell()
        if ids is None or self.volume_face_map is None:
            return None
        return ids[self.volume_face_map]

    def can_export_volume(self) -> bool:
        return (self.volume is not None and self.volume.has_tetrahedra
                and len(self.volume.triangles) > 0)
