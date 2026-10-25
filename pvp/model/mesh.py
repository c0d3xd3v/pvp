"""Mesh containers shared by readers, the pre-processing project, the scene
and the writers. Plain NumPy arrays, 0-based indices, coordinates in mm."""
from dataclasses import dataclass, field

import numpy as np


def _rows(a, width: int, dtype) -> np.ndarray:
    a = np.asarray(a if a is not None else [], dtype=dtype)
    return np.ascontiguousarray(a.reshape(-1, width))


@dataclass(eq=False)
class Mesh:
    """Triangle surface, optionally with the tets it bounds and per-triangle
    boundary-condition numbers (1-based) plus their names."""
    vertices:     np.ndarray                    # (N, 3) float64
    triangles:    np.ndarray                    # (M, 3) int64
    tetrahedra:   np.ndarray | None = None      # (K, 4) int64, empty for surfaces
    triangle_bcs: np.ndarray | None = None      # (M,) int32 or empty
    bc_names:     dict[int, str] = field(default_factory=dict)

    def __post_init__(self):
        self.vertices = _rows(self.vertices, 3, np.float64)
        self.triangles = _rows(self.triangles, 3, np.int64)
        self.tetrahedra = _rows(self.tetrahedra, 4, np.int64)
        self.triangle_bcs = np.asarray(
            self.triangle_bcs if self.triangle_bcs is not None else [], dtype=np.int32).ravel()

    @property
    def has_tetrahedra(self) -> bool:
        return len(self.tetrahedra) > 0

    def bbox_diagonal(self) -> float:
        if len(self.vertices) == 0:
            return 0.0
        return float(np.linalg.norm(self.vertices.max(axis=0) - self.vertices.min(axis=0)))


@dataclass(eq=False)
class ResultMesh:
    """Triangle surface with point fields (scalar (N,) or vector (N, k))."""
    vertices:  np.ndarray
    triangles: np.ndarray
    fields:    dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self):
        self.vertices = _rows(self.vertices, 3, np.float64)
        self.triangles = _rows(self.triangles, 3, np.int64)
