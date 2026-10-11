from dataclasses import dataclass
from typing import Callable, Optional, Protocol
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


# Progress callback: (stage_label, fraction, max_energy, v_num, t_num).
# fraction is in [0, 1] when known or float('nan') for indeterminate.
# max_energy is NaN and v_num / t_num are -1 outside the main optimization
# phase (where metrics aren't available).
ProgressFn = Callable[[str, float, float, int, int], None]


class TetMesher(Protocol):
    name: str

    def param_schema(self, bbox_diagonal: float | None = None) -> list[ParamSpec]:
        """Return the parameter schema. When a bbox diagonal (in model units)
        is given, absolute-unit parameters get sensible defaults for that
        geometry."""
        ...

    def mesh(self, vertices: np.ndarray, triangles: np.ndarray,
             params: dict,
             progress: Optional[ProgressFn] = None) -> MeshingResult: ...
