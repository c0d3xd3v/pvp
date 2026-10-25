"""ExportMesh + add_midside_nodes: shared data model for mesh writers."""
import numpy as np
import pytest

from pvp.fileio.export_model import (
    ExportMesh, BCGroup, add_midside_nodes, tri6_connectivity,
)


def test_export_mesh_coerces_dtypes():
    m = ExportMesh(
        nodes=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
        tets=[[0, 1, 2, 3]],
        surface_tri=[[0, 1, 2]],
    )
    assert m.nodes.dtype == np.float64
    assert m.tets.dtype == np.int64
    assert m.surface_tri.dtype == np.int64
    assert m.bc_groups == []


def test_midside_count_matches_unique_edges(unit_cube):
    P, T, _ = unit_cube
    nodes_ext, tet10, _ = add_midside_nodes(P, T)
    # Count unique undirected edges across all tets, independently.
    all_edges = np.vstack([
        T[:, [0, 1]], T[:, [1, 2]], T[:, [0, 2]],
        T[:, [0, 3]], T[:, [1, 3]], T[:, [2, 3]],
    ])
    all_edges = np.sort(all_edges, axis=1)
    unique_edges = np.unique(all_edges, axis=0)

    assert nodes_ext.shape[0] == P.shape[0] + unique_edges.shape[0]
    assert tet10.shape == (T.shape[0], 10)
    assert np.array_equal(tet10[:, :4], T)


def test_midside_nodes_are_edge_midpoints(unit_cube):
    """Each midside column of tet10 must index a node that lies at the
    midpoint of the corresponding local edge — this is the invariant every
    writer relies on, so verify it geometrically rather than trusting the
    code's edge table."""
    P, T, _ = unit_cube
    nodes_ext, tet10, _ = add_midside_nodes(P, T)
    edges = [(0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3)]

    for i, (a, b) in enumerate(edges):
        mids = nodes_ext[tet10[:, 4 + i]]
        expected = 0.5 * (nodes_ext[tet10[:, a]] + nodes_ext[tet10[:, b]])
        assert np.allclose(mids, expected)


def test_midside_shared_between_adjacent_tets():
    """Two tets sharing an edge must reference the same midside node."""
    # Two tets glued on the face (0, 1, 2).
    P = np.array([
        [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, -1],
    ], dtype=np.float64)
    T = np.array([
        [0, 1, 2, 3],
        [0, 1, 2, 4],
    ])
    _, tet10, _ = add_midside_nodes(P, T)
    # Edge (0, 1) is shared; midside col 4 (edge 0-1) must match across tets.
    assert tet10[0, 4] == tet10[1, 4]
    # Edge (0, 3) in tet 0 and edge (0, 3) → but tet 1 has vertex 4 not 3,
    # so its col 7 (edge 0-3-local = 0-4-global) must differ.
    assert tet10[0, 7] != tet10[1, 7]


def test_tri6_connectivity_lies_on_edges(unit_cube):
    P, T, F = unit_cube
    nodes_ext, _, edge_midnode = add_midside_nodes(P, T)
    tri6 = tri6_connectivity(F, edge_midnode)
    assert tri6.shape == (F.shape[0], 6)
    assert np.array_equal(tri6[:, :3], F)
    for i, (a, b) in enumerate([(0, 1), (1, 2), (0, 2)]):
        mids = nodes_ext[tri6[:, 3 + i]]
        expected = 0.5 * (nodes_ext[tri6[:, a]] + nodes_ext[tri6[:, b]])
        assert np.allclose(mids, expected)


def test_bc_group_holds_triangle_indices():
    g = BCGroup("wall", np.array([3, 7, 11]))
    assert g.name == "wall"
    assert list(g.triangles) == [3, 7, 11]
