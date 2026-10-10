import numpy as np

from PySide6.QtCore import Slot
from PySide6.QtCore import QObject

import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from visualization.vtk.ResultActor import ResultActor
from visualization.vtk.FaceSelectionActor import FaceSelectionActor
from visualization.vtk.BoundaryPartitions import BoundaryPartitions
from visualization.vtk.ClipPlane import ClipPlane


def _triangle_polydata(vertices, triangles) -> vtk.vtkPolyData:
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.asarray(vertices, dtype=np.float64), deep=True))
    tris = np.asarray(triangles, dtype=np.int64)
    conn = np.column_stack((np.full(len(tris), 3, dtype=np.int64), tris)).ravel()
    cells = vtk.vtkCellArray()
    cells.SetCells(len(tris), numpy_to_vtk(conn, deep=True, array_type=vtk.VTK_ID_TYPE))
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(cells)
    return polydata


class SceneCtrl(QObject):
    """Owns the VTK actors of the scene (surface, volume/background roles,
    result) and decides which of them the clip plane applies to.

    Boundary-condition partitions live in `self.partitions`, the clip plane
    and its widget in `self.__clip`.
    """

    def __init__(self):
        super().__init__()
        self.__vtkitem = None
        self.__polydata = None
        self.__actor = None            # FaceSelectionActor of the surface (pre-processing)
        self.__result_actor = None
        self.__role_actors: dict[str, vtk.vtkActor] = {}
        self.__volume_ug = None
        self.__volume_clip_filter = None
        self.__clip = ClipPlane()
        self.partitions = BoundaryPartitions(request_render=self.__render)

    def set_vtk_item(self, vtkitem):
        self.__vtkitem = vtkitem
        self.__clip.attach(vtkitem)
        self.__vtkitem.rendererInitialized.connect(self.__prepare_rendering)

    def __render(self):
        if self.__vtkitem is not None:
            self.__vtkitem.update()

    def __renderer(self) -> vtk.vtkRenderer:
        return self.__vtkitem.renderer.renderer

    # --- actors ----------------------------------------------------------

    def __remove_all_actors(self):
        for actor in [self.__actor, self.__result_actor, *self.__role_actors.values()]:
            if actor is not None:
                self.__renderer().RemoveActor(actor)
        self.__role_actors.clear()
        self.__volume_ug = None
        self.__volume_clip_filter = None

    def __add_role_actor(self, role: str, polydata: vtk.vtkPolyData,
                         color=(0.7, 0.7, 0.7), opacity=0.3, wireframe=True):
        if role in self.__role_actors:
            self.__renderer().RemoveActor(self.__role_actors[role])
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
        if self.__clip.enabled:
            mapper.AddClippingPlane(self.__clip.plane)
        self.__renderer().AddActor(actor)
        self.__render()

    def clear_result_actor(self):
        if self.__result_actor is not None:
            self.__renderer().RemoveActor(self.__result_actor)
            self.__result_actor = None
            self.__render()

    def __prepare_rendering(self):
        if self.__vtkitem and self.__vtkitem.renderer and self.__polydata:
            self.__remove_all_actors()
            self.__result_actor = None
            self.__actor = FaceSelectionActor()
            # All cells start as unassigned (partition id 0)
            self.__actor.setPolyData(self.__polydata,
                                     np.zeros(self.__polydata.GetNumberOfCells(), dtype=np.int32))
            self.partitions.attach(self.__actor)
            if self.__clip.enabled:
                self.__actor.mapper.AddClippingPlane(self.__clip.plane)
            self.__renderer().AddActor(self.__actor)
            self.__renderer().ResetCamera()
            self.__clip.reposition()
            self.__vtkitem.setSeletableActor(self.__actor)
            self.__render()

    def add_surface_geometry(self, vertices, triangles):
        self.__polydata = _triangle_polydata(vertices, triangles)
        self.__prepare_rendering()
        return self.__polydata

    def add_volume_geometry(self, vertices, triangles):
        self.__add_role_actor("volume", _triangle_polydata(vertices, triangles),
                              color=(0.4, 0.6, 1.0), opacity=0.25, wireframe=True)

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
        self.__volume_clip_filter = self.__clip.volume_filter(ug)

        if "volume" in self.__role_actors:
            self.__renderer().RemoveActor(self.__role_actors.pop("volume"))

        mapper = vtk.vtkDataSetMapper()
        if self.__clip.enabled:
            mapper.SetInputConnection(self.__volume_clip_filter.GetOutputPort())
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
        self.__renderer().AddActor(actor)
        self.__render()

    def add_background_geometry(self, polydata: vtk.vtkPolyData):
        self.__add_role_actor("background", polydata, color=(0.2, 0.9, 0.3), opacity=0.4, wireframe=True)

    def interactive_select(self, face_ids, partition_id):
        self.partitions.assign_faces(face_ids, partition_id)

    @Slot(bool)
    def toogleWireframe(self, toogle):
        if self.__actor is None:
            return
        if toogle:
            self.__actor.enableEdges()
        else:
            self.__actor.disableEdges()
        self.__render()

    # --- results ---------------------------------------------------------

    def __prepare_result_rendering(self):
        if self.__vtkitem and self.__vtkitem.renderer and self.__polydata:
            self.__remove_all_actors()
            self.__actor = None
            self.partitions.detach()
            self.__result_actor = ResultActor()
            self.__result_actor.setDataset(self.__polydata)
            if self.__clip.enabled:
                self.__result_actor.GetMapper().AddClippingPlane(self.__clip.plane)
            self.__renderer().AddActor(self.__result_actor)
            self.__renderer().ResetCamera()
            self.__clip.reposition()
            self.__render()

    def add_result_geometry(self, data):
        self.__polydata = _triangle_polydata(data.get_vertices(), data.get_triangles())
        for name in data.get_field_names():
            vtk_array = numpy_to_vtk(np.array(data.get_vertex_field_data(name)), deep=True)
            vtk_array.SetName(name)
            self.__polydata.GetPointData().AddArray(vtk_array)
        self.__prepare_result_rendering()

    def select_function(self, name):
        if self.__result_actor is not None:
            self.__result_actor.select_function(name)
            self.__render()

    def set_animation_time(self, t):
        if self.__result_actor is not None:
            self.__result_actor.setAnimationTime(t)
            self.__result_actor.updateAnimation()
            self.__render()

    def apply_vector_field_on_position(self, should_apply, scale):
        if self.__result_actor is not None:
            self.__result_actor.apply_vector_field_on_position(should_apply, scale)
            self.__render()

    # --- clipping --------------------------------------------------------

    def __apply_clip_planes(self):
        if self.__actor:
            self.__actor.mapper.AddClippingPlane(self.__clip.plane)
        for role, actor in self.__role_actors.items():
            if role == "volume" and self.__volume_clip_filter is not None:
                # Whole-tet clipping via cell filter, not planar mapper clip
                actor.GetMapper().SetInputConnection(self.__volume_clip_filter.GetOutputPort())
            else:
                actor.GetMapper().AddClippingPlane(self.__clip.plane)
        if self.__result_actor:
            self.__result_actor.GetMapper().AddClippingPlane(self.__clip.plane)

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

    @Slot(bool)
    def setClippingEnabled(self, enabled: bool):
        self.__clip.set_enabled(enabled)
        if enabled:
            self.__apply_clip_planes()
        else:
            self.__remove_clip_planes()
        self.__render()

    @Slot(str)
    def setClipAxis(self, axis: str):
        if self.__clip.set_axis(axis):
            self.__render()
