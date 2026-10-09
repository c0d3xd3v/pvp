import math

import numpy as np

from meshing.TetMesher import ParamSpec, MeshingResult, ProgressFn


class FTetWildMesher:
    name = "FloatTetwild"
    param_schema = [
        ParamSpec("stop_energy", "Stop Energy",
                  default=10.0, min_value=5.0, max_value=100.0, step=1.0,
                  tooltip="Quality target of the tet optimization. Lower = better tets, "
                          "slower. Limited effect (capped at 80 iterations)."),
        ParamSpec("ideal_edge_length_rel", "Edge Length (rel)",
                  default=0.05, min_value=0.005, max_value=0.5, step=0.005,
                  tooltip="Target edge length relative to the bbox diagonal. Mainly controls "
                          "the interior; at the surface, epsilon and geometry dominate."),
        ParamSpec("eps_rel", "Epsilon (rel)",
                  default=0.0002, min_value=0.0001, max_value=0.01, step=0.0001,
                  tooltip="Max. deviation of the new surface from the input, relative to the "
                          "bbox diagonal. Smaller = surface detail is kept, but many more "
                          "tets. 0.001 = coarse/faceted."),
    ]

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

    def mesh(self, vertices, triangles, params, progress: ProgressFn | None = None):
        # Import here so the app runs even if the wrapper isn't built yet
        from pyFloatTetwildWrapper import FTetWildWrapper

        V = np.asarray(vertices, dtype=np.float64)
        F = np.asarray(triangles, dtype=np.int32)
        V_scaled, scale, translation = self._scale_to_box(V)

        w = FTetWildWrapper(
            stop_energy=float(params.get("stop_energy", 10.0)),
            ideal_edge_length_rel=float(params.get("ideal_edge_length_rel", 0.05)),
            eps_rel=float(params.get("eps_rel", 0.0002)),
        )

        if progress is not None:
            def _bridge(stage: str, it: int, total: int):
                label = self._STAGE_LABEL.get(stage, stage)
                if stage == "optimizing" and total > 0:
                    label = f"Optimizing ({it}/{total})"
                    frac = it / total
                else:
                    frac = math.nan
                try:
                    progress(label, frac)
                except Exception:
                    pass
            # setProgressCallback exists on patched wrappers only; fall back
            # silently if someone runs an older build.
            if hasattr(w, "setProgressCallback"):
                w.setProgressCallback(_bridge)

        w.loadMeshGeometry(V_scaled, F)
        w.tetrahedralize()
        tris, tets, nods = w.getSurfaceIndices()

        nods_out = np.asarray(nods, dtype=np.float64) / scale + translation
        return MeshingResult(
            vertices=nods_out,
            triangles=np.asarray(tris, dtype=np.int32),
            tetrahedra=np.asarray(tets, dtype=np.int32),
        )

    @staticmethod
    def _scale_to_box(V, target_size: float = 1000.0):
        """FTetWild's tolerances behave best when the mesh sits in a well-scaled
        bounding box (~1000 units). Scale before, invert after."""
        bb_min = V.min(axis=0)
        bb_max = V.max(axis=0)
        max_extent = float((bb_max - bb_min).max())
        scale = target_size / max_extent
        return (V - bb_min) * scale, scale, bb_min
