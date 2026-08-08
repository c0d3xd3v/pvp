import ngsolve as ngs
import netgen.meshing as nm
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
        self.__surface_partitions = None
        self.__partition_names = None
        self.__read_mesh_file(path)

    def __read_mesh_file(self, file_path:str):
        if file_path.endswith(".vol"):
            ngs_mesh = ngs.Mesh(file_path)
            self.__vertices = [[p[0], p[1], p[2]] for p in ngs_mesh.ngmesh.Points()]
            self.__triangles = [(t[0][0:3] - 1).tolist() for t in np.array(ngs_mesh.ngmesh.Elements2D())]
            self.__tetraedras = [(t[0][0:4] - 1).tolist() for t in np.array(ngs_mesh.ngmesh.Elements3D())]
        elif file_path.endswith(".msh"):
            mesh = meshio.read(file_path)
            self.__vertices = mesh.points.tolist()
            self.__triangles = mesh.cells_dict["triangle"].tolist()
            self.__tetraedras = mesh.cells_dict["tetra"].tolist()

    def __addSurfaceFromLists(self, fds, mesh, pmap, tris):
        for i, tri in enumerate(tris):
            vindices = [pmap[v] for v in tri]
            T = nm.Element2D(fds, vindices)
            mesh.Add(T)
        return mesh

    def __addVolumeFromLists(self, index, mesh, pmap, tets):
        for i, tet in enumerate(tets):
            vindices = [pmap[v] for v in tet]
            vindices[2], vindices[3] = vindices[3], vindices[2]
            T = nm.Element3D(index, vindices)
            mesh.Add(T)
        return mesh

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

    def get_tetrahedra(self):
        return self.__tetraedras

    def saveNgSolveMesh(self, file_name):
        # Aufbau der Netgen-Mesh
        mesh = nm.Mesh()
        pmap = {}
        for i, p in enumerate(self.__vertices):
            mp = nm.MeshPoint(nm.Point3d(p[0], p[1], p[2]))
            pmap[i] = mesh.Add(mp)

        for i, partition in enumerate(self.__surface_partitions):
            indices = [self.__triangles[k] for k in partition]
            fds = mesh.Add(nm.FaceDescriptor(bc=i+1, domin=0, surfnr=0))
            mesh = self.__addSurfaceFromLists(fds, mesh, pmap, indices)
            partition_name = self.__partition_names[i]
            print(i+1, partition_name)
            mesh.SetBCName(i+1, partition_name)

        mesh = self.__addVolumeFromLists(0, mesh, pmap, self.__tetraedras)
        mesh.Update()
        mesh.Save(file_name)
