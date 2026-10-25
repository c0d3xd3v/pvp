import itertools

import numpy as np

from pvp.model.mesh import Mesh

# Corner k of the box has signs (s0, s1, s2) with k = 4*(s0>0) + 2*(s1>0) + (s2>0).
_SIGNS = np.array(list(itertools.product((-1, 1), repeat=3)), dtype=np.float64)
# Two triangles per side (-x, +x, -y, +y, -z, +z), consistently oriented with
# normals pointing into the box, as the box generator always did.
_TRIANGLES = np.array([
    [0, 2, 3], [0, 3, 1],  [4, 7, 6], [4, 5, 7],
    [0, 5, 4], [0, 1, 5],  [2, 6, 7], [2, 7, 3],
    [0, 4, 6], [0, 6, 2],  [1, 7, 5], [1, 3, 7],
], dtype=np.int64)


def bounding_box_mesh(vertices, scale: float = 1.1) -> Mesh:
    """Axis-aligned bounding box of the points, enlarged by `scale` around
    its center, as a closed triangle mesh (later: oriented box via PCA)."""
    V = np.asarray(vertices, dtype=np.float64)
    lo, hi = V.min(axis=0), V.max(axis=0)
    center, half = (lo + hi) / 2, (hi - lo) / 2 * scale
    return Mesh(vertices=center + _SIGNS * half, triangles=_TRIANGLES)
