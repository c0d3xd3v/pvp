from dataclasses import dataclass, field

from geometry.AbstractMeshData import AbstractGeometryData


@dataclass
class InMemoryMeshData(AbstractGeometryData):
    """Mesh geometry produced in memory (e.g. by a mesher) rather than read
    from a file. Carries no boundary-condition information."""
    vertices:   list = field(default_factory=list)   # [[x, y, z], ...]
    triangles:  list = field(default_factory=list)   # [[i, j, k], ...]
    tetrahedra: list = field(default_factory=list)   # [[i, j, k, l], ...]

    def get_vertices(self):   return self.vertices
    def get_triangles(self):  return self.triangles
    def get_tetrahedra(self): return self.tetrahedra
