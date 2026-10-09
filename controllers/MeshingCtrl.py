import traceback

import numpy as np

from PySide6.QtCore import Slot, Signal, QObject, QThread

from meshing.FTetWildMesher import FTetWildMesher


class _MeshingWorker(QObject):
    """Runs on a background QThread. Owns no VTK/GUI state."""
    finished = Signal(bool, object)   # success, MeshingResult or None
    progress = Signal(str, float)     # stage label, fraction (NaN = indeterminate)

    def __init__(self, mesher, vertices, triangles, params):
        super().__init__()
        self.__mesher = mesher
        self.__V = vertices
        self.__F = triangles
        self.__params = params

    @Slot()
    def run(self):
        try:
            result = self.__mesher.mesh(self.__V, self.__F, self.__params,
                                        progress=self.progress.emit)
            self.finished.emit(True, result)
        except Exception as e:
            print(f"Meshing failed: {e}")
            traceback.print_exc()
            self.finished.emit(False, None)


class MeshingCtrl(QObject):
    meshingStarted  = Signal()
    meshingFinished = Signal(bool)        # True = success, False = failure
    progressChanged = Signal(str, float)  # stage label, fraction (NaN = indeterminate)

    def __init__(self):
        super().__init__()
        self.__meshers = {m.name: m for m in [FTetWildMesher()]}
        self.__preproc_ctrl = None
        self.__scene_ctrl = None
        self.__thread: QThread | None = None
        self.__worker: _MeshingWorker | None = None

    def set_controllers(self, preproc_ctrl, scene_ctrl):
        self.__preproc_ctrl = preproc_ctrl
        self.__scene_ctrl = scene_ctrl

    @Slot(result='QVariantList')
    def getMeshers(self) -> list:
        return list(self.__meshers.keys())

    @Slot(str, result='QVariantList')
    def getSchema(self, mesher_name: str) -> list:
        m = self.__meshers.get(mesher_name)
        if not m:
            return []
        return [{
            "name":    p.name,
            "label":   p.label,
            "default": p.default,
            "min":     p.min_value,
            "max":     p.max_value,
            "step":    p.step,
            "tooltip": p.tooltip,
        } for p in m.param_schema]

    @Slot(str, 'QVariantMap', result=bool)
    def runMesher(self, mesher_name: str, params) -> bool:
        if self.__thread is not None and self.__thread.isRunning():
            print("Meshing: already running")
            return False

        m = self.__meshers.get(mesher_name)
        if m is None or self.__preproc_ctrl is None or self.__scene_ctrl is None:
            return False
        surface = self.__preproc_ctrl.get_session().surface
        if surface is None or surface.data is None:
            print("Meshing: no surface loaded")
            return False

        V = np.array(surface.data.get_vertices(), dtype=np.float64)
        F = np.array(surface.data.get_triangles(), dtype=np.int32)
        param_dict = {k: float(v) for k, v in dict(params).items()}
        print(f"Meshing: {mesher_name} params={param_dict}")

        self.__thread = QThread()
        self.__worker = _MeshingWorker(m, V, F, param_dict)
        self.__worker.moveToThread(self.__thread)

        # Wiring — Qt manages cleanup via deleteLater so we never block GUI thread.
        self.__thread.started.connect(self.__worker.run)
        self.__worker.finished.connect(self.__on_worker_finished)          # GUI-thread
        self.__worker.finished.connect(self.__thread.quit)                 # bg-thread
        self.__worker.finished.connect(self.__worker.deleteLater)
        self.__worker.progress.connect(self.progressChanged)               # auto-queued → GUI
        self.__thread.finished.connect(self.__thread.deleteLater)
        # When the C++ QThread object is destroyed, forget our reference
        self.__thread.destroyed.connect(self.__on_thread_destroyed)

        self.meshingStarted.emit()
        self.__thread.start()
        return True

    @Slot(bool, object)
    def __on_worker_finished(self, success: bool, result):
        # Runs on GUI thread (worker.finished → auto-queued).
        if success and result is not None:
            # Replace project: surface = tet boundary, volume = tet set.
            # PreProcCtrl handles session + scene + selection consistently.
            self.__preproc_ctrl.replace_project_with_mesh(
                result.vertices,
                result.triangles,
                result.tetrahedra,
                name="meshed",
            )
        self.meshingFinished.emit(success)
        # No explicit cleanup — Qt handles it via the deleteLater chain above.

    @Slot()
    def __on_thread_destroyed(self):
        self.__thread = None
        self.__worker = None

    @Slot(result=bool)
    def cancelMesher(self) -> bool:
        """Hard-cancel the currently running mesher. Uses QThread.terminate(),
        which is unsafe (may leak the C++ FTetWildWrapper and its internal
        allocations). Acceptable trade-off for user-triggered abort.
        """
        if self.__thread is None or not self.__thread.isRunning():
            return False
        # terminate() stops the thread forcefully. Signals from the worker
        # won't fire anymore, so we have to drive the shutdown ourselves.
        self.__thread.terminate()
        self.__thread.wait(2000)   # bounded wait; terminate should be near-instant
        # Qt's deleteLater chain won't run because `worker.finished` never fired.
        try:
            if self.__worker is not None:
                self.__worker.deleteLater()
            if self.__thread is not None:
                self.__thread.deleteLater()
        except RuntimeError:
            pass
        self.__thread = None
        self.__worker = None
        self.meshingFinished.emit(False)
        return True
