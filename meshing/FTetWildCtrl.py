import sys
import numpy as np

_FTETWILD_BUILD = "/home/kaih/Development/VibroAcoustic/meshing/build"

if _FTETWILD_BUILD not in sys.path:
    sys.path.insert(0, _FTETWILD_BUILD)


class FTetWildCtrl:
    """
    Thin controller around the FloatTetwild Python wrapper.
    Takes a surface mesh (vertices + triangles) and optional background mesh,
    returns (nodes, tets, surface_tris) as numpy arrays.
    """

    def __init__(self,
                 stop_energy: float = 10.0,
                 edge_length_rel: float = 0.05,
                 eps_rel: float = 0.001):
        self._stop_energy    = stop_energy
        self._edge_length_rel = edge_length_rel
        self._eps_rel        = eps_rel

    def mesh(self,
             vertices: np.ndarray,
             triangles: np.ndarray,
             background_mesh=None
             ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Returns (nodes, tets, surface_tris).
        background_mesh: OBBMeshGenerator instance or None.
        """
        import pyFloatTetwildWrapper as fw

        wrapper = fw.FTetWildWrapper(
            self._stop_energy,
            self._edge_length_rel,
            self._eps_rel,
        )

        V = np.array(vertices, dtype=np.float32)
        F = np.array(triangles, dtype=np.int32)
        wrapper.loadMeshGeometry(V, F)
        wrapper.tetrahedralize()
        tris, tets, nodes = wrapper.getSurfaceIndices()
        return np.array(nodes), np.array(tets), np.array(tris)
