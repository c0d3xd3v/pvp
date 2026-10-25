import numpy as np


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0, v1, v2 = (vertices[faces[:, k]] for k in range(3))
    normals = np.cross(v1 - v0, v2 - v0)
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms[norms == 0] = 1.0     # degenerate triangles: zero normal, never "smooth"
    return normals / norms


def _adjacent_face_pairs(faces: np.ndarray) -> np.ndarray:
    """(P, 2) pairs of faces sharing an edge. A non-manifold edge with k > 2
    faces contributes all k*(k-1)/2 pairs."""
    m = len(faces)
    edges = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)   # (3M, 2)
    owner = np.repeat(np.arange(m, dtype=np.int64), 3)
    _, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()
    order = np.argsort(inverse, kind="stable")
    starts = np.concatenate(([0], np.cumsum(counts)))

    two = np.flatnonzero(counts == 2)
    pairs = [np.column_stack((owner[order[starts[two]]], owner[order[starts[two] + 1]]))]
    for e in np.flatnonzero(counts > 2):        # rare, plain loop is fine
        group = owner[order[starts[e]:starts[e + 1]]]
        i, j = np.triu_indices(len(group), k=1)
        pairs.append(np.column_stack((group[i], group[j])))
    return np.concatenate(pairs).astype(np.int64).reshape(-1, 2)


class TriangleMeshGraph:
    """Edge-adjacency of a triangle surface, split into smooth regions: faces
    connected across edges whose normals differ by less than the compare
    angle (what a click on the surface selects)."""

    def __init__(self, vertices, faces, angle: float = 10.0):
        vertices = np.asarray(vertices, dtype=np.float64)
        faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
        self.num_faces = len(faces)
        self.__normals = _face_normals(vertices, faces)
        self.__pairs = _adjacent_face_pairs(faces)
        self.__angle = float(angle)
        self.__regions = None

    def set_normal_compare_angle(self, angle: float):
        self.__angle = float(angle)
        self.__regions = None

    def region(self, face_id: int) -> np.ndarray:
        """All faces in the smooth region of face_id."""
        labels, order, starts = self.__region_index()
        lab = labels[face_id]
        return order[starts[lab]:starts[lab + 1]]

    def region_label(self, face_id: int) -> int:
        return int(self.__region_index()[0][face_id])

    def __region_index(self):
        # Computed once per angle; a Python flood fill per hover took up to
        # seconds on large flat faces.
        if self.__regions is None:
            from scipy.sparse import coo_matrix                    # ~0.1 s, not needed at startup
            from scipy.sparse.csgraph import connected_components
            n = self.__normals
            p0, p1 = self.__pairs[:, 0], self.__pairs[:, 1]
            smooth = np.einsum("ij,ij->i", n[p0], n[p1]) > np.cos(np.radians(self.__angle))
            graph = coo_matrix((np.ones(int(smooth.sum()), dtype=np.int8), (p0[smooth], p1[smooth])),
                               shape=(self.num_faces, self.num_faces))
            _, labels = connected_components(graph, directed=False)
            order = np.argsort(labels, kind="stable")
            starts = np.searchsorted(labels[order], np.arange(labels.max() + 2))
            self.__regions = (labels, order, starts)
        return self.__regions
