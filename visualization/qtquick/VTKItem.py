
from collections import deque

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QPointF, Slot, QPoint, QCoreApplication, QObject
from PySide6.QtGui import QSurfaceFormat, QMouseEvent, QWheelEvent
from PySide6.QtQuick import QQuickFramebufferObject
from PySide6.QtQml import qmlRegisterType

import vtk

from visualization.vtk.VTKMouseInteractorStyle import VTKMouseInteractorStyle
from visualization.qtquick.mouse_helper import cloneMouseEvent
from visualization.qtquick.mouse_helper import cloneWheelEvent
from visualization.qtquick.mouse_helper import convertToMouseEvent
from visualization.qtquick.mouse_helper import create_mouse_event_from_hover_event
from visualization.qtquick.VTKItemFramebufferRenderer import FbItemRenderer


class _InteractorTimerBridge(QObject):
    """vtkGenericRenderWindowInteractor fires CreateTimerEvent/DestroyTimerEvent
    but doesn't drive the timers itself — it leaves that to the platform
    binding. Here we hand them to QTimer so widgets that animate (like
    vtkCameraOrientationWidget's reorient tween) actually tick, and we poke
    the Qt-Quick item to repaint on every tick."""

    def __init__(self, interactor, item):
        super().__init__(item)
        self._interactor = interactor
        self._item = item
        self._timers: dict[int, QTimer] = {}
        interactor.AddObserver("CreateTimerEvent", self._on_create)
        interactor.AddObserver("DestroyTimerEvent", self._on_destroy)

    def _on_create(self, obj, _event):
        duration = max(1, int(obj.GetTimerEventDuration()))
        vtk_id = int(obj.GetTimerEventId())
        is_oneshot = (obj.GetTimerEventType() == obj.OneShotTimer)
        timer = QTimer(self)
        timer.setSingleShot(is_oneshot)
        timer.setInterval(duration)
        timer.timeout.connect(lambda tid=vtk_id: self._tick(tid))
        self._timers[vtk_id] = timer
        obj.SetTimerEventPlatformId(vtk_id)
        timer.start()

    def _tick(self, vtk_id):
        self._interactor.SetTimerEventId(vtk_id)
        self._interactor.TimerEvent()
        self._item.update()
        t = self._timers.get(vtk_id)
        if t is not None and t.isSingleShot():
            self._timers.pop(vtk_id, None)

    def _on_destroy(self, obj, _event):
        vtk_id = int(obj.GetTimerEventPlatformId())
        timer = self._timers.pop(vtk_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()


class _GizmoYFlipGuard:
    """The FBO is displayed with setMirrorVertically(True), so what the user
    sees is a vertical flip of what VTK renders. Our mouse-event path already
    compensates globally (`h - y` in __setEventInformation). This guard
    keeps a hook in place to let us flip once more for the orientation
    gizmo if it turns out its hit-test needs it — enabled via `active`."""

    def __init__(self, interactor, widget, active: bool = False):
        self._iren = interactor
        self._w = widget
        self.active = active
        self._saved = None
        pre  = interactor.AddObserver("LeftButtonPressEvent",  self._pre,  0.9)
        post = interactor.AddObserver("LeftButtonPressEvent",  self._post, 0.1)
        pre_m  = interactor.AddObserver("MouseMoveEvent",      self._pre,  0.9)
        post_m = interactor.AddObserver("MouseMoveEvent",      self._post, 0.1)

    def _pre(self, obj, _event):
        if not self.active:
            return
        x, y = obj.GetEventPosition()
        _, h = obj.GetSize()
        self._saved = (x, y)
        obj.SetEventPosition(x, h - 1 - y)

    def _post(self, obj, _event):
        if self._saved is None:
            return
        obj.SetEventPosition(*self._saved)
        self._saved = None


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
        self.colors.SetColor("ParaViewBkg", [82, 87, 110, 255])

        # Blender-style orientation gizmo (VTK ≥ 9.1). The representation
        # anchors itself to the lower-right of the renderer, so no viewport
        # math is needed in updatePaintNode.
        self.om = vtk.vtkCameraOrientationWidget()
        rep = self.om.GetRepresentation()
        rep.AnchorToLowerRight()
        rep.SetSize(80, 80)
        rep.SetPadding(6, 6)
        self._timer_bridge = None   # created in object_created
        self._yflip = None

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

            self.om.SetParentRenderer(renderer)
            self.om.SetInteractor(self.interactor)
            # Timer-bridge first so the widget's reorient animation can tick
            # as soon as it's enabled.
            self._timer_bridge = _InteractorTimerBridge(self.interactor, self)
            self._yflip = _GizmoYFlipGuard(self.interactor, self.om, active=False)
            self.om.On()
            # The widget drives the camera from a timer, not a mouse-move
            # event, so Qt-Quick wouldn't know to repaint on its own.
            self.om.AddObserver("InteractionEvent", lambda *_: self.update())
            self.om.AddObserver("EndInteractionEvent", lambda *_: self.update())

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

    def hoverMoveEvent(self, event):
        # Qt only sends mouseMoveEvent while a button is pressed. Widgets
        # like vtkCameraOrientationWidget need button-less mouse-moves to
        # highlight the hovered handle — without those, the first click on
        # a handle lands "cold" and the widget's state-machine misses it.
        # Forward the hover as a plain MouseMove, flagged "not accepted" so
        # the render-thread's event filter actually picks it up.
        self.lastMouseMoveEvent = create_mouse_event_from_hover_event(event)
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
        pixel_ratio = self.window().devicePixelRatio()
        self.mouse_interactor.set_pixel_ratio(pixel_ratio)
        return QQuickFramebufferObject.updatePaintNode(self, node, inOutData)

    @Slot(bool)
    def setGizmoYFlip(self, enabled: bool):
        """Toggle the mirror-compensation hook. Call from QML/Python if the
        gizmo's hit test turns out to be off by the FBO's vertical flip."""
        if self._yflip is not None:
            self._yflip.active = bool(enabled)

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

