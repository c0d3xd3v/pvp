import vtk
from PySide6 import QtCore


class VTKMouseInteractorStyleQtSignals(QtCore.QObject):
    cell_picked = QtCore.Signal(int)
    cell_right_picked = QtCore.Signal(int)
    point_picked = QtCore.Signal(int)
    cell_hovered = QtCore.Signal(int)   # OriginalId under the cursor, -1 = none; on change only


class VTKMouseInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self):
        super().__init__()
        self.selectableActor = None
        self.mesh_polydata = None
        self.__pixel_ratio = 1.0
        self.clip_mode = False  # suppresses cell picking when clip widget is active
        self.qt_signals = VTKMouseInteractorStyleQtSignals()
        self.__surface_locator = None
        self.__hover_enabled = False          # on only while a partition is current
        self.__last_hovered_cell = -1
        self.AddObserver('LeftButtonPressEvent', self.left_button_press_event)
        self.AddObserver('RightButtonPressEvent', self.right_button_press_event)
        self.AddObserver('MouseMoveEvent', self.mouse_move_event)
        self.AddObserver('LeaveEvent', self.leave_event)

    def set_hover_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.__hover_enabled:
            return
        self.__hover_enabled = enabled
        if not enabled:
            self.__emit_hover(-1)

    def set_pixel_ratio(self, ratio):
        self.__pixel_ratio = ratio

    def setSelectableActor(self, actor, polydata=None):
        self.selectableActor = actor
        if polydata:
            self.mesh_polydata = polydata
        elif actor:
            mapper = actor.GetMapper()
            if mapper:
                self.mesh_polydata = mapper.GetInput()
        # Hover and click ray-cast a locator on the surface data. Deliberately no
        # long-lived vtkCellPicker with AddPickList(actor): it keeps a C++ ref to
        # the old FaceSelectionActor (a Python subclass) after a rebuild, which
        # corrupted VTK's Python object map and segfaulted after meshing.
        self.__surface_locator = None
        if actor is not None and self.mesh_polydata is not None:
            self.__surface_locator = vtk.vtkCellLocator()
            self.__surface_locator.SetDataSet(self.mesh_polydata)
            self.__surface_locator.BuildLocator()
        # -2: the next hover emits even if it lands on the same cell id of the new mesh
        self.__last_hovered_cell = -2
        self.qt_signals.cell_hovered.emit(-1)

    def left_button_press_event(self, obj, event):
        self.__emit_hover(-1)   # no stale overlay during a camera drag
        if self.GetInteractor().GetRepeatCount() > 0:
            self.center_on_picked_point()
            return      # no face selection, no rotation start for a double-click
        if not self.clip_mode:
            cell = self.__surface_cell_under_cursor()
            if cell != -1:
                self.qt_signals.cell_picked.emit(cell)
        self.OnLeftButtonDown()

    def right_button_press_event(self, obj, event):
        # Right-click = "unassign faces". We pick a cell and emit a dedicated
        # signal; we deliberately do NOT forward to OnRightButtonDown so the
        # trackball's dolly-on-drag doesn't fight the deselect. Zoom still
        # works via the mouse wheel.
        self.__emit_hover(-1)
        if self.clip_mode:
            return
        cell = self.__surface_cell_under_cursor()
        if cell != -1:
            self.qt_signals.cell_right_picked.emit(cell)

    def mouse_move_event(self, obj, event):
        # A Python observer on the style replaces VTK's built-in handler
        # instead of adding to it: without this the trackball stops rotating.
        self.OnMouseMove()
        if not self.__hover_enabled:
            return
        if self.clip_mode:
            self.__emit_hover(-1)
            return
        if self.GetState() != 0:
            return
        self.__emit_hover(self.__surface_cell_under_cursor())

    def __surface_cell_under_cursor(self) -> int:
        """Surface cell (OriginalId) under the cursor, or -1. Ray-casts only the
        selectable surface, so coincident actors (e.g. the tet volume after
        meshing) can't swallow the pick — hover and click always agree."""
        renderer = self.GetDefaultRenderer()
        if self.__surface_locator is None or renderer is None:
            return -1
        x, y = self.GetInteractor().GetEventPosition()
        near, far = (self.__display_to_world(renderer, x, y, z) for z in (0.0, 1.0))
        t, sub, cell = vtk.reference(0.0), vtk.reference(0), vtk.reference(-1)
        if not self.__surface_locator.IntersectWithLine(near, far, 0.0, t, [0.0] * 3, [0.0] * 3, sub, cell):
            return -1
        ids = self.mesh_polydata.GetCellData().GetArray("OriginalIds")
        return ids.GetValue(int(cell)) if ids else int(cell)

    @staticmethod
    def __display_to_world(renderer, x, y, z):
        renderer.SetDisplayPoint(x, y, z)
        renderer.DisplayToWorld()
        wx, wy, wz, w = renderer.GetWorldPoint()
        return [wx / w, wy / w, wz / w]

    def leave_event(self, obj, event):
        self.OnLeave()
        self.__emit_hover(-1)

    def __emit_hover(self, cell_id: int):
        if cell_id == self.__last_hovered_cell:
            return
        self.__last_hovered_cell = cell_id
        self.qt_signals.cell_hovered.emit(cell_id)

    def center_on_picked_point(self):
        """Move the camera so the surface point under the cursor becomes the focal
        point (and thus the rotation center). View direction and distance stay."""
        pos = self.GetInteractor().GetEventPosition()
        renderer = self.GetDefaultRenderer() or self.GetCurrentRenderer()
        if renderer is None:
            return
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        if not picker.Pick(pos[0], pos[1], 0, renderer):
            return
        target = picker.GetPickPosition()
        cam = renderer.GetActiveCamera()
        fp, cp = cam.GetFocalPoint(), cam.GetPosition()
        delta = [t - f for t, f in zip(target, fp)]
        cam.SetFocalPoint(target)
        cam.SetPosition([c + d for c, d in zip(cp, delta)])
        renderer.ResetCameraClippingRange()
