
from collections import deque

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QPointF, Slot, QPoint, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QMouseEvent, QWheelEvent
from PySide6.QtQuick import QQuickFramebufferObject
from PySide6.QtQml import qmlRegisterType

import vtk

from visualization.vtk.vtkhelper import make_cube_actor
from visualization.vtk.VTKMouseInteractorStyle import VTKMouseInteractorStyle

from visualization.qtquick.mouse_helper import cloneMouseEvent
from visualization.qtquick.mouse_helper import cloneWheelEvent
from visualization.qtquick.mouse_helper import convertToMouseEvent
from visualization.qtquick.mouse_helper import create_mouse_event_from_hover_event
from visualization.qtquick.VTKItemFramebufferRenderer import FbItemRenderer


class VTKItem(QQuickFramebufferObject):
    rendererInitialized = Signal()
    def __init__(self):
        super().__init__()
        self.renderer = None
        self.interactor = None
        self.renderWindow = None

        # Button events are queued, not overwritten: press/double-click/release can
        # all arrive before the render thread runs, and every one of them matters.
        # (deque append/popleft are thread-safe; the render thread consumes them.)
        self.mouseButtonEvents: deque[QMouseEvent] = deque()
        self.lastMouseMoveEvent: QMouseEvent = None
        self.lastWheelEvent: QWheelEvent = None

        self.colors = vtk.vtkNamedColors()
        labels = 'xyz'

        self.colors.SetColor("ParaViewBkg", [82, 87, 110, 255])
        self.axes = make_cube_actor(labels, self.colors)
        self.om = vtk.vtkOrientationMarkerWidget()
        self.om.SetOrientationMarker(self.axes)

        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.AllButtons)

        self.mouseIn = False
        self.zoomIn = False
        self.zoomOut = False
        self.mouseMove = False
        self.mouseLeftPress = False
        self.mouseLeftRelease = False
        self.mouse_interactor = VTKMouseInteractorStyle()
        self.setMirrorVertically(True)

    def object_created(self):
        if self.renderer != None:

            renderer:vtk.vtkRenderer = self.renderer.renderer
            self.interactor = self.renderer.rwi

            self.renderer.setInteractorStyle(self.mouse_interactor)

            bgcolor = vtk.vtkNamedColors().HTMLColorToRGB("#363737")
            bgcolor = [bgcolor[0]/255., bgcolor[1]/255., bgcolor[2]/255.]
            white = vtk.vtkNamedColors().GetColor3d('White')
            renderer.SetBackground(bgcolor)
            renderer.SetBackground2(bgcolor)
            renderer.GradientBackgroundOn()

            self.om.SetInteractor(self.interactor)
            self.om.EnabledOn()
            self.om.InteractiveOff()
            self.om.Modified()

            self.update()
            self.mouse_interactor.set_pixel_ratio(self.window().devicePixelRatio())
            self.rendererInitialized.emit()

    def setSeletableActor(self, actor):
        self.mouse_interactor.setSelectableActor(actor)

    def mousePressEvent(self, event: QMouseEvent):
        self.__processMouseButtonEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.__processMouseButtonEvent(event)

    def __processMouseButtonEvent(self, event: QMouseEvent):
        self.mouseButtonEvents.append(cloneMouseEvent(event))
        event.accept()
        self.update()

    def mouseMoveEvent(self, event):
        self.lastMouseMoveEvent = cloneMouseEvent(event)
        self.lastMouseMoveEvent.ignore()
        event.accept()
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        self.lastWheelEvent = cloneWheelEvent(event)
        self.lastWheelEvent.ignore()
        event.accept()
        self.update()

    @Slot(float, float, int, int, int)
    def onMousePressed(
        self, x: float, y: float, button: int, buttons: int, modifiers: int
    ):
        self.mouseButtonEvents.append(convertToMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(x, y),
            Qt.MouseButton(button),
            Qt.MouseButtons(buttons),
            Qt.KeyboardModifiers(modifiers),
        ))
        self.update()

    @Slot(float, float, int, int, int)
    def onMouseDoubleClicked(
        self, x: float, y: float, button: int, buttons: int, modifiers: int
    ):
        # The renderer turns a DblClick into a press with repeat count 1, which the
        # interactor style treats as "center on picked point".
        self.mouseButtonEvents.append(convertToMouseEvent(
            QEvent.MouseButtonDblClick,
            QPointF(x, y),
            Qt.MouseButton(button),
            Qt.MouseButtons(buttons),
            Qt.KeyboardModifiers(modifiers),
        ))
        self.update()

    @Slot(float, float, int, int, int)
    def onMouseReleased(
        self, x: float, y: float, button: int, buttons: int, modifiers: int
    ):
        self.mouseButtonEvents.append(convertToMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(x, y),
            Qt.MouseButton(button),
            Qt.MouseButtons(buttons),
            Qt.KeyboardModifiers(modifiers),
        ))
        self.update()

    @Slot(float, float, int, int, int)
    def onMouseMove(
        self, x: float, y: float, button: int, buttons: int, modifiers: int
    ):
        self.lastMouseMoveEvent = convertToMouseEvent(
            QEvent.MouseMove,
            QPointF(x, y),
            Qt.MouseButton(button),
            Qt.MouseButtons(buttons),
            Qt.KeyboardModifiers(modifiers),
        )
        self.lastMouseMoveEvent.ignore()
        self.update()

    @Slot(QPoint, int, int, int, QPoint, float, float)
    def onMouseWheel(
        self,
        angleDelta: QPoint,
        buttons: int,
        inverted: int,
        modifiers: int,
        pixelDelta: QPoint,
        x: float,
        y: float,
    ):
        self.lastWheelEvent = QWheelEvent(
            QPointF(x, y),
            QPointF(x, y),
            pixelDelta,
            angleDelta,
            Qt.MouseButtons(buttons),
            Qt.KeyboardModifiers(modifiers),
            Qt.NoScrollPhase,
            bool(inverted),
        )
        self.lastWheelEvent.ignore()
        self.update()

    def clearAllActors(self):
        actors = self.renderer.renderer.GetActors()
        actors.InitTraversal()
        actor = actors.GetNextItem()
        while actor:
            self.renderer.renderer.RemoveActor(actor)
            actor = actors.GetNextItem()

    def updatePaintNode(self, node, inOutData):
        width = self.width()
        height = self.height()

        pixel_ratio = self.window().devicePixelRatio()
        #print(f'pixel ratio : {pixel_ratio}')
        self.mouse_interactor.set_pixel_ratio(pixel_ratio)

        if width != 0. and height != 0.:
            self.om.SetViewport(1 - 110./width, 0, 1, 110./height)
        return QQuickFramebufferObject.updatePaintNode(self, node, inOutData)

    def createRenderer(self):
        self.renderer = FbItemRenderer()
        self.object_created()
        return self.renderer

def defaultFormat(stereo_capable):
  """ Po prostu skopiowałem to z https://github.com/Kitware/VTK/blob/master/GUISupport/Qt/QVTKRenderWindowAdapter.cxx
     i działa poprawnie bufor głębokości
  """
  fmt = QSurfaceFormat()
  fmt.setRenderableType(QSurfaceFormat.OpenGL)
  fmt.setVersion(4, 6)
  fmt.setProfile(QSurfaceFormat.CoreProfile)
  fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
  fmt.setRedBufferSize(8)
  fmt.setGreenBufferSize(8)
  fmt.setBlueBufferSize(8)
  fmt.setDepthBufferSize(8)
  fmt.setAlphaBufferSize(8)
  fmt.setStencilBufferSize(0)
  fmt.setStereo(stereo_capable)
  fmt.setSamples(0)

  return fmt

QSurfaceFormat.setDefaultFormat(defaultFormat(False))
qmlRegisterType(VTKItem, "QmlVtk", 1, 0, "VTKItem")
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

