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


# Canonical local-edge layout for the midside columns of our Tet10 arrays.
# Matches Abaqus/CalculiX C3D10 (and VTK Lagrange tet). Gmsh element type 11
# swaps the last two midnodes — writers that target Gmsh use TET10_TO_GMSH to
# permute cols 8 and 9. The underlying midside *points* are the same for both;
# only the output position differs.
_TET10_EDGES = np.array([
    (0, 1),  # col 4
    (1, 2),  # col 5
    (0, 2),  # col 6
    (0, 3),  # col 7
    (1, 3),  # col 8  (Abaqus node 9  / Gmsh node 10)
    (2, 3),  # col 9  (Abaqus node 10 / Gmsh node 9)
], dtype=np.int64)

TET10_TO_GMSH = np.array([0, 1, 2, 3, 4, 5, 6, 7, 9, 8], dtype=np.int64)

_TRI6_EDGES = [(0, 1), (1, 2), (0, 2)]


def add_midside_nodes(nodes: np.ndarray, tets: np.ndarray):
    """Return (nodes_ext, tet10, edge_midnode) with straight midpoints on every edge.

    Each unique undirected edge produces exactly one midnode, so adjacent tets
    share midnodes along their common edges (which is what Gmsh/CalculiX
    expect). Column layout of tet10 is the Abaqus-style order documented on
    _TET10_EDGES. edge_midnode maps (v_low, v_high) → node index, so writers
    can look up midnodes on surface-triangle edges without rebuilding the map.
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

    edge_midnode = {
        (int(a), int(b)): N + i for i, (a, b) in enumerate(unique_pairs)
    }
    return nodes_ext, tet10, edge_midnode


def tri6_connectivity(triangles: np.ndarray, edge_midnode: dict) -> np.ndarray:
    """Promote linear surface triangles to Tri6 by looking up midnodes on each
    triangle edge in a pre-built edge→midnode map (from add_midside_nodes).
    Column layout matches Gmsh element type 9 and Abaqus STRI65:
      0..2 -> corners, 3..5 -> midnodes on edges (0,1), (1,2), (0,2).
    Every triangle edge must be a tet edge, otherwise the lookup fails."""
    triangles = np.asarray(triangles, dtype=np.int64)
    tri6 = np.empty((triangles.shape[0], 6), dtype=np.int64)
    tri6[:, :3] = triangles
    for i, (a, b) in enumerate(_TRI6_EDGES):
        pairs = np.sort(np.stack([triangles[:, a], triangles[:, b]], axis=1), axis=1)
        tri6[:, 3 + i] = [edge_midnode[(int(p[0]), int(p[1]))] for p in pairs]
    return tri6
