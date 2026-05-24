import numpy as np

from PySide6.QtCore import Slot
from PySide6.QtCore import QObject

import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from Visualization.vtk.NgSolveResultActor import NgSolveResultActor
from Visualization.vtk.FaceSelectionActor import FaceSelectionActor
from Visualization.vtk.PointSetActor import PointSetActor


class SceneCtrl(QObject):
    def __init__(self):
        super().__init__()
        self.__vtkitem = None
        self.__polydata = None
        self.__actor = None
        self.__partition_id = 1
        self.__points_actor = None

    def __prepare_rendering(self):
        if self.__vtkitem and self.__polydata:
            self.__vtkitem.renderer.renderer.RemoveActor(self.__actor)
            self.__vtkitem.renderer.renderer.RemoveActor(self.__points_actor)
            self.__actor = FaceSelectionActor()
            self.__points_actor = PointSetActor()
            partitions = [1]*(self.__polydata.GetNumberOfCells())
            self.__actor.setPolyData(self.__polydata, partitions)
            self.__vtkitem.renderer.renderer.AddActor(self.__actor)
            self.__vtkitem.renderer.renderer.AddActor(self.__points_actor)
            self.__vtkitem.renderer.renderer.ResetCamera()
            self.__vtkitem.setSeletableActor(self.__actor)
            self.__vtkitem.update()

    def update_scene(self, polydata):
        self.__polydata = polydata
        partitions = [1]*(self.__polydata.GetNumberOfCells())
        self.__actor.setPolyData(self.__polydata, partitions)
        self.__actor.Modified()
        self.__polydata.Modified()

    def camera_look_at(self, point):
        cam = self.__vtkitem.renderer.renderer.GetActiveCamera()
        cam.SetFocalPoint(point)
        self.__vtkitem.update()

    def add_surface_geometry(self, vertices, triangles):

        self.__polydata = vtk.vtkPolyData()

        points_array = numpy_to_vtk(vertices, deep=True)

        _sf = np.array(triangles)
        nbpts = np.full(_sf.shape[0], 3)
        _sf = np.column_stack((nbpts, _sf))

        triangles_array = numpy_to_vtk(_sf, deep=True, array_type=vtk.VTK_ID_TYPE)

        points = vtk.vtkPoints()
        points.SetData(points_array)

        cells2 = vtk.vtkCellArray()
        cells2.SetCells(triangles_array.GetNumberOfTuples(), triangles_array)

        self.__polydata.SetPoints(points)
        self.__polydata.SetPolys(cells2)
        self.__prepare_rendering()

        return self.__polydata

    def interactive_select(self, data, partition_id):
        self.__actor.updatePartitions(data, partition_id)
        #self.__partition_id = self.__partition_id + 1
        #self.__actor.hide_selected()
        self.__vtkitem.update()

    def set_vtk_item(self, vtkitem):
        self.__vtkitem = vtkitem
        self.__vtkitem.rendererInitialized.connect(self.__prepare_rendering)

    def show_point(self, coords):
        pts = vtk.vtkPoints()
        pts.InsertNextPoint(coords)
        self.__points_actor.setPoints(pts)
        self.__points_actor.selectPoint(0)

    @Slot(bool)
    def toogleWireframe(self, toogle):
        if toogle:
            self.__actor.enableEdges()
        else:
            self.__actor.disableEdges()
        self.__vtkitem.update()
