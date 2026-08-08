import numpy as np

from PySide6.QtCore import Slot
from PySide6.QtCore import QObject

import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from Visualization.vtk.ResultActor import ResultActor
from Visualization.vtk.FaceSelectionActor import FaceSelectionActor
from Visualization.vtk.PointSetActor import PointSetActor


class SceneCtrl(QObject):
    def __init__(self):
        super().__init__()
        self.__vtkitem = None
        self.__polydata = None
        self.__actor = None
        self.__result_actor = None
        self.__partition_id = 1
        self.__points_actor = None

    def __remove_all_actors(self):
        for actor in [self.__actor, self.__result_actor, self.__points_actor]:
            if actor is not None:
                self.__vtkitem.renderer.renderer.RemoveActor(actor)

    def __prepare_rendering(self):
        if self.__vtkitem and self.__polydata:
            self.__remove_all_actors()
            self.__result_actor = None
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

    def __prepare_result_rendering(self):
        if self.__vtkitem and self.__polydata:
            self.__remove_all_actors()
            self.__actor = None
            self.__points_actor = None
            self.__result_actor = ResultActor()
            self.__result_actor.setDataset(self.__polydata)
            self.__vtkitem.renderer.renderer.AddActor(self.__result_actor)
            self.__vtkitem.renderer.renderer.ResetCamera()
            self.__vtkitem.update()

    def add_result_geometry(self, data):
        self.__polydata = vtk.vtkPolyData()

        vertices = np.array(data.get_vertices())
        points_array = numpy_to_vtk(vertices, deep=True)

        _sf = np.array(data.get_triangles())
        nbpts = np.full(_sf.shape[0], 3)
        _sf = np.column_stack((nbpts, _sf))
        triangles_array = numpy_to_vtk(_sf, deep=True, array_type=vtk.VTK_ID_TYPE)

        points = vtk.vtkPoints()
        points.SetData(points_array)
        cells = vtk.vtkCellArray()
        cells.SetCells(triangles_array.GetNumberOfTuples(), triangles_array)

        self.__polydata.SetPoints(points)
        self.__polydata.SetPolys(cells)

        for name in data.get_field_names():
            field = np.array(data.get_vertex_field_data(name))
            vtk_array = numpy_to_vtk(field, deep=True)
            vtk_array.SetName(name)
            self.__polydata.GetPointData().AddArray(vtk_array)

        self.__prepare_result_rendering()

    def select_function(self, name):
        if self.__result_actor is not None:
            self.__result_actor.select_function(name)
            self.__vtkitem.update()

    def set_animation_time(self, t):
        if self.__result_actor is not None:
            self.__result_actor.setAnimationTime(t)
            self.__result_actor.updateAnimation()
            self.__vtkitem.update()

    def apply_vector_field_on_position(self, should_apply, scale):
        if self.__result_actor is not None:
            self.__result_actor.apply_vector_field_on_position(should_apply, scale)
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
