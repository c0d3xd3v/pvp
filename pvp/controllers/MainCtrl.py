from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtCore import QUrl
from PySide6.QtCore import Signal
from PySide6.QtCore import QObject
from PySide6.QtCore import QTimer
from PySide6.QtQml import QQmlApplicationEngine

from pvp.controllers.SelectionCtrl import SelectionCtrl
from pvp.controllers.SceneCtrl import SceneCtrl
from pvp.controllers.PreProcCtrl import PreProcCtrl
from pvp.controllers.ResultCtrl import ResultCtrl
from pvp.controllers.MeshingCtrl import MeshingCtrl
from pvp.fileio.readers import read_result
from pvp.fileio.formats import file_kind
from pvp.visualization.qtquick.VTKItem import VTKItem



class MainCtrl(QObject):
    meshLoaded = Signal(str)

    def __init__(self):
        super().__init__()
        self.__selection_ctrl = SelectionCtrl()
        self.__scene_ctrl     = SceneCtrl()
        self.__preproc_ctrl    = PreProcCtrl()
        self.__result_ctrl    = ResultCtrl()
        self.__meshing_ctrl   = MeshingCtrl()
        self.__startup_file: str | None = None

        self.__preproc_ctrl.set_controllers(self.__scene_ctrl, self.__selection_ctrl)
        self.__result_ctrl.set_scene_ctrl(self.__scene_ctrl)
        self.__selection_ctrl.set_scene_ctrl(self.__scene_ctrl)
        self.__meshing_ctrl.set_controllers(self.__preproc_ctrl, self.__scene_ctrl)
        self.__selection_ctrl.update_partition.connect(self.__scene_ctrl.interactive_select)
        self.__selection_ctrl.clear_partition.connect(self.__scene_ctrl.interactive_deselect)
        self.__selection_ctrl.preview_partition.connect(self.__scene_ctrl.interactive_preview)
        self.__selection_ctrl.clear_preview.connect(self.__scene_ctrl.interactive_clear_preview)

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
        ctxt.setContextProperty("PreProcCtrl", self.__preproc_ctrl)
        ctxt.setContextProperty("ResultCtrl", self.__result_ctrl)
        ctxt.setContextProperty("MeshingCtrl", self.__meshing_ctrl)

    def setupInternal(self, item: VTKItem):
        self.__scene_ctrl.set_vtk_item(item)
        item.mouse_interactor.qt_signals.cell_picked.connect(self.__selection_ctrl.face_selected)
        item.mouse_interactor.qt_signals.cell_right_picked.connect(self.__selection_ctrl.face_deselected)
        item.mouse_interactor.qt_signals.cell_hovered.connect(self.__selection_ctrl.face_hovered)
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

    @Slot(str, float)
    @Slot(str)
    def loadMesh(self, file_path: str, surface_scale: float = 1.0):
        """`surface_scale` applies to STL/OBJ only; the QML side picks it
        from the units dialog so the vertices land in mm regardless of the
        original file's convention."""
        file_path = QUrl(file_path).toLocalFile()
        kind = file_kind(file_path)

        if kind == "result":
            data = read_result(file_path)
            self.__selection_ctrl.set_picking_enabled(False)
            self.__scene_ctrl.reset_view_toggles()
            self.__scene_ctrl.add_result_geometry(data)
            self.__result_ctrl.load_result(data)
            self.meshLoaded.emit("results")
        elif kind == "surface":
            self.__exit_result_mode()
            self.__preproc_ctrl.loadSurface(file_path, surface_scale)
            self.meshLoaded.emit("geometry")
        elif kind == "volume":
            self.__exit_result_mode()
            self.__preproc_ctrl.loadVolume(file_path)
            self.meshLoaded.emit("geometry")
        elif kind == "project":
            self.__exit_result_mode()
            if self.__preproc_ctrl.loadProject(file_path) == "":
                self.meshLoaded.emit("geometry")

    @Slot(str, result=str)
    def fileKind(self, url: str) -> str:
        """QML asks before loading: surfaces need a unit, results a type."""
        return file_kind(QUrl(url).toLocalFile() or url)

    def __exit_result_mode(self):
        self.__scene_ctrl.clear_result_actor()
        self.__result_ctrl.clear()
