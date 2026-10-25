"""The pre-processing project: the meshes, their boundary partitions and the
settings that belong to them (what a .pvp file stores)."""
from dataclasses import dataclass, field
from pathlib import Path

from pvp.model.mesh import Mesh
from pvp.model.partitions import Partitions

DEFAULT_NORMAL_ANGLE = 10.0


@dataclass(eq=False)
class Project:
    name: str = ""                       # shown for the loaded meshes
    surface: Mesh | None = None          # main geometry; partitions refer to its triangles
    volume: Mesh | None = None           # tet mesh (loaded or meshed); its boundary is `surface`
    background: Mesh | None = None       # bounding box for fTetWild's sizing field
    partitions: Partitions = field(default_factory=Partitions)
    normal_angle: float = DEFAULT_NORMAL_ANGLE   # face-region angle of the selection tool
    # Original input file, embedded in saved projects so they are self-contained
    source_name:  str = ""
    source_bytes: bytes | None = None
    # Parameters of the last mesher run (saved in the project, prefilled in the UI)
    mesher_name:   str = ""
    mesher_params: dict = field(default_factory=dict)

    def start(self, name: str, surface: Mesh, volume: Mesh | None = None,
              source_path: str | None = None):
        """Replace everything with a new geometry. With source_path the input
        file is embedded; without it the previous source is kept (meshing a
        geometry keeps its origin)."""
        self.name = name
        self.surface, self.volume, self.background = surface, volume, None
        if source_path is not None:
            p = Path(source_path)
            self.source_name, self.source_bytes = p.name, p.read_bytes()
            self.mesher_name, self.mesher_params = "", {}
        self.partitions.reset(len(surface.triangles))

    def can_export_volume(self) -> bool:
        return (self.volume is not None and self.volume.has_tetrahedra
                and len(self.volume.triangles) > 0)
