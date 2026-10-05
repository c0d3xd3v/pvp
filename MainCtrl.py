from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtCore import QUrl
from PySide6.QtCore import Signal
from PySide6.QtCore import QObject
from PySide6.QtCore import QTimer
from PySide6.QtQml import QQmlApplicationEngine

from SelectionCtrl import SelectionCtrl
from SceneCtrl import SceneCtrl
from PreProcCtrl import PreProcCtrl
from ResultCtrl import ResultCtrl
from MeshingCtrl import MeshingCtrl
from FileIOCtrl import FileIOCtrl
from geometry.AbstractMeshData import AbstractResultData
from qml.vtk.VTKItem import VTKItem

_VOLUME_EXTS  = {".vol", ".msh"}
_SURFACE_EXTS = {".obj", ".stl"}
_RESULT_EXTS  = {".vtk"}


class MainCtrl(QObject):
    meshLoaded = Signal(str)

    def __init__(self):
        super().__init__()
        self.__fileio_ctrl    = FileIOCtrl()
        self.__selection_ctrl = SelectionCtrl()
        self.__scene_ctrl     = SceneCtrl()
        self.__prepoc_ctrl    = PreProcCtrl()
        self.__result_ctrl    = ResultCtrl()
        self.__meshing_ctrl   = MeshingCtrl()
        self.__startup_file: str | None = None

        self.__prepoc_ctrl.set_controllers(self.__scene_ctrl, self.__selection_ctrl)
        self.__result_ctrl.set_scene_ctrl(self.__scene_ctrl)
        self.__selection_ctrl.set_scene_ctrl(self.__scene_ctrl)
        self.__meshing_ctrl.set_controllers(self.__prepoc_ctrl, self.__scene_ctrl)
        self.__selection_ctrl.update_partition.connect(self.__scene_ctrl.interactive_select)

    def get_scene_ctrl(self):
        return self.__scene_ctrl

    def set_cmd_args(self, args):
        # Loading needs the VTK renderer, which only exists after the first frame;
        # the file is loaded from __on_renderer_ready (see setupInternal).
        if len(args) > 1:
            self.__startup_file = QUrl.fromLocalFile(str(Path(args[1]).resolve())).toString()

    def setupContext(self, engine: QQmlApplicationEngine):
        ctxt = engine.rootContext()
        ctxt.setContextProperty("MainCtrl", self)
        ctxt.setContextProperty("SceneCtrl", self.__scene_ctrl)
        ctxt.setContextProperty("SelectionCtrl", self.__selection_ctrl)
        ctxt.setContextProperty("PreProcCtrl", self.__prepoc_ctrl)
        ctxt.setContextProperty("ResultCtrl", self.__result_ctrl)
        ctxt.setContextProperty("MeshingCtrl", self.__meshing_ctrl)

    def setupInternal(self, item: VTKItem):
        self.__scene_ctrl.set_vtk_item(item)
        item.mouse_interactor.qt_signals.cell_picked.connect(self.__selection_ctrl.face_selected)
        # rendererInitialized is emitted on the render thread; connecting it to a
        # slot of this (GUI-thread) object makes the call queued onto the GUI thread.
        item.rendererInitialized.connect(self.__on_renderer_ready)
        if item.renderer is not None:   # render thread was faster than us
            QTimer.singleShot(0, self.__on_renderer_ready)

    @Slot()
    def __on_renderer_ready(self):
        # Go through loadMesh so QML gets meshLoaded like for a file dialog/drop.
        if self.__startup_file:
            path, self.__startup_file = self.__startup_file, None
            self.loadMesh(path)

    @Slot(str)
    def loadMesh(self, file_path: str):
        file_path = QUrl(file_path).toLocalFile()
        ext = Path(file_path).suffix.lower()

        if ext in _RESULT_EXTS:
            self.__fileio_ctrl.load_file(file_path)
            data = self.__fileio_ctrl.get_geometry()
            self.__selection_ctrl.set_picking_enabled(False)
            self.__scene_ctrl.add_result_geometry(data)
            self.__result_ctrl.load_result(data)
            self.meshLoaded.emit("results")
        elif ext in _SURFACE_EXTS:
            self.__exit_result_mode()
            self.__prepoc_ctrl.loadSurface(file_path)
            self.meshLoaded.emit("geometry")
        elif ext in _VOLUME_EXTS:
            self.__exit_result_mode()
            self.__prepoc_ctrl.loadVolume(file_path)
            self.meshLoaded.emit("geometry")

    def __exit_result_mode(self):
        self.__scene_ctrl.clear_result_actor()
        self.__result_ctrl.clear()
