import traceback

import numpy as np

from PySide6.QtCore import Slot, Signal, QObject, QThread

from meshing.FTetWildMesher import FTetWildMesher, MeshingCancelled


class _MeshingWorker(QObject):
    """Runs on a background QThread. Owns no VTK/GUI state."""
    finished = Signal(bool, object)   # success, MeshingResult or None
    # stage label, fraction (NaN = indeterminate), max_energy (NaN outside the
    # optimization loop), v_num, t_num (-1 outside the optimization loop)
    progress = Signal(str, float, float, int, int)

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
        except MeshingCancelled:
            print("Meshing cancelled by user")
            self.finished.emit(False, None)
        except Exception as e:
            print(f"Meshing failed: {e}")
            traceback.print_exc()
            self.finished.emit(False, None)


class MeshingCtrl(QObject):
    meshingStarted  = Signal()
    meshingFinished = Signal(bool)        # True = success, False = failure
    # stage label, fraction (NaN = indeterminate), max_energy (NaN outside
    # optimization), v_num, t_num (-1 outside optimization)
    progressChanged = Signal(str, float, float, int, int)

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
        bbox_diag = self.__current_bbox_diagonal()
        return [{
            "name":    p.name,
            "label":   p.label,
            "default": p.default,
            "min":     p.min_value,
            "max":     p.max_value,
            "step":    p.step,
            "tooltip": p.tooltip,
        } for p in m.param_schema(bbox_diag)]

    def __current_bbox_diagonal(self) -> float | None:
        """Diagonal of the bbox of the currently loaded surface, in model
        units — mesher schema uses it to compute sensible defaults for
        absolute-unit parameters."""
        if self.__preproc_ctrl is None:
            return None
        surf = self.__preproc_ctrl.get_session().surface
        if surf is None or surf.data is None:
            return None
        V = np.asarray(surf.data.get_vertices(), dtype=np.float64)
        if V.size == 0:
            return None
        return float(np.linalg.norm(V.max(axis=0) - V.min(axis=0)))

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
        """Cooperative cancel of the currently running mesher. Signals the
        underlying FTetWildWrapper to raise Cancelled at its next progress
        tick; the worker's exception path then drives the normal cleanup
        via the finished signal.

        Response time is bounded by one optimizer iteration (seconds), or
        one stage boundary when the current stage doesn't call back. Older
        implementations used QThread.terminate(), which crashed the process
        when it fired while fTetWild / TBB held locks.
        """
        if self.__thread is None or not self.__thread.isRunning():
            return False
        for m in self.__meshers.values():
            # Each mesher ignores the request when it isn't the one running.
            try:
                m.request_cancel()
            except AttributeError:
                pass
        return True
