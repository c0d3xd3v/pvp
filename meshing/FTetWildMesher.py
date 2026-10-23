import math
import threading

import numpy as np

from meshing.TetMesher import ParamSpec, MeshingResult, ProgressFn


class MeshingCancelled(Exception):
    """Raised by FTetWildMesher.mesh when a cancel request is honored."""


# fTetWild expresses edge length and surface tolerance relative to the input
# bbox diagonal. We expose both to the user as absolute values in model units
# (mm — the project assumes STL input is in mm) and convert here. Defaults are
# the usual relative fractions, so a fresh surface produces the same mesh as
# before this unit change.
_EDGE_DEFAULT_FRAC = 0.05
_EPS_DEFAULT_FRAC = 0.0002


class FTetWildMesher:
    name = "FloatTetwild"

    def __init__(self):
        # Guards the reference to the wrapper currently running inside mesh().
        # request_cancel runs on the GUI thread; mesh() runs on the worker.
        self._cancel_lock = threading.Lock()
        self._current_wrapper = None

    _STAGE_LABEL = {
        "preprocessing":      "Preprocessing…",
        "tetrahedralizing":   "Tetrahedralizing…",
        "inserting":          "Inserting triangles…",
        "optimizing":         "Optimizing",
        "correcting surface": "Correcting surface…",
        "smoothing boundary": "Smoothing boundary…",
        "filtering outside":  "Filtering outside…",
        "done":               "Finishing…",
    }

    def param_schema(self, bbox_diagonal: float | None = None) -> list[ParamSpec]:
        # Fallback diagonal when no surface is loaded yet — keeps the UI
        # usable with reasonable defaults. 1000 mm matches fTetWild's internal
        # target scale.
        d = float(bbox_diagonal) if bbox_diagonal and bbox_diagonal > 0 else 1000.0
        edge_default = d * _EDGE_DEFAULT_FRAC
        eps_default = d * _EPS_DEFAULT_FRAC
        return [
            ParamSpec("stop_energy", "Stop Energy",
                      default=10.0, min_value=5.0, max_value=100.0, step=1.0,
                      tooltip="Quality target of the tet optimization. Lower = better tets, "
                              "slower. Limited effect (capped at 80 iterations)."),
            ParamSpec("ideal_edge_length", "Edge Length (mm)",
                      default=edge_default,
                      min_value=1e-6,
                      max_value=d,
                      step=self._nice_step(edge_default),
                      tooltip="Target edge length in model units (mm). Default = 5% of the "
                              "bbox diagonal. Mainly controls the interior; at the surface, "
                              "epsilon and geometry dominate."),
            ParamSpec("eps", "Epsilon (mm)",
                      default=eps_default,
                      min_value=1e-9,
                      max_value=d * 0.05,
                      step=self._nice_step(eps_default),
                      tooltip="Max. deviation of the new surface from the input, in mm. "
                              "Default = 0.02% of the bbox diagonal. Smaller = surface "
                              "detail is kept, but many more tets."),
        ]

    def mesh(self, vertices, triangles, params, progress: ProgressFn | None = None):
        # Import here so the app runs even if the wrapper isn't built yet
        import pyFloatTetwildWrapper as pyftw
        FTetWildWrapper = pyftw.FTetWildWrapper

        V = np.asarray(vertices, dtype=np.float64)
        F = np.asarray(triangles, dtype=np.int32)
        bbox_diag = float(np.linalg.norm(V.max(axis=0) - V.min(axis=0)))
        if bbox_diag <= 0.0:
            raise ValueError("input surface has zero extent")
        V_scaled, scale, translation = self._scale_to_box(V)

        edge_mm = float(params.get("ideal_edge_length", bbox_diag * _EDGE_DEFAULT_FRAC))
        eps_mm = float(params.get("eps", bbox_diag * _EPS_DEFAULT_FRAC))
        w = FTetWildWrapper(
            stop_energy=float(params.get("stop_energy", 10.0)),
            ideal_edge_length_rel=edge_mm / bbox_diag,
            eps_rel=eps_mm / bbox_diag,
        )

        if progress is not None:
            def _bridge(stage: str, it: int, total: int,
                        max_energy: float, v_num: int, t_num: int):
                label = self._STAGE_LABEL.get(stage, stage)
                if stage == "optimizing" and total > 0:
                    label = f"Optimizing ({it}/{total})"
                    frac = it / total
                else:
                    frac = math.nan
                try:
                    progress(label, frac, max_energy, v_num, t_num)
                except Exception:
                    pass
            # setProgressCallback exists on patched wrappers only; fall back
            # silently if someone runs an older build.
            if hasattr(w, "setProgressCallback"):
                w.setProgressCallback(_bridge)

        with self._cancel_lock:
            self._current_wrapper = w
        try:
            w.loadMeshGeometry(V_scaled, F)
            w.tetrahedralize()
            tris, tets, nods = w.getSurfaceIndices()
        except pyftw.Cancelled:
            # fTetWild/TBB stacks are not exception-safe, so the wrapper may
            # hold half-built state. Dropping our only reference lets Python
            # tear it down after we unwind.
            raise MeshingCancelled()
        finally:
            with self._cancel_lock:
                self._current_wrapper = None

        nods_out = np.asarray(nods, dtype=np.float64) / scale + translation
        return MeshingResult(
            vertices=nods_out,
            triangles=np.asarray(tris, dtype=np.int32),
            tetrahedra=np.asarray(tets, dtype=np.int32),
        )

    def request_cancel(self) -> bool:
        """Signal the running mesh() call to abort at the next progress tick.
        Safe to call from any thread; no-op if nothing is running."""
        with self._cancel_lock:
            w = self._current_wrapper
        if w is None:
            return False
        try:
            w.requestCancel()
        except Exception:
            return False
        return True

    @staticmethod
    def _nice_step(x: float) -> float:
        """Round-ish step size one order of magnitude below x, so the UI
        spinner moves in sensible increments regardless of mesh scale."""
        if x <= 0:
            return 0.001
        return 10 ** math.floor(math.log10(x) - 1)

    @staticmethod
    def _scale_to_box(V, target_size: float = 1000.0):
        """FTetWild's tolerances behave best when the mesh sits in a well-scaled
        bounding box (~1000 units). Scale before, invert after."""
        bb_min = V.min(axis=0)
        bb_max = V.max(axis=0)
        max_extent = float((bb_max - bb_min).max())
        scale = target_size / max_extent
        return (V - bb_min) * scale, scale, bb_min
