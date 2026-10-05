import ngsolve as ngs
import numpy as np

from geometry.AbstractMeshData import AbstractGeometryData


class TetrahedralVolumeMeshGeometryFile(AbstractGeometryData):
    '''
    '''
    def __init__(self, path:str):
        self.__path = path
        self.__vertices = None
        self.__triangles = None
        self.__tetraedras = None
        self.__triangle_bcs = []      # per-triangle BC index (1-based), aligned with __triangles
        self.__bc_names: dict[int, str] = {}  # bc_index -> user-facing name
        self.__read_mesh_file(path)

    def __read_mesh_file(self, file_path:str):
        if file_path.endswith(".vol"):
            ngs_mesh = ngs.Mesh(file_path)
            ngmesh = ngs_mesh.ngmesh
            self.__vertices = [[p[0], p[1], p[2]] for p in ngmesh.Points()]

            # Vertex indices via numpy (PointId is not directly int-castable)
            els_arr = np.array(ngmesh.Elements2D())
            self.__triangles = [(row[0][0:3] - 1).tolist() for row in els_arr]

            # For BC lookup we need the FaceDescriptor.bc value, NOT el.index
            # directly — the latter is the FD index which is not guaranteed to
            # equal the bc number (e.g. netgen may insert default FDs).
            self.__triangle_bcs = []
            fd_to_bc: dict[int, int] = {}
            for el in ngmesh.Elements2D():
                fd_idx = int(el.index)
                if fd_idx not in fd_to_bc:
                    try:
                        fd_to_bc[fd_idx] = int(ngmesh.GetFaceDescriptor(fd_idx).bc)
                    except Exception:
                        fd_to_bc[fd_idx] = fd_idx
                self.__triangle_bcs.append(fd_to_bc[fd_idx])

            self.__tetraedras = [(t[0][0:4] - 1).tolist() for t in np.array(ngmesh.Elements3D())]

            # BC name mapping keyed by bc number. Query per unique bc so we don't
            # rely on the ordering of GetBoundaries() vs FaceDescriptor list.
            try:
                boundaries = ngs_mesh.GetBoundaries()
                for i, name in enumerate(boundaries):
                    self.__bc_names[i + 1] = name
            except Exception:
                pass
        elif file_path.endswith(".msh"):
            mesh = meshio.read(file_path)
            self.__vertices = mesh.points.tolist()
            self.__triangles = mesh.cells_dict["triangle"].tolist()
            self.__tetraedras = mesh.cells_dict["tetra"].tolist()
            self.__triangle_bcs = [1] * len(self.__triangles)

    def get_vertices(self):
        return self.__vertices

    def get_triangles(self):
        return self.__triangles

    def get_tetrahedra(self):
        return self.__tetraedras

    def get_triangle_bcs(self):
        return self.__triangle_bcs

    def get_bc_names(self):
        return dict(self.__bc_names)
