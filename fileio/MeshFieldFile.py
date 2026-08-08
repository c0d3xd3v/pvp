import meshio
import numpy as np
import locale

from geometry.AbstractMeshData import AbstractResultData


class TriangleSurfaceMeshFieldFile(AbstractResultData):
    def __init__(self, path:str):
        self.__path = path
        self.__vertices = None
        self.__triangles = None
        self.__surface_fields = None
        self.__field_names = None
        self.__read_mesh_file(path)

    def __read_mesh_file(self, file_path:str):
        old_locale = locale.getlocale(locale.LC_NUMERIC)
        locale.setlocale(locale.LC_NUMERIC, "C")

        mesh = meshio.read(file_path)
        # Zugriff auf Daten
        SV = np.array(mesh.points)          # Koordinaten (N, 3)

        triangle_blocks = [cell.data for cell in mesh.cells if cell.type == "triangle"]
        
        if len(triangle_blocks) == 0:
            raise ValueError("No triangle cells found in mesh")
        elif len(triangle_blocks) == 1:
            SF = triangle_blocks[0]
        else:
            # Concatenate multiple triangle blocks
            SF = np.vstack(triangle_blocks)
        
        # Ensure SF is a proper 2D array of shape (N, 3)
        SF = np.asarray(SF, dtype=np.int64)

        daten = mesh.point_data       # Punktbezogene Daten (Dict)
        zell_daten = mesh.cell_data   # Zellbezogene Daten (Dict)

        print(f"Anzahl Punkte: {len(SV)}")
        self.__surface_fields = []
        self.__field_names = []
        for key in daten.keys():
            d = np.array(daten[key])
            print(f"Datenfeld: {key}, {d.shape}")
            self.__surface_fields.append(d)
            self.__field_names.append(key)

        print(len(self.__surface_fields))

        locale.setlocale(locale.LC_NUMERIC, old_locale)
        self.__triangles, self.__vertices = SF, SV

    def get_vertices(self):
        return self.__vertices

    def get_triangles(self):
        return self.__triangles

    def get_field_names(self):
        return self.__field_names

    def get_vertex_field_data(self, field_name: str):
        index = self.__field_names.index(field_name)
        return self.__surface_fields[index]
