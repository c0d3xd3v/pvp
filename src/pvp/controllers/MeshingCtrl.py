import traceback

from PySide6.QtCore import Slot, Signal, QObject, QThread

from pvp.meshing.FTetWildMesher import FTetWildMesher, MeshingCancelled
from pvp.model.project import Project
from pvp.services import multibody


class _MeshingWorker(QObject):
    """Runs on a background QThread. Owns no VTK/GUI state."""
    finished = Signal(bool, object)   # success, (MeshingResult, face map, regions) or None
    # stage label, fraction (NaN = indeterminate), max_energy (NaN outside the
    # optimization loop), v_num, t_num (-1 outside the optimization loop)
    progress = Signal(str, float, float, int, int)

    def __init__(self, mesher, surface, bodies, params, mode):
        """surface: the input surface; bodies: [(component label, its
        triangles)] that get meshed; mode: see services/multibody.py."""
        super().__init__()
        self.__mesher = mesher
        self.__surface = surface
        self.__bodies = bodies
        self.__params = params
        self.__mode = mode
        self.cancel_requested = False   # set from the GUI thread, polled between runs

    @Slot()
    def run(self):
        try:
            result = multibody.mesh_bodies(
                self.__mesher, self.__surface.vertices, self.__surface.triangles,
                self.__bodies, self.__params, self.__mode,
                progress=self.progress.emit, cancelled=lambda: self.cancel_requested)
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

    @Slot(result=str)
    def getMeshMode(self) -> str:
        return self.__project.mesh_mode

    @Slot(str, 'QVariantMap', str, result=bool)
    def runMesher(self, mesher_name: str, params, mode: str = multibody.CONFORMING) -> bool:
        if self.__thread is not None and self.__thread.isRunning():
            print("Meshing: already running")
            return False

        m = self.__meshers.get(mesher_name)
        if m is None:
            return False
        # Always the input surface (its checked components); a previous
        # result is replaced
        surface = self.__project.surface
        if surface is None:
            print("Meshing: no input data loaded")
            return False
        project = self.__project
        bodies = multibody.body_faces(project.surface_components, project.meshed_components)
        if not bodies:
            print("Meshing: no component selected")
            return False
        if mode not in multibody.MESH_MODES:
            mode = multibody.CONFORMING

        param_dict = {k: float(v) for k, v in dict(params).items()}
        print(f"Meshing: {mesher_name} params={param_dict} bodies={len(bodies)} mode={mode}")
        project.mesher_name = mesher_name
        project.mesher_params = dict(param_dict)
        project.mesh_mode = mode

        self.__thread = QThread()
        self.__worker = _MeshingWorker(m, surface, bodies, param_dict, mode)
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
            self.__preproc_ctrl.take_mesh_result(*result)
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
        if self.__worker is not None:
            self.__worker.cancel_requested = True
        for m in self.__meshers.values():
            # Each mesher ignores the request when it isn't the one running.
            try:
                m.request_cancel()
            except AttributeError:
                pass
        return True
