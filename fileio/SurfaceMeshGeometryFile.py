import igl
import numpy as np
import locale

from geometry.AbstractMeshData import AbstractGeometryData


class TriangleSurfaceMeshGeometryFile(AbstractGeometryData):
    def __init__(self, path:str):
        self.__path = path
        self.__vertices = None
        self.__triangles = None
        self.__surface_partitions = None
        self.__partition_names = None
        self.__read_mesh_file(path)

    def __read_mesh_file(self, file_path:str):
        old_locale = locale.getlocale(locale.LC_NUMERIC)
        locale.setlocale(locale.LC_NUMERIC, "C")
        sv, sf = igl.read_triangle_mesh(file_path)
        (SV, SVI, SVJ, SF) = igl.remove_duplicate_vertices(sv, sf, epsilon=1e-7)
        locale.setlocale(locale.LC_NUMERIC, old_locale)
        self.__triangles, self.__vertices = SF, SV

    def add_surface_partition(self, triangle_indices, partition_name):
        self.__partition_names.append(partition_name)
        self.__surface_partitions.append(triangle_indices)

    def clear_surface_partition(self):
        self.__partition_names = []
        self.__surface_partitions = []

    def get_vertices(self):
        return self.__vertices

    def get_triangles(self):
        return self.__triangles

