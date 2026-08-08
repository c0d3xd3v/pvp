import numpy as np

from PySide6.QtCore import Slot
from PySide6.QtCore import QObject

import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from Visualization.vtk.ResultActor import ResultActor
from Visualization.vtk.FaceSelectionActor import FaceSelectionActor
from Visualization.vtk.PointSetActor import PointSetActor


_CLIP_NORMALS = {
    "x":  (1, 0, 0), "-x": (-1, 0, 0),
    "y":  (0, 1, 0), "-y": (0, -1, 0),
    "z":  (0, 0, 1), "-z": (0, 0, -1),
}


class SceneCtrl(QObject):
    def __init__(self):
        super().__init__()
        self.__vtkitem = None
        self.__polydata = None
        self.__actor = None
        self.__result_actor = None
        self.__partition_id = 1
        self.__points_actor = None
        self.__role_actors: dict[str, vtk.vtkActor] = {}
        self.__clip_plane = vtk.vtkPlane()
        self.__clip_plane.SetNormal(1, 0, 0)
        self.__clip_plane.SetOrigin(0, 0, 0)
        self.__clip_rep = None
        self.__clip_widget = None
        self.__clipping_enabled = False
        self.__clip_axis_str = "x"
        self.__volume_ug = None
        self.__volume_clip_filter = None

    def __remove_all_actors(self):
        # Only clears the primary surface/result/points actors.
        # role_actors (volume, background) have their own lifecycle and persist
        # across surface reloads.
        for actor in [self.__actor, self.__result_actor, self.__points_actor]:
            if actor is not None:
                self.__vtkitem.renderer.renderer.RemoveActor(actor)

    def __add_role_actor(self, role: str, polydata: vtk.vtkPolyData,
                         color=(0.7, 0.7, 0.7), opacity=0.3, wireframe=True):
        if role in self.__role_actors:
            self.__vtkitem.renderer.renderer.RemoveActor(self.__role_actors[role])
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*color)
        prop.SetOpacity(opacity)
        if wireframe:
            prop.SetRepresentationToWireframe()
        self.__role_actors[role] = actor
        if self.__clipping_enabled:
            actor.GetMapper().AddClippingPlane(self.__clip_plane)
        self.__vtkitem.renderer.renderer.AddActor(actor)
        self.__vtkitem.update()

    def remove_role_actor(self, role: str):
        if role in self.__role_actors:
            self.__vtkitem.renderer.renderer.RemoveActor(self.__role_actors.pop(role))
            self.__vtkitem.update()

    def __prepare_rendering(self):
        if self.__vtkitem and self.__polydata:
            self.__remove_all_actors()
            self.__result_actor = None
            self.__actor = FaceSelectionActor()
            self.__points_actor = PointSetActor()
            partitions = [1]*(self.__polydata.GetNumberOfCells())
            self.__actor.setPolyData(self.__polydata, partitions)
            if self.__clipping_enabled:
                self.__actor.mapper.AddClippingPlane(self.__clip_plane)
            self.__vtkitem.renderer.renderer.AddActor(self.__actor)
            self.__vtkitem.renderer.renderer.AddActor(self.__points_actor)
            self.__vtkitem.renderer.renderer.ResetCamera()
            self.__reposition_clip_widget()
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
            if self.__clipping_enabled:
                self.__result_actor.GetMapper().AddClippingPlane(self.__clip_plane)
            self.__vtkitem.renderer.renderer.AddActor(self.__result_actor)
            self.__vtkitem.renderer.renderer.ResetCamera()
            self.__reposition_clip_widget()
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

    def __ensure_clip_widget(self):
        if self.__clip_widget is not None:
            self.__reposition_clip_widget()
            return
        interactor = self.__vtkitem.interactor

        self.__clip_rep = vtk.vtkImplicitPlaneRepresentation()
        self.__clip_rep.SetPlaceFactor(1.0)
        self.__clip_rep.DrawPlaneOff()
        self.__clip_rep.OutlineTranslationOff()
        self.__clip_rep.ScaleEnabledOff()
        # Hide arrow via opacity — survives EnabledOn() unlike VisibilityOff().
        for getter in ("GetNormalProperty", "GetSelectedNormalProperty"):
            if hasattr(self.__clip_rep, getter):
                getattr(self.__clip_rep, getter)().SetOpacity(0.0)

        self.__clip_widget = vtk.vtkImplicitPlaneWidget2()
        self.__clip_widget.SetInteractor(interactor)
        self.__clip_widget.SetRepresentation(self.__clip_rep)
        self.__clip_widget.AddObserver("InteractionEvent", self.__on_clip_widget_interaction)
        self.__clip_widget.AddObserver("EndInteractionEvent", self.__on_clip_widget_end)

        self.__reposition_clip_widget()

    def __hide_clip_sphere(self):
        if self.__clip_rep is None:
            return
        _normal_prop = self.__clip_rep.GetNormalProperty()
        _actors = vtk.vtkActorCollection()
        self.__clip_rep.GetActors(_actors)
        _actors.InitTraversal()
        _a = _actors.GetNextActor()
        while _a:
            _p = _a.GetProperty()
            # Sphere actor: has its own non-None property (not NormalProperty) and non-flat 3D bounds
            if _p is not None and _p is not _normal_prop:
                _b = _a.GetBounds()
                if _b and all(_b[2*i+1] > _b[2*i] for i in range(3)):
                    _a.VisibilityOff()
            _a = _actors.GetNextActor()

    def __reposition_clip_widget(self):
        if self.__clip_rep is None:
            return
        renderer = self.__vtkitem.renderer.renderer
        bounds = renderer.ComputeVisiblePropBounds()
        if bounds[0] < bounds[1]:
            self.__clip_rep.PlaceWidget(bounds)
            center = [(bounds[i * 2] + bounds[i * 2 + 1]) / 2.0 for i in range(3)]
            self.__clip_rep.SetOrigin(center)
        self.__clip_rep.SetNormal(*self.__clip_plane.GetNormal())
        self.__clip_rep.GetPlane(self.__clip_plane)

    def __on_clip_widget_interaction(self, obj, event):
        self.__clip_rep.GetPlane(self.__clip_plane)

    def __on_clip_widget_end(self, obj, event):
        if self.__clip_rep is not None:
            self.__clip_rep.SetInteractionState(0)

    def __apply_clip_planes(self):
        if self.__actor:
            self.__actor.mapper.AddClippingPlane(self.__clip_plane)
        for role, actor in self.__role_actors.items():
            if role == "volume" and self.__volume_clip_filter is not None:
                # Whole-tet clipping via cell filter, not planar mapper clip
                actor.GetMapper().SetInputConnection(self.__volume_clip_filter.GetOutputPort())
            else:
                actor.GetMapper().AddClippingPlane(self.__clip_plane)
        if self.__result_actor:
            self.__result_actor.GetMapper().AddClippingPlane(self.__clip_plane)

    def __remove_clip_planes(self):
        if self.__actor:
            self.__actor.mapper.RemoveAllClippingPlanes()
        for role, actor in self.__role_actors.items():
            if role == "volume" and self.__volume_ug is not None:
                actor.GetMapper().SetInputData(self.__volume_ug)
            else:
                actor.GetMapper().RemoveAllClippingPlanes()
        if self.__result_actor:
            self.__result_actor.GetMapper().RemoveAllClippingPlanes()

    def __sync_interactor_clip_state(self):
        self.__vtkitem.mouse_interactor.clip_mode = self.__clipping_enabled

    @Slot(bool)
    def setClippingEnabled(self, enabled: bool):
        self.__clipping_enabled = enabled
        if enabled:
            self.__ensure_clip_widget()
            self.__apply_clip_planes()
            self.__clip_widget.EnabledOn()
            self.__hide_clip_sphere()
        else:
            self.__remove_clip_planes()
            if self.__clip_widget:
                self.__clip_widget.EnabledOff()
        self.__sync_interactor_clip_state()
        self.__vtkitem.update()

    @Slot(str)
    def setClipAxis(self, axis: str):
        if axis not in _CLIP_NORMALS:
            return
        self.__clip_axis_str = axis
        normal = _CLIP_NORMALS[axis]
        self.__clip_plane.SetNormal(*normal)
        if self.__clip_rep is not None:
            self.__clip_rep.SetNormal(*normal)
            self.__clip_rep.Modified()
        if self.__clipping_enabled:
            self.__sync_interactor_clip_state()
        if self.__vtkitem:
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
        if self.__actor is None:
            return
        if toogle:
            self.__actor.enableEdges()
        else:
            self.__actor.disableEdges()
        self.__vtkitem.update()

    def add_volume_geometry(self, vertices, triangles):
        polydata = self.__build_polydata(vertices, triangles)
        self.__add_role_actor("volume", polydata, color=(0.4, 0.6, 1.0), opacity=0.25, wireframe=True)

    def add_volume_unstructured_mesh(self, vertices, tetrahedra):
        pts = vtk.vtkPoints()
        pts.SetData(numpy_to_vtk(np.array(vertices, dtype=np.float64), deep=True))

        ug = vtk.vtkUnstructuredGrid()
        ug.SetPoints(pts)

        tets = np.array(tetrahedra, dtype=np.int64)
        npts = np.full(len(tets), 4, dtype=np.int64)
        connectivity = np.column_stack((npts, tets)).ravel()
        ca = vtk.vtkCellArray()
        ca.SetCells(len(tets), numpy_to_vtk(connectivity, deep=True, array_type=vtk.VTK_ID_TYPE))
        ug.SetCells(vtk.VTK_TETRA, ca)

        self.__volume_ug = ug
        # Whole-tet clipping: keep only cells fully on the "keep" side of the plane.
        # ExtractInside=Off matches mapper.AddClippingPlane convention
        # (mapper keeps the +normal side; ExtractInsideOn would keep -normal).
        extract = vtk.vtkExtractGeometry()
        extract.SetInputData(ug)
        extract.SetImplicitFunction(self.__clip_plane)
        extract.ExtractInsideOff()
        extract.ExtractBoundaryCellsOff()
        self.__volume_clip_filter = extract

        if "volume" in self.__role_actors:
            self.__vtkitem.renderer.renderer.RemoveActor(self.__role_actors.pop("volume"))

        mapper = vtk.vtkDataSetMapper()
        if self.__clipping_enabled:
            mapper.SetInputConnection(extract.GetOutputPort())
        else:
            mapper.SetInputData(ug)
        # Push volume slightly back to avoid z-fighting with the coincident surface mesh
        mapper.SetResolveCoincidentTopologyToPolygonOffset()
        mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(2.0, 2.0)
        mapper.SetRelativeCoincidentTopologyLineOffsetParameters(2.0, 2.0)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(0.4, 0.6, 1.0)
        prop.SetOpacity(1.0)
        prop.EdgeVisibilityOn()
        prop.SetEdgeColor(0.15, 0.25, 0.4)
        self.__role_actors["volume"] = actor
        self.__vtkitem.renderer.renderer.AddActor(actor)
        self.__vtkitem.update()

    def add_background_geometry(self, polydata: vtk.vtkPolyData):
        self.__add_role_actor("background", polydata, color=(0.2, 0.9, 0.3), opacity=0.4, wireframe=True)

    def __build_polydata(self, vertices, triangles) -> vtk.vtkPolyData:
        polydata = vtk.vtkPolyData()
        points_array = numpy_to_vtk(np.array(vertices), deep=True)
        _sf = np.array(triangles)
        nbpts = np.full(_sf.shape[0], 3)
        _sf = np.column_stack((nbpts, _sf))
        triangles_array = numpy_to_vtk(_sf, deep=True, array_type=vtk.VTK_ID_TYPE)
        points = vtk.vtkPoints()
        points.SetData(points_array)
        cells = vtk.vtkCellArray()
        cells.SetCells(triangles_array.GetNumberOfTuples(), triangles_array)
        polydata.SetPoints(points)
        polydata.SetPolys(cells)
        return polydata
