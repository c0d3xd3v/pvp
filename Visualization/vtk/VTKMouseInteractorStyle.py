import vtk
from PySide6 import QtCore


class VTKMouseInteractorStyleQtSignals(QtCore.QObject):
    cell_picked = QtCore.Signal(int)
    point_picked = QtCore.Signal(int)


class VTKMouseInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self):
        super().__init__()
        self.selectableActor = None
        self.mesh_polydata = None
        self.__pixel_ratio = 1.0
        self.clip_mode = False  # suppresses cell picking when clip widget is active
        self.qt_signals = VTKMouseInteractorStyleQtSignals()
        self.AddObserver('LeftButtonPressEvent', self.left_button_press_event)

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

    def left_button_press_event(self, obj, event):
        if self.GetInteractor().GetRepeatCount() > 0:
            self.center_on_picked_point()
            return      # no face selection, no rotation start for a double-click
        if not self.clip_mode:
            pos = self.GetInteractor().GetEventPosition()
            renderer = self.GetDefaultRenderer()
            cell_picker = vtk.vtkCellPicker()
            cell_picker.SetTolerance(0.01)
            if cell_picker.Pick(pos[0], pos[1], 0, renderer):
                picked_actor = cell_picker.GetActor()
                picked_cell  = cell_picker.GetCellId()
                if picked_actor and picked_actor == self.selectableActor and picked_cell != -1:
                    mapper   = picked_actor.GetMapper()
                    polydata = mapper.GetInput()
                    original_cell = picked_cell
                    if polydata:
                        ids = polydata.GetCellData().GetArray("OriginalIds")
                        if ids:
                            original_cell = ids.GetValue(picked_cell)
                    self.qt_signals.cell_picked.emit(original_cell)
        self.OnLeftButtonDown()

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
