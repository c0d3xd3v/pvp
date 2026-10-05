import os
import sys
import platform

import vtk

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QCursor, QMouseEvent, QWheelEvent
from PySide6.QtQuick import QQuickFramebufferObject
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

GL_RGBA = 0x1908   # OpenGL enum; avoids depending on PyOpenGL for one constant

# Try to import VTKMouseInteractorStyle, fall back to the standard style
try:
    from visualization.vtk.VTKMouseInteractorStyle import VTKMouseInteractorStyle
    CustomStyle = VTKMouseInteractorStyle
except ImportError:
    CustomStyle = vtk.vtkInteractorStyleTrackballCamera

class FbItemRenderer(QQuickFramebufferObject.Renderer):
    def __init__(self):
        super().__init__()
        self.isinit = False
        self.rw = None
        self.rwi = None
        self.renderer = None
        self._fbo = None

        # Create VTK render window and interactor
        self.rw = vtk.vtkGenericOpenGLRenderWindow()
        self.rwi = vtk.vtkGenericRenderWindowInteractor()

        self.mouseIn = False
        self.vtkitem = None

        # VTK setup
        self.rw.SetOwnContext(False)
        self.rwi.SetRenderWindow(self.rw)
        self.renderer = vtk.vtkRenderer()
        self.rw.AddRenderer(self.renderer)
        self.window = None

        # Set interactor style
        self.style = CustomStyle()
        self.setInteractorStyle(self.style)

        # Platform-independent initialization
        self._init_platform_specific()

    def _init_platform_specific(self):
        """Platform-specific initialization"""

        # General settings
        self.rw.SetMultiSamples(0)  # disable MSAA for the FBO
        self.renderer.SetBackground(0.1, 0.1, 0.1)  # dark background

        # For better performance
        self.rw.SetAlphaBitPlanes(1)
        self.rw.SetPointSmoothing(1)
        self.rw.SetLineSmoothing(1)

    def setInteractorStyle(self, style):
        self.style = style
        if self.rwi:
            self.rwi.SetInteractorStyle(self.style)
        if self.style and self.renderer:
            self.style.SetDefaultRenderer(self.renderer)

    def createFramebufferObject(self, size):
        """Create the framebuffer object"""

        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        fmt.setInternalTextureFormat(GL_RGBA)  # explicit format
        fmt.setSamples(0)  # disable MSAA
        fmt.setMipmap(False)

        # Create FBO
        fbo = QOpenGLFramebufferObject(size, fmt)

        self._fbo = fbo
        self.isinit = False  # force re-initialization

        return fbo

    def synchronize(self, item: QQuickFramebufferObject):
        if not item:
            return

        self.vtkitem = item
        dpr = self.__getPixelRatio()

        size = item.size()
        if size.width() > 0 and size.height() > 0:
            w = int(size.width()*dpr)
            h = int(size.height()*dpr)

            if self.rw.GetSize() != [w, h]:
                self.rw.SetSize(w, h)
                self.rwi.SetSize(w, h)

    def render(self):
        """Main render function"""
        if not self.vtkitem:
            return

        # Initialize on first render
        if not self.isinit:
            self._initialize_vtk_context()

        # Make the VTK context current
        self.rw.SetIsCurrent(True)
        self.rw.SetReadyForRendering(True)

        # Process mouse events
        self._process_mouse_events()

        # Render
        self.rw.Render()
        self.rwi.Render()

    def _initialize_vtk_context(self):
        """Initialize the VTK OpenGL context"""
        try:
            self.rw.SetIsCurrent(True)
            self.rw.SetReadyForRendering(True)
            self.rw.OpenGLInitContext()

            # Settings required for the Qt integration
            self.rw.SetUseOffScreenBuffers(False)
            self.rw.SetSwapBuffers(True)  # Qt does the swapping

            self.rwi.Initialize()
            self.rwi.Start()
            self.rwi.Enable()

            # Renderer tuning
            #self.renderer.SetUseDepthPeeling(1)
            #self.renderer.SetMaximumNumberOfPeels(5)
            #self.renderer.SetOcclusionRatio(0.1)
            self.renderer.UseFXAAOn()

            self.isinit = True
            print(f"VTK OpenGL Context initialized on {platform.system()}")

        except Exception as e:
            print(f"Error initializing VTK context: {e}")
            # Fallback: try without special initialization
            self.rwi.Initialize()
            self.isinit = True

    def _process_mouse_events(self):
        """Process mouse events from the QML item"""
        if not hasattr(self.vtkitem, 'mouseButtonEvents'):
            return

        # Button events
        # all queued, in order (press, double-click, release, ...)
        while self.vtkitem.mouseButtonEvents:
            self.__processMouseButtonEvent(self.vtkitem.mouseButtonEvents.popleft())

        # Move events
        if self.vtkitem.lastMouseMoveEvent and not self.vtkitem.lastMouseMoveEvent.isAccepted():
            self.__processMouseMoveEvent(self.vtkitem.lastMouseMoveEvent)
            self.vtkitem.lastMouseMoveEvent.accept()

        # Wheel events
        if self.vtkitem.lastWheelEvent and not self.vtkitem.lastWheelEvent.isAccepted():
            self.__processWheelEvent(self.vtkitem.lastWheelEvent)
            self.vtkitem.lastWheelEvent.accept()

    def __processMouseButtonEvent(self, event: QMouseEvent):
        """Handle mouse button events"""
        if not self.rwi:
            return

        ctrl, shift = self.__getCtrlShift(event)
        repeat = 0
        if event.type() == QEvent.MouseButtonDblClick:
            repeat = 1

        self.__setEventInformation(event.position(), ctrl, shift, chr(0), repeat, None)

        if event.type() == QEvent.MouseButtonPress or event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                self.rwi.LeftButtonPressEvent()
            elif event.button() == Qt.RightButton:
                self.rwi.RightButtonPressEvent()
            elif event.button() == Qt.MiddleButton:
                self.rwi.MiddleButtonPressEvent()
        elif event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                self.rwi.LeftButtonReleaseEvent()
            elif event.button() == Qt.RightButton:
                self.rwi.RightButtonReleaseEvent()
            elif event.button() == Qt.MiddleButton:
                self.rwi.MiddleButtonReleaseEvent()

    def __processMouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        if not self.rwi:
            return

        ctrl, shift = self.__getCtrlShift(event)
        self.__setEventInformation(event.position(), ctrl, shift, chr(0), 0, None)
        self.rwi.MouseMoveEvent()

    def __processWheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel events"""
        if not self.rwi:
            return

        ctrl, shift = self.__getCtrlShift(event)
        self.__setEventInformation(event.position(), ctrl, shift, chr(0), 0, None)

        delta = event.angleDelta().y()
        if delta > 0:
            self.rwi.MouseWheelForwardEvent()
        elif delta < 0:
            self.rwi.MouseWheelBackwardEvent()

    def __setEventInformation(self, positionPoint: QPointF, ctrl, shift, key, repeat=0, keysum=None):
        """Set event information for VTK"""
        if not self.rwi:
            return

        dpr = self.__getPixelRatio()
        (w, h) = self.rw.GetSize()

        if w <= 0 or h <= 0:
            return

        y = positionPoint.y()*dpr
        x = positionPoint.x()*dpr

        self.rwi.SetEventInformation(
            int(round(x)),
            int(round(h - y)),
            ctrl,
            shift,
            key,
            repeat,
            keysum,
        )

    def __getCtrlShift(self, event):
        """Determine Ctrl/Shift modifiers"""
        ctrl = shift = False

        if hasattr(event, "modifiers"):
            if event.modifiers() & Qt.ShiftModifier:
                shift = True
            if event.modifiers() & Qt.ControlModifier:
                ctrl = True

        return ctrl, shift

    def __getPixelRatio(self):
        if self.vtkitem and self.vtkitem.window():
            return self.vtkitem.window().devicePixelRatio()
        return 1.0

    # Helpers for the VTK integration
    def add_actor(self, actor):
        """Add a VTK actor"""
        if self.renderer and actor:
            self.renderer.AddActor(actor)
            self.rw.Render()

    def remove_actor(self, actor):
        """Remove a VTK actor"""
        if self.renderer and actor:
            self.renderer.RemoveActor(actor)
            self.rw.Render()

    def clear(self):
        """Clear the scene"""
        if self.renderer:
            self.renderer.RemoveAllViewProps()
            self.rw.Render()

    def reset_camera(self):
        """Reset the camera"""
        if self.renderer:
            self.renderer.ResetCamera()
            self.rw.Render()
