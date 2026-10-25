from dataclasses import dataclass, field
from pathlib import Path
from geometry.MeshRole import MeshRole
from geometry.AbstractMeshData import AbstractGeometryData


@dataclass
class PreProcMesh:
    role: MeshRole
    data: AbstractGeometryData
    name: str = ""


@dataclass
class PreProcSession:
    surface:    PreProcMesh | None = field(default=None)
    volume:     PreProcMesh | None = field(default=None)
    background: PreProcMesh | None = field(default=None)
    # Original input file, embedded in saved projects so they are self-contained
    source_name:  str = ""
    source_bytes: bytes | None = None
    # Parameters of the last mesher run (saved in the project, prefilled in the UI)
    mesher_name:   str = ""
    mesher_params: dict = field(default_factory=dict)

    def set_source(self, path: str):
        p = Path(path)
        self.source_name = p.name
        self.source_bytes = p.read_bytes()

    def set(self, mesh: PreProcMesh):
        if mesh.role == MeshRole.SURFACE:
            self.surface = mesh
        elif mesh.role == MeshRole.VOLUME:
            self.volume = mesh
        elif mesh.role == MeshRole.BACKGROUND:
            self.background = mesh

    def get(self, role: MeshRole) -> PreProcMesh | None:
        return {
            MeshRole.SURFACE:    self.surface,
            MeshRole.VOLUME:     self.volume,
            MeshRole.BACKGROUND: self.background,
        }[role]

    def clear(self, role: MeshRole):
        self.set(PreProcMesh(role=role, data=None, name=""))
