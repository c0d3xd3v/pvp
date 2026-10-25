import traceback

import numpy as np

from PySide6.QtCore import Slot, Signal, QObject, QThread

from pvp.meshing.FTetWildMesher import FTetWildMesher, MeshingCancelled
from pvp.model.project import Project
from pvp.services.boundary_transfer import BoundarySnapshot, snapshot_boundaries


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

    def __init__(self, project: Project, preproc_ctrl):
        super().__init__()
        self.__meshers = {m.name: m for m in [FTetWildMesher()]}
        self.__project = project
        self.__preproc_ctrl = preproc_ctrl
        self.__thread: QThread | None = None
        self.__worker: _MeshingWorker | None = None
        self.__bc_snapshot: BoundarySnapshot | None = None

    @Slot(result='QVariantList')
    def getMeshers(self) -> list:
        return list(self.__meshers.keys())

    @Slot(str, result='QVariantList')
    def getSchema(self, mesher_name: str) -> list:
        m = self.__meshers.get(mesher_name)
        if not m:
            return []
        project = self.__project
        # Absolute-unit parameters get defaults relative to the model size
        bbox_diag = project.surface.bbox_diagonal() if project.surface is not None else 0.0
        # Prefill with the parameters of the last run on this geometry (also
        # restored from a project file), else the mesher's defaults.
        last = project.mesher_params if project.mesher_name == mesher_name else {}
        return [{
            "name":    p.name,
            "label":   p.label,
            "default": last.get(p.name, p.default),
            "min":     p.min_value,
            "max":     p.max_value,
            "step":    p.step,
            "tooltip": p.tooltip,
        } for p in m.param_schema(bbox_diag or None)]

    @Slot(str, 'QVariantMap', result=bool)
    def runMesher(self, mesher_name: str, params) -> bool:
        if self.__thread is not None and self.__thread.isRunning():
            print("Meshing: already running")
            return False

        m = self.__meshers.get(mesher_name)
        if m is None:
            return False
        surface = self.__project.surface
        if surface is None:
            print("Meshing: no surface loaded")
            return False

        V = surface.vertices
        F = surface.triangles.astype(np.int32)
        param_dict = {k: float(v) for k, v in dict(params).items()}
        print(f"Meshing: {mesher_name} params={param_dict}")
        self.__project.mesher_name = mesher_name
        self.__project.mesher_params = dict(param_dict)

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

        # Snapshot boundary assignments on the current surface so the new
        # tet-mesher boundary can inherit them in __on_worker_finished.
        self.__bc_snapshot = snapshot_boundaries(self.__project)

        self.meshingStarted.emit()
        self.__thread.start()
        return True

    @Slot(bool, object)
    def __on_worker_finished(self, success: bool, result):
        # Runs on GUI thread (worker.finished → auto-queued).
        if success and result is not None:
            # Replace project: surface = tet boundary, volume = tet set.
            self.__preproc_ctrl.take_mesh_result(result, self.__bc_snapshot)
        self.__bc_snapshot = None
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
