import vtk


NORMALS = {
    "x":  (1, 0, 0), "-x": (-1, 0, 0),
    "y":  (0, 1, 0), "-y": (0, -1, 0),
    "z":  (0, 0, 1), "-z": (0, 0, -1),
}


class ClipPlane:
    """The interactive clip plane: a vtkPlane plus the 3D widget to drag it.

    Which actors get clipped is up to the scene; it attaches `plane` to their
    mappers (or uses volume_filter() for whole-tet clipping).
    """

    def __init__(self):
        self.plane = vtk.vtkPlane()
        self.plane.SetNormal(*NORMALS["x"])
        self.plane.SetOrigin(0, 0, 0)
        self.enabled = False
        self.__vtkitem = None
        self.__rep = None
        self.__widget = None

    def attach(self, vtkitem):
        self.__vtkitem = vtkitem

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if enabled:
            self.__ensure_widget()
            self.__widget.EnabledOn()
            self.__hide_sphere()
        elif self.__widget is not None:
            self.__widget.EnabledOff()
        # while clipping, left-drag moves the plane instead of picking faces
        self.__vtkitem.mouse_interactor.clip_mode = enabled

    def set_axis(self, axis: str) -> bool:
        if axis not in NORMALS:
            return False
        self.plane.SetNormal(*NORMALS[axis])
        if self.__rep is not None:
            self.__rep.SetNormal(*NORMALS[axis])
            self.__rep.Modified()
        return True

    def reposition(self):
        """Fit the widget to the visible scene and put the plane through its center."""
        if self.__rep is None:
            return
        bounds = self.__vtkitem.renderer.renderer.ComputeVisiblePropBounds()
        if bounds[0] < bounds[1]:
            self.__rep.PlaceWidget(bounds)
            self.__rep.SetOrigin([(bounds[2 * i] + bounds[2 * i + 1]) / 2.0 for i in range(3)])
        self.__rep.SetNormal(*self.plane.GetNormal())
        self.__rep.GetPlane(self.plane)

    def volume_filter(self, unstructured_grid):
        """Whole-cell clipping for a volume mesh: keeps only cells fully on the
        kept side. ExtractInsideOff matches the mapper.AddClippingPlane convention
        (mapper keeps the +normal side; ExtractInsideOn would keep -normal)."""
        extract = vtk.vtkExtractGeometry()
        extract.SetInputData(unstructured_grid)
        extract.SetImplicitFunction(self.plane)
        extract.ExtractInsideOff()
        extract.ExtractBoundaryCellsOff()
        return extract

    def __ensure_widget(self):
        if self.__widget is not None:
            self.reposition()
            return
        self.__rep = vtk.vtkImplicitPlaneRepresentation()
        self.__rep.SetPlaceFactor(1.0)
        self.__rep.DrawPlaneOff()
        self.__rep.OutlineTranslationOff()
        self.__rep.ScaleEnabledOff()
        # Hide arrow via opacity — survives EnabledOn() unlike VisibilityOff().
        self.__rep.GetNormalProperty().SetOpacity(0.0)
        self.__rep.GetSelectedNormalProperty().SetOpacity(0.0)

        self.__widget = vtk.vtkImplicitPlaneWidget2()
        self.__widget.SetInteractor(self.__vtkitem.interactor)
        self.__widget.SetRepresentation(self.__rep)
        self.__widget.AddObserver("InteractionEvent", self.__on_interaction)
        self.__widget.AddObserver("EndInteractionEvent", self.__on_interaction_end)
        self.reposition()

    def __hide_sphere(self):
        normal_prop = self.__rep.GetNormalProperty()
        actors = vtk.vtkActorCollection()
        self.__rep.GetActors(actors)
        actors.InitTraversal()
        a = actors.GetNextActor()
        while a:
            p = a.GetProperty()
            # Sphere actor: has its own property (not NormalProperty) and non-flat 3D bounds
            if p is not None and p is not normal_prop:
                b = a.GetBounds()
                if b and all(b[2 * i + 1] > b[2 * i] for i in range(3)):
                    a.VisibilityOff()
            a = actors.GetNextActor()

    def __on_interaction(self, obj, event):
        self.__rep.GetPlane(self.plane)

    def __on_interaction_end(self, obj, event):
        self.__rep.SetInteractionState(0)
