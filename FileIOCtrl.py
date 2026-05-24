from pathlib import Path

from fileio.SurfaceMeshGeometryFile import TriangleSurfaceMeshGeometryFile
from fileio.VolumeMeshGeometryFile import TetrahedralVolumeMeshGeometryFile


class FileIOCtrl:
    def __init__(self):
        self.__loaded_file = None

    def __load_mesh_surface_geometry(self, path):
        self.__loaded_file = TriangleSurfaceMeshGeometryFile(path)

    def __load_mesh_volume_geometry(self, path):
        self.__loaded_file = TetrahedralVolumeMeshGeometryFile(path)

    def load_file(self, path:str):
        ext = Path(path).suffix
        if  ext in [".vol", ".msh"]:
            self.__load_mesh_volume_geometry(path)
        elif ext in [".obj", ".stl"]:
            self.__load_mesh_surface_geometry(path)

    def get_geometry(self):
        return self.__loaded_file
