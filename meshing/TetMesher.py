from dataclasses import dataclass
from typing import Protocol
import numpy as np


@dataclass
class ParamSpec:
    name: str
    label: str
    default: float
    min_value: float
    max_value: float
    step: float = 0.001
    tooltip: str = ""


@dataclass
class MeshingResult:
    vertices: np.ndarray    # (N, 3) float
    triangles: np.ndarray   # (M, 3) int — outer surface
    tetrahedra: np.ndarray  # (K, 4) int


class TetMesher(Protocol):
    name: str
    param_schema: list[ParamSpec]

    def mesh(self, vertices: np.ndarray, triangles: np.ndarray,
             params: dict) -> MeshingResult: ...
