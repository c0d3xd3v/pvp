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


def component_labels(triangles) -> np.ndarray:
    """Edge-connected components: label per triangle, 0 = largest component."""
    from scipy.sparse import coo_matrix                    # ~0.1 s, not needed at startup
    from scipy.sparse.csgraph import connected_components
    from pvp.geometry.TriangleMeshGraph import _adjacent_face_pairs
    faces = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    if len(faces) == 0:
        return np.zeros(0, dtype=np.int32)
    pairs = _adjacent_face_pairs(faces)
    graph = coo_matrix((np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])),
                       shape=(len(faces), len(faces)))
    _, labels = connected_components(graph, directed=False)
    # renumber by size (descending), ties by first triangle, so the list is stable
    sizes = np.bincount(labels)
    order = np.lexsort((np.arange(len(sizes)), -sizes))
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    return rank[labels].astype(np.int32)


def component_stats(triangles, labels) -> list[SurfaceStats]:
    """SurfaceStats per component (vertices: the ones its triangles use)."""
    faces = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    labels = np.asarray(labels, dtype=np.int64)
    n = int(labels.max()) + 1 if len(labels) else 0
    edges = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    _, first, counts = np.unique(edges, axis=0, return_index=True, return_counts=True)
    # components are edge-connected, so all triangles of an edge share a label
    edge_label = np.repeat(labels, 3)[first]
    open_edges = np.bincount(edge_label[counts == 1], minlength=n)
    nonmanifold = np.bincount(edge_label[counts > 2], minlength=n)
    tris = np.bincount(labels, minlength=n)
    vert_label = np.full(int(faces.max()) + 1 if len(faces) else 0, -1, dtype=np.int64)
    vert_label[faces.ravel()] = np.repeat(labels, 3)
    verts = np.bincount(vert_label[vert_label >= 0], minlength=n)
    return [SurfaceStats(int(verts[i]), int(tris[i]), int(open_edges[i]), int(nonmanifold[i]))
            for i in range(n)]
