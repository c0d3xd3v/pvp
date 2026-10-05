from dataclasses import dataclass, field


@dataclass
class InMemoryMeshData:
    """Lightweight mesh container for geometry produced in-memory (e.g. by a
    mesher). Implements the subset of the AbstractGeometryData interface that
    the scene/session code depends on. Export goes through
    fileio.NetgenVolWriter, like every other volume mesh.
    """
    vertices:   list = field(default_factory=list)   # [[x, y, z], ...]
    triangles:  list = field(default_factory=list)   # [[i, j, k], ...]
    tetrahedra: list = field(default_factory=list)   # [[i, j, k, l], ...]

    def get_vertices(self):   return self.vertices
    def get_triangles(self):  return self.triangles
    def get_tetrahedra(self): return self.tetrahedra
    def get_triangle_bcs(self): return []
    def get_bc_names(self):     return {}
