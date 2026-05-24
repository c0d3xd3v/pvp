import vtk
import random
import numpy as np
import vtkmodules

class PointSetActor(vtk.vtkActor):
    def __init__(self):
        vtk.vtkActor.__init__(self)

        # Alle Punkte speichern
        self.all_points = None
        # Für selektierte Punkte
        self.point_selection = vtk.vtkPoints()
        self.verts = vtk.vtkCellArray()
        self.selected_point_ids = []  # Liste der selektierten Punkt-IDs

        self.polydata = vtk.vtkPolyData()
        self.polydata.SetPoints(self.point_selection)
        self.polydata.SetVerts(self.verts)

        self.mapper = vtk.vtkOpenGLSphereMapper()
        self.mapper.SetInputData(self.polydata)

        self.SetMapper(self.mapper)
        self.GetProperty().SetColor(1, 0, 0)
        self.GetProperty().SetPointSize(5)
        self.PickableOn()

    def setPoints(self, points):
        self.all_points = points
        # Zurücksetzen der Selektion, da IDs möglicherweise ungültig
        self.clearSelection()
        # Hier werden keine Punkte gerendert, da Selektion leer ist

    def setPointSize(self, point_size):
        self.mapper.SetRadius(point_size)
        self.polydata.Modified()
        self.mapper.Update()

    def selectPoints(self, point_ids):
        """Selektiert mehrere Punkte und zeigt diese an."""
        # Filtere ungültige IDs
        if self.all_points is None:
            self.selected_point_ids = []
        else:
            num_points = self.all_points.GetNumberOfPoints()
            valid_ids = [pid for pid in point_ids]
            self.selected_point_ids = valid_ids
        self.updateVisualization()
        print(f"Selected points: {len(self.selected_point_ids)}")

    def selectPoint(self, point_id):
        """Beibehaltung der alten Methode für Einzelselektion (optional)."""
        self.selectPoints([point_id] if point_id >= 0 else [])

    def clearSelection(self):
        """Löscht die Selektion (zeigt keine Punkte an)."""
        self.selected_point_ids = []
        self.updateVisualization()

    def updateVisualization(self):
        """Aktualisiert die Visualisierung basierend auf den selektierten Punkten."""
        self.point_selection = vtk.vtkPoints()
        self.verts = vtk.vtkCellArray()

        if self.selected_point_ids:
            # Punkte und Vertices hinzufügen
            for i, pid in enumerate(self.selected_point_ids):
                point = [0, 0, 0]
                self.all_points.GetPoint(pid, point)
                self.point_selection.InsertNextPoint(point)
                # Vertex für diesen Punkt erstellen
                self.verts.InsertNextCell(1)
                self.verts.InsertCellPoint(i)

        self.polydata.SetPoints(self.point_selection)
        self.polydata.SetVerts(self.verts)
        self.polydata.Modified()
        self.mapper.Update()

    def getSelectedPoints(self):
        """Gibt eine Liste der Koordinaten der selektierten Punkte zurück."""
        points = []
        for pid in self.selected_point_ids:
            point = [0, 0, 0]
            self.all_points.GetPoint(pid, point)
            points.append(point)
        return points

    def getSelectedPoint(self):
        """Gibt die Koordinaten des ersten selektierten Punktes zurück (oder None)."""
        if self.selected_point_ids:
            point = [0, 0, 0]
            self.all_points.GetPoint(self.selected_point_ids[0], point)
            return point
        return None

    def getSelectedPointIds(self):
        """Gibt die Liste der selektierten Punkt-IDs zurück."""
        return self.selected_point_ids

    def getSelectedPointId(self):
        """Gibt die erste selektierte Punkt-ID zurück (oder -1, falls keine)."""
        return self.selected_point_ids[0] if self.selected_point_ids else -1
