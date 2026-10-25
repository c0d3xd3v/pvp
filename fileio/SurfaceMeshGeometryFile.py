import numpy as np
import locale

from geometry.AbstractMeshData import AbstractGeometryData


class TriangleSurfaceMeshGeometryFile(AbstractGeometryData):
    def __init__(self, path: str, scale: float = 1.0):
        self.__path = path
        self.__vertices = None
        self.__triangles = None
        self.__read_mesh_file(path, scale)

    def __read_mesh_file(self, file_path: str, scale: float):
        import igl      # ~0.3 s; only needed once a surface file is opened
        old_locale = locale.getlocale(locale.LC_NUMERIC)
        locale.setlocale(locale.LC_NUMERIC, "C")
        sv, sf = igl.read_triangle_mesh(file_path)
        (SV, SVI, SVJ, SF) = igl.remove_duplicate_vertices(sv, sf, epsilon=1e-7)
        locale.setlocale(locale.LC_NUMERIC, old_locale)
        if scale != 1.0:
            # STL/OBJ files carry no unit metadata; the user picks the source
            # unit at load time and we convert to mm here, so every downstream
            # consumer (edge-length UI, meshers, writers) sees mm.
            SV = SV * float(scale)
        self.__triangles, self.__vertices = SF, SV

    def get_vertices(self):
        return self.__vertices

    def get_triangles(self):
        return self.__triangles

