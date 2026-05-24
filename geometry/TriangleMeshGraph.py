from collections import deque
from typing import List, Optional, Dict, Set, Tuple
import sys
import igl
import numpy as np

from geometry.ConditionalGraph import ConditionalGraph
from geometry.ConditionalGraph import GraphCompareCondition

import vtk
from vtk.util.numpy_support import vtk_to_numpy
from vtk.util.numpy_support import numpy_to_vtk

class TriangleMeshCompareCondition(GraphCompareCondition):
    """Condition für Triangle Meshes basierend auf Normalen"""
    def __init__(self, vertices, faces, angle_threshold=2.0):
        self.vertices = vertices
        self.faces = faces
        self.angle_threshold = angle_threshold
        self._normals_cache = None
        self.compute_all_normals()

    def compute_all_normals(self):
        """Berechnet alle Face-Normalen auf einmal (schneller)"""
        if self._normals_cache is None:
            v0 = self.vertices[self.faces[:, 0]]
            v1 = self.vertices[self.faces[:, 1]]
            v2 = self.vertices[self.faces[:, 2]]

            v01 = v1 - v0
            v02 = v2 - v0

            normals = np.cross(v01, v02)
            norms = np.linalg.norm(normals, axis=1, keepdims=True)
            norms[norms == 0] = 1.0  # Vermeide Division durch 0
            self._normals_cache = normals / norms

        return self._normals_cache

    def compare(self, f1: int, f2: int) -> bool:
        """Vergleicht zwei Faces anhand ihrer Normalen"""
        normals = self.compute_all_normals()
        n1 = normals[f1]
        n2 = normals[f2]

        dot_product = np.clip(np.dot(n1, n2), -1.0, 1.0)
        angle = np.degrees(np.arccos(dot_product))
        #print(angle, self.angle_threshold, (angle < self.angle_threshold))
        return angle < self.angle_threshold

class TriangleMeshGraph(ConditionalGraph):
    """Spezialisierter Graph für Triangle Meshes mit Partitionierung"""

    def __init__(self, polydata):
        """
        Args:
            vertices: numpy array der Vertices (Nx3)
            faces: numpy array der Faces (Mx3)
            condition: Optional comparison condition
        """
        self.polydata = polydata
        self.condition = None
        self.vertices = None
        self.faces = None
        self.point_to_faces = None
        # Angenommen, du hast ein vtkPolyData-Objekt namens 'polydata'
        points = polydata.GetPoints()
        if points:
            self.vertices = vtk_to_numpy(points.GetData())  # N x 3 Array

        polys = polydata.GetPolys()
        if polys and polys.GetNumberOfCells() > 0:
            cell_data = vtk_to_numpy(polys.GetData())
            self.faces = cell_data.reshape(-1, 4)[:, 1:4]

        self.num_faces = len(self.faces)
        print(f'faces : {self.num_faces}')

        # Parent constructor aufrufen
        self.condition = None
        self.condition = TriangleMeshCompareCondition(self.vertices, self.faces)
        super().__init__(self.num_faces, self.condition)

        # Adjazenzliste aus Mesh erstellen
        self.build_adjacency_from_mesh()
        self.build_point_to_faces()

    def build_adjacency_from_mesh(self):
        """Baut Adjazenzliste aus Triangle Mesh"""
        # Dictionary für Edge->Faces Mapping
        edge_to_faces = {}

        # Für jede Face
        for face_idx, face in enumerate(self.faces):
            # Alle Kanten der Face
            edges = [
                tuple(sorted((face[0], face[1]))),
                tuple(sorted((face[1], face[2]))),
                tuple(sorted((face[2], face[0])))
            ]

            # Jede Karte zur aktuellen Face hinzufügen
            for edge in edges:
                if edge not in edge_to_faces:
                    edge_to_faces[edge] = []
                edge_to_faces[edge].append(face_idx)

        # Adjazenzliste erstellen
        for face_list in edge_to_faces.values():
            if len(face_list) == 2:
                # Zwei Faces teilen sich eine Kante (Nachbarn)
                f1, f2 = face_list
                self.add_edge(f1, f2)
                self.add_edge(f2, f1)
            elif len(face_list) > 2:
                # Mehr als 2 Faces teilen eine Kante (selten, aber möglich)
                for i in range(len(face_list)):
                    for j in range(i + 1, len(face_list)):
                        self.add_edge(face_list[i], face_list[j])
                        self.add_edge(face_list[j], face_list[i])

    def build_point_to_faces(self):
        num_points = len(self.vertices)
        self.point_to_faces = [[] for _ in range(num_points)]
        for face_idx, tri in enumerate(self.faces):
            for v in tri:
                self.point_to_faces[v].append(face_idx)

    def set_normal_compare_angle(self, angle):
        self.condition.angle_threshold = angle

    def compute_geometric_center(self) -> np.ndarray:
        """
        Berechnet das geometrische Zentrum als arithmetisches Mittel aller Vertices.

        Returns:
            np.ndarray: (x, y, z) Koordinaten des Zentrums.
        """
        if self.vertices is None or len(self.vertices) == 0:
            raise ValueError("Keine Vertices vorhanden.")
        return np.mean(self.vertices, axis=0)

    def translate_mesh(self, displacement):
        print(f'displacement : {displacement.shape}')
        print(f'self.vertices : {self.vertices.shape}')
        np.subtract(self.vertices, displacement, out=self.vertices)
        vtk_points = vtk.vtkPoints()
        vtk_points.SetData(numpy_to_vtk(self.vertices))
        print(vtk_points)
        self.polydata.SetPoints(vtk_points)
