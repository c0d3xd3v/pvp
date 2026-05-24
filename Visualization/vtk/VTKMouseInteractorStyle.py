import vtk
from PySide6 import QtCore
import math

class VTKMouseInteractorStyleQtSignals(QtCore.QObject):
    cell_picked = QtCore.Signal(int)
    point_picked = QtCore.Signal(int)


class VTKMouseInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self):
        super().__init__()
        self.selectableActor = None
        self.mesh_polydata = None
        self.__pixel_ratio = 1.0
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
        pr = 1.0
        pos = self.GetInteractor().GetEventPosition()
        coords = (pos[0] * pr, pos[1] * pr)

        renderer = self.GetDefaultRenderer()

        cell_picker = vtk.vtkCellPicker()
        cell_picker.SetTolerance(0.01)

        if cell_picker.Pick(coords[0], coords[1], 0, renderer):

            picked_actor = cell_picker.GetActor()
            picked_cell = cell_picker.GetCellId()

            picked_position = cell_picker.GetPickPosition()
            print("Pick position:", picked_position)

            if picked_actor and picked_actor == self.selectableActor and picked_cell != -1:

                mapper = picked_actor.GetMapper()
                polydata = mapper.GetInput()

                original_cell = picked_cell

                if polydata:
                    ids = polydata.GetCellData().GetArray("OriginalIds")
                    if ids:
                        original_cell = ids.GetValue(picked_cell)

                print(f'polydata : {polydata.GetCellData().GetArray("OriginalIds") is None}')
                print("Filtered cell:", picked_cell)
                print("Original cell:", original_cell)

                self.qt_signals.cell_picked.emit(original_cell)

        self.OnLeftButtonDown()
