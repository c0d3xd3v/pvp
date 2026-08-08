from dataclasses import dataclass, field
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
