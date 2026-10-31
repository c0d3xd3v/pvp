"""Quick checks of an input triangle surface: is it a closed solid?"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SurfaceStats:
    vertices: int
    triangles: int
    open_edges: int          # edges with only one triangle (holes, gaps)
    nonmanifold_edges: int   # edges shared by more than two triangles

    @property
    def closed(self) -> bool:
        """Watertight: every edge borders exactly two triangles."""
        return self.triangles > 0 and self.open_edges == 0 and self.nonmanifold_edges == 0


def surface_stats(vertices, triangles) -> SurfaceStats:
    faces = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    edges = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return SurfaceStats(vertices=len(vertices), triangles=len(faces),
                        open_edges=int(np.count_nonzero(counts == 1)),
                        nonmanifold_edges=int(np.count_nonzero(counts > 2)))
