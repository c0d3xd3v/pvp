"""In-memory representation of what every mesh writer needs.

An ExportMesh is the hand-off point between the preprocessor and the format
writers: linear-tet connectivity, the oriented boundary surface, and named
boundary-condition groups. For quadratic output, add_midside_nodes() extends
the mesh with Tet10 midside nodes (straight edge midpoints — the user picked
this over projecting onto the input surface, for determinism and stability).
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class BCGroup:
    name: str
    triangles: np.ndarray  # 1-D int, indices into ExportMesh.surface_tri


@dataclass
class ExportMesh:
    """All inputs a writer needs. Coordinates are in model units (mm).

    Every triangle in surface_tri should appear in exactly one BCGroup; the
    preprocessor already collects an explicit "default" group for stray
    triangles, so writers can treat the groups as a full partition.
    """
    nodes: np.ndarray            # (N, 3) float64
    tets: np.ndarray             # (K, 4) int, 0-based linear-tet connectivity
    surface_tri: np.ndarray      # (M, 3) int, 0-based boundary triangle vertices
    bc_groups: list[BCGroup] = field(default_factory=list)

    def __post_init__(self):
        self.nodes = np.ascontiguousarray(self.nodes, dtype=np.float64)
        self.tets = np.ascontiguousarray(self.tets, dtype=np.int64)
        self.surface_tri = np.ascontiguousarray(self.surface_tri, dtype=np.int64)


# Local-edge layout of the midside columns in the Tet10 connectivity below.
# Matches Gmsh element type 11; Abaqus/CalculiX C3D10 uses the same undirected
# edges (its node 8/9/10 label the midnodes on edges 0-3 / 1-3 / 2-3), so no
# reordering is needed between the two. Writers still verify positions.
_TET10_EDGES = np.array([
    (0, 1),  # col 4
    (1, 2),  # col 5
    (0, 2),  # col 6
    (0, 3),  # col 7
    (1, 3),  # col 8
    (2, 3),  # col 9
], dtype=np.int64)


def add_midside_nodes(nodes: np.ndarray, tets: np.ndarray):
    """Return (nodes_ext, tet10) with straight midpoints on every edge.

    Each unique undirected edge produces exactly one midnode, so adjacent tets
    share midnodes along their common edges (which is what Gmsh/CalculiX
    expect). Column layout of tet10:
      0..3 -> corner vertices (copied from `tets`)
      4..9 -> midside nodes on edges in _TET10_EDGES order
    """
    nodes = np.asarray(nodes, dtype=np.float64)
    tets = np.asarray(tets, dtype=np.int64)
    K = tets.shape[0]
    N = nodes.shape[0]

    endpoints = tets[:, _TET10_EDGES]                # (K, 6, 2)
    endpoints = np.sort(endpoints, axis=2)           # undirected: smaller first
    pairs = endpoints.reshape(-1, 2)                 # (K*6, 2)

    unique_pairs, inverse = np.unique(pairs, axis=0, return_inverse=True)
    midside_cols = inverse.reshape(K, 6).astype(np.int64) + N

    midpoints = 0.5 * (nodes[unique_pairs[:, 0]] + nodes[unique_pairs[:, 1]])
    nodes_ext = np.vstack([nodes, midpoints])

    tet10 = np.empty((K, 10), dtype=np.int64)
    tet10[:, :4] = tets
    tet10[:, 4:] = midside_cols
    return nodes_ext, tet10
