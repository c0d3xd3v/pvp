
import threading
from collections import deque

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QPointF, Slot, QPoint, QCoreApplication, QObject
from PySide6.QtGui import QSurfaceFormat, QMouseEvent, QWheelEvent
from PySide6.QtQuick import QQuickFramebufferObject
from PySide6.QtQml import qmlRegisterType

from visualization.vtk import vtklib as vtk
from visualization.vtk.VTKMouseInteractorStyle import VTKMouseInteractorStyle
from visualization.qtquick.mouse_helper import cloneMouseEvent
from visualization.qtquick.mouse_helper import cloneWheelEvent
from visualization.qtquick.mouse_helper import convertToMouseEvent
from visualization.qtquick.mouse_helper import create_mouse_event_from_hover_event
from visualization.qtquick.VTKItemFramebufferRenderer import FbItemRenderer


class _InteractorTimerBridge(QObject):
    """Drives the timers vtkGenericRenderWindowInteractor asks for (it only
    fires CreateTimerEvent/DestroyTimerEvent), e.g. the reorient tween of
    vtkCameraOrientationWidget.

    Two threads are involved: VTK (events, rendering) runs on Qt Quick's render
    thread, while QTimer and QQuickItem.update() only work on the GUI thread.
    So the QTimers live here on the GUI thread and merely mark a timer as due;
    the render thread runs the due VTK TimerEvents in process_due(), right
    before it renders the frame."""

    _start_requested = Signal(int, bool, int)
    _stop_requested = Signal(int)

    def __init__(self, item):
        super().__init__(item)   # must be constructed on the GUI thread
        self._item = item
        self._interactor = None
        self._timers: dict[int, QTimer] = {}
        self._lock = threading.Lock()
        self._alive: set[int] = set()
        self._due: set[int] = set()
        self._start_requested.connect(self._start, Qt.QueuedConnection)
        self._stop_requested.connect(self._stop, Qt.QueuedConnection)

    def attach(self, interactor):
        self._interactor = interactor
        interactor.AddObserver("CreateTimerEvent", self._on_create)
        interactor.AddObserver("DestroyTimerEvent", self._on_destroy)

    # --- render thread ------------------------------------------------------

    def _on_create(self, obj, _event):
        vtk_id = int(obj.GetTimerEventId())
        duration = int(obj.GetTimerEventDuration())
        obj.SetTimerEventPlatformId(vtk_id)
        with self._lock:
            self._alive.add(vtk_id)
            # Short timers are due at the next frame: the camera widget puts the
            # camera at the target pose until its first tick, so waiting a full
            # interval would flash the end pose before the animation plays.
            if duration <= 16:
                self._due.add(vtk_id)
        # One VTK tick per displayed frame at most (~60 fps), otherwise the
        # whole tween runs between two frames and looks like a jump.
        self._start_requested.emit(vtk_id, obj.GetTimerEventType() == obj.OneShotTimer,
                                   max(16, duration))

    def _on_destroy(self, obj, _event):
        vtk_id = int(obj.GetTimerEventPlatformId())
        with self._lock:
            self._alive.discard(vtk_id)
            self._due.discard(vtk_id)
        self._stop_requested.emit(vtk_id)

    def process_due(self):
        if self._interactor is None:
            return
        with self._lock:
            due, self._due = self._due & self._alive, set()
        for vtk_id in due:
            self._interactor.SetTimerEventId(vtk_id)
            self._interactor.TimerEvent()

    # --- GUI thread ---------------------------------------------------------

    @Slot(int, bool, int)
    def _start(self, vtk_id, oneshot, interval_ms):
        self._stop(vtk_id)
        timer = QTimer(self)
        timer.setSingleShot(oneshot)
        timer.setInterval(interval_ms)
        timer.timeout.connect(lambda: self._fire(vtk_id, oneshot))
        self._timers[vtk_id] = timer
        timer.start()
        self._item.update()

    def _fire(self, vtk_id, oneshot):
        with self._lock:
            if vtk_id in self._alive:
                self._due.add(vtk_id)
        if oneshot:
            self._stop(vtk_id)
        self._item.update()

    @Slot(int)
    def _stop(self, vtk_id):
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
        self._timer_bridge = _InteractorTimerBridge(self)   # attached in object_created
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

            # Runs on the render thread, from createRenderer() inside
            # updatePaintNode() — the one place besides the GUI thread where
            # Qt accepts self.update().
            self.om.SetParentRenderer(renderer)
            self.om.SetInteractor(self.interactor)
            self._timer_bridge.attach(self.interactor)
            self._yflip = _GizmoYFlipGuard(self.interactor, self.om, active=False)
            self.om.On()

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

