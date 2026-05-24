import numpy as np

from PySide6.QtCore import Slot
from PySide6.QtCore import Signal
from PySide6.QtCore import QObject

from geometry.TriangleMeshGraph import TriangleMeshGraph


class MeshCtrl(QObject):
    update_partition = Signal(list, int)
    mesh_geometry_modified = Signal()

    def __init__(self):
        super().__init__()
        self.__surfaceTriangleMeshGraph = None

    def load_geometry(self, polydata):
        self.__surfaceTriangleMeshGraph = None
        self.__surfaceTriangleMeshGraph = TriangleMeshGraph(polydata)
        self.set_normal_compare_angle(10.0)

    def set_normal_compare_angle(self, angle):
        if self.__surfaceTriangleMeshGraph is not None:
            self.__surfaceTriangleMeshGraph.set_normal_compare_angle(angle)

    @Slot()
    def center_to_geometric_center(self):
        gc = self.__surfaceTriangleMeshGraph.compute_geometric_center()
        self.__surfaceTriangleMeshGraph.translate_mesh(np.array([gc]))
        self.mesh_geometry_modified.emit()

    def face_selected(self, face_id):
        self.__surfaceTriangleMeshGraph.reset()
        flat_faces = self.__surfaceTriangleMeshGraph.BFS(face_id)
        self.update_partition.emit(flat_faces, 0)
        '''
        sf = self.face_selection_actor.get_selected_faces()
        uf = self.face_selection_actor.get_unselected_faces()
        self.mesh_file.clear_surface_partition()
        self.mesh_file.add_surface_partition(uf, "fixed")
        self.mesh_file.add_surface_partition(sf, "default")
        self.mesh_file.saveNgSolveMesh("test.vol")
        '''