from pvp.fileio.formats import file_kind
from pvp.fileio.SurfaceMeshGeometryFile import TriangleSurfaceMeshGeometryFile
from pvp.fileio.VolumeMeshGeometryFile import TetrahedralVolumeMeshGeometryFile
from pvp.fileio.MeshFieldFile import TriangleSurfaceMeshFieldFile

class FileIOCtrl:
    def __init__(self):
        self.__loaded_file = None

    def __load_mesh_surface_geometry(self, path, scale):
        self.__loaded_file = TriangleSurfaceMeshGeometryFile(path, scale=scale)

    def __load_mesh_volume_geometry(self, path):
        self.__loaded_file = TetrahedralVolumeMeshGeometryFile(path)

    def __load_mesh_surface_field(self, path):
        self.__loaded_file = TriangleSurfaceMeshFieldFile(path)

    def load_file(self, path: str, scale: float = 1.0):
        """`scale` applies to STL/OBJ only — those formats carry no units, so
        the UI picks one at open time and this converts to mm here."""
        kind = file_kind(path)
        if kind == "volume":
            self.__load_mesh_volume_geometry(path)
        elif kind == "surface":
            self.__load_mesh_surface_geometry(path, scale)
        elif kind == "result":
            self.__load_mesh_surface_field(path)

    def get_geometry(self):
        return self.__loaded_file
