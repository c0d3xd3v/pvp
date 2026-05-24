import os
import sys
import platform

import vtk
from OpenGL.GL import GL_RGBA

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QCursor, QMouseEvent, QWheelEvent
from PySide6.QtQuick import QQuickFramebufferObject
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

# Versuche VTKMouseInteractorStyle zu importieren, fallback auf standard style
try:
    from Visualization.vtk.VTKMouseInteractorStyle import VTKMouseInteractorStyle
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

        # VTK Render Window und Interactor erstellen
        self.rw = vtk.vtkGenericOpenGLRenderWindow()
        self.rwi = vtk.vtkGenericRenderWindowInteractor()

        self.mouseIn = False
        self.vtkitem = None

        # VTK Setup
        self.rw.SetOwnContext(False)
        self.rwi.SetRenderWindow(self.rw)
        self.renderer = vtk.vtkRenderer()
        self.rw.AddRenderer(self.renderer)
        self.window = None

        # Interactor Style setzen
        self.style = CustomStyle()
        self.setInteractorStyle(self.style)

        # Plattform-unabhängige Initialisierung
        self._init_platform_specific()

    def _init_platform_specific(self):
        """Plattform-spezifische Initialisierung"""

        # Allgemeine Einstellungen
        self.rw.SetMultiSamples(0)  # MSAA deaktivieren für FBO
        self.renderer.SetBackground(0.1, 0.1, 0.1)  # Dunkler Hintergrund

        # Für bessere Performance
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
        """Framebuffer Object erstellen"""

        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        fmt.setInternalTextureFormat(GL_RGBA)  # Explizites Format
        fmt.setSamples(0)  # MSAA deaktivieren
        fmt.setMipmap(False)

        # FBO erstellen
        fbo = QOpenGLFramebufferObject(size, fmt)

        self._fbo = fbo
        self.isinit = False  # Neuinitialisierung erzwingen

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
        """Haupt-Render-Funktion"""
        if not self.vtkitem:
            return

        # Initialisierung beim ersten Render
        if not self.isinit:
            self._initialize_vtk_context()

        # VTK Context aktivieren
        self.rw.SetIsCurrent(True)
        self.rw.SetReadyForRendering(True)

        # Mouse Events verarbeiten
        self._process_mouse_events()

        # Render durchführen
        self.rw.Render()
        self.rwi.Render()

    def _initialize_vtk_context(self):
        """VTK OpenGL Context initialisieren"""
        try:
            self.rw.SetIsCurrent(True)
            self.rw.SetReadyForRendering(True)
            self.rw.OpenGLInitContext()

            # Wichtige Einstellungen für Qt Integration
            self.rw.SetUseOffScreenBuffers(False)
            self.rw.SetSwapBuffers(True)  # Qt macht das Swapping

            self.rwi.Initialize()
            self.rwi.Start()
            self.rwi.Enable()

            # Renderer optimieren
            #self.renderer.SetUseDepthPeeling(1)
            #self.renderer.SetMaximumNumberOfPeels(5)
            #self.renderer.SetOcclusionRatio(0.1)
            self.renderer.UseFXAAOn()

            self.isinit = True
            print(f"VTK OpenGL Context initialized on {platform.system()}")

        except Exception as e:
            print(f"Error initializing VTK context: {e}")
            # Fallback: Versuche es ohne spezielle Initialisierung
            self.rwi.Initialize()
            self.isinit = True

    def _process_mouse_events(self):
        """Mouse Events vom QML Item verarbeiten"""
        if not hasattr(self.vtkitem, 'lastMouseButtonEvent'):
            return

        # Button Events
        if self.vtkitem.lastMouseButtonEvent and not self.vtkitem.lastMouseButtonEvent.isAccepted():
            self.__processMouseButtonEvent(self.vtkitem.lastMouseButtonEvent)
            self.vtkitem.lastMouseButtonEvent.accept()

        # Move Events
        if self.vtkitem.lastMouseMoveEvent and not self.vtkitem.lastMouseMoveEvent.isAccepted():
            self.__processMouseMoveEvent(self.vtkitem.lastMouseMoveEvent)
            self.vtkitem.lastMouseMoveEvent.accept()

        # Wheel Events
        if self.vtkitem.lastWheelEvent and not self.vtkitem.lastWheelEvent.isAccepted():
            self.__processWheelEvent(self.vtkitem.lastWheelEvent)
            self.vtkitem.lastWheelEvent.accept()

    def __processMouseButtonEvent(self, event: QMouseEvent):
        """Verarbeite Mouse Button Events"""
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
        """Verarbeite Mouse Move Events"""
        if not self.rwi:
            return

        ctrl, shift = self.__getCtrlShift(event)
        self.__setEventInformation(event.position(), ctrl, shift, chr(0), 0, None)
        self.rwi.MouseMoveEvent()

    def __processWheelEvent(self, event: QWheelEvent):
        """Verarbeite Mouse Wheel Events"""
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
        """Setze Event-Information für VTK"""
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
        """Ermittle Ctrl/Shift Modifier"""
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

    # Hilfsmethoden für VTK Integration
    def add_actor(self, actor):
        """VTK Actor hinzufügen"""
        if self.renderer and actor:
            self.renderer.AddActor(actor)
            self.rw.Render()

    def remove_actor(self, actor):
        """VTK Actor entfernen"""
        if self.renderer and actor:
            self.renderer.RemoveActor(actor)
            self.rw.Render()

    def clear(self):
        """Szene löschen"""
        if self.renderer:
            self.renderer.RemoveAllViewProps()
            self.rw.Render()

    def reset_camera(self):
        """Camera zurücksetzen"""
        if self.renderer:
            self.renderer.ResetCamera()
            self.rw.Render()
