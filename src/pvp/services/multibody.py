"""Meshing several bodies (connected components of the input surface) at once.

Two modes:
- "conforming": one mesher run over all bodies. fTetWild inserts every input
  triangle, so the tet mesh conforms to the contact faces; each tet is then
  labelled with the body whose surface encloses it (winding number).
- "per_body": one mesher run per body, the results are concatenated. Nodes on
  contact faces are duplicated and the contact faces stay boundary faces
  (coupled in the solver with *TIE / *CONTACT).

Region = component label (index into Project.surface_components).
"""
import numpy as np

from pvp.services.boundary_transfer import closest_cells

CONFORMING = "conforming"
PER_BODY = "per_body"
MESH_MODES = (CONFORMING, PER_BODY)


def body_faces(surface_components, meshed_components) -> list[tuple[int, np.ndarray]]:
    """(component label, surface triangle indices) per body that gets meshed."""
    labels = np.asarray(surface_components, dtype=np.int64)
    return [(int(c), np.flatnonzero(labels == c))
            for c in np.flatnonzero(np.asarray(meshed_components, dtype=bool))]


def concat_meshes(parts) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """parts: [(label, vertices, triangles, tetrahedra)] -> (V, F, T, regions
    per tet, label per boundary triangle). Nodes are not shared between parts."""
    Vs, Fs, Ts, regions, tri_label, offset = [], [], [], [], [], 0
    for label, V, F, T in parts:
        V = np.asarray(V, dtype=np.float64)
        F = np.asarray(F, dtype=np.int64).reshape(-1, 3)
        T = np.asarray(T, dtype=np.int64).reshape(-1, 4)
        Vs.append(V)
        Fs.append(F + offset)
        Ts.append(T + offset)
        regions.append(np.full(len(T), label, dtype=np.int32))
        tri_label.append(np.full(len(F), label, dtype=np.int32))
        offset += len(V)
    return (np.vstack(Vs), np.vstack(Fs), np.vstack(Ts),
            np.concatenate(regions), np.concatenate(tri_label))


def label_tets_by_winding(vertices, tetrahedra, surface_vertices, surface_triangles,
                          bodies) -> np.ndarray:
    """Body label per tet: the body whose surface winds most around the tet's
    centroid (≈1 inside a closed body, ≈0 outside)."""
    T = np.asarray(tetrahedra, dtype=np.int64)
    if len(bodies) == 1:
        return np.full(len(T), bodies[0][0], dtype=np.int32)
    import igl
    centroids = np.asarray(vertices, dtype=np.float64)[T].mean(axis=1)
    SV = np.asarray(surface_vertices, dtype=np.float64)
    SF = np.asarray(surface_triangles, dtype=np.int64)
    w = np.column_stack([igl.fast_winding_number(SV, SF[faces], centroids)
                         for _, faces in bodies])
    labels = np.array([label for label, _ in bodies], dtype=np.int32)
    return labels[np.argmax(w, axis=1)]


def boundary_regions(tetrahedra, regions, triangles) -> np.ndarray:
    """Region of the tet each boundary triangle is a face of."""
    T = np.asarray(tetrahedra, dtype=np.int64)
    F = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    faces = np.sort(T[:, [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]].reshape(-1, 3), axis=1)
    owner = np.repeat(np.asarray(regions, dtype=np.int32), 4)
    # boundary faces belong to exactly one tet: match them against all tet faces
    keys, idx = np.unique(faces, axis=0, return_index=True)
    query = np.sort(F, axis=1)
    pos = _find_rows(keys, query)
    if np.any(pos < 0):
        raise ValueError(f"{int(np.sum(pos < 0))} boundary triangles are not tet faces")
    return owner[idx[pos]]


def _find_rows(sorted_rows, query) -> np.ndarray:
    """Index of each query row in sorted_rows (lexicographically sorted,
    unique), -1 where missing."""
    if len(query) == 0:
        return np.zeros(0, dtype=np.int64)
    n = int(max(sorted_rows.max(), query.max())) + 1
    a = (sorted_rows[:, 0] * n + sorted_rows[:, 1]) * n + sorted_rows[:, 2]
    b = (query[:, 0] * n + query[:, 1]) * n + query[:, 2]
    pos = np.searchsorted(a, b)
    pos = np.minimum(pos, len(a) - 1)
    return np.where(a[pos] == b, pos, -1)


def face_map_per_body(surface_vertices, surface_triangles, bodies,
                      vertices, triangles, tri_label) -> np.ndarray:
    """Closest input triangle per boundary triangle, searched only among the
    triangles of the body it belongs to: a contact face of body B must not
    take the partition of the coincident face of body A."""
    F = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    SF = np.asarray(surface_triangles, dtype=np.int64)
    tri_label = np.asarray(tri_label)
    face_map = np.full(len(F), -1, dtype=np.int64)
    for label, faces in bodies:
        mine = np.flatnonzero(tri_label == label)
        if len(mine):
            face_map[mine] = faces[closest_cells(surface_vertices, SF[faces], vertices, F[mine])]
    if np.any(face_map < 0):
        raise ValueError(f"{int(np.sum(face_map < 0))} boundary triangles belong to no body")
    return face_map


def mesh_bodies(mesher, surface_vertices, surface_triangles, bodies, params,
                mode=CONFORMING, progress=None, cancelled=lambda: False):
    """Mesh the bodies [(label, surface faces)] of the input surface.

    Returns (MeshingResult, face map, regions): face map = input surface
    triangle per boundary triangle, regions = body label per tet (None with a
    single body, which then meshes exactly as before). `cancelled` is polled
    between the per-body runs; a run itself is cancelled by the mesher."""
    from pvp.meshing.FTetWildMesher import MeshingCancelled
    from pvp.meshing.TetMesher import MeshingResult
    from pvp.model.mesh import Mesh

    if mode not in MESH_MODES:
        raise ValueError(f"unknown mesh mode {mode!r}")
    SV = np.asarray(surface_vertices, dtype=np.float64)
    SF = np.asarray(surface_triangles, dtype=np.int64)
    if not bodies:
        raise ValueError("no body to mesh")

    def part(faces):
        p = Mesh(vertices=SV, triangles=SF[faces]).surface_only()
        return p.vertices, p.triangles.astype(np.int32)

    def note(label):
        if progress is not None:
            progress(label, float("nan"), float("nan"), -1, -1)

    if mode == PER_BODY and len(bodies) > 1:
        parts = []
        for i, (label, faces) in enumerate(bodies):
            if cancelled():
                raise MeshingCancelled()
            prefixed = None
            if progress is not None:
                def prefixed(stage, *rest, _i=i):
                    progress(f"Part {_i + 1}/{len(bodies)}: {stage}", *rest)
            V, F = part(faces)
            r = mesher.mesh(V, F, params, progress=prefixed)
            parts.append((label, r.vertices, r.triangles, r.tetrahedra))
        V, F, T, regions, tri_label = concat_meshes(parts)
        result = MeshingResult(vertices=V, triangles=F.astype(np.int32),
                               tetrahedra=T.astype(np.int32))
    else:
        V, F = part(np.concatenate([faces for _, faces in bodies]))
        result = mesher.mesh(V, F, params, progress=progress)
        regions = tri_label = None
        if len(bodies) > 1:
            note("Labelling bodies")
            regions = label_tets_by_winding(result.vertices, result.tetrahedra, SV, SF, bodies)
            tri_label = boundary_regions(result.tetrahedra, regions, result.triangles)

    # Which input triangle each boundary triangle takes its partition from
    note("Transferring boundaries")
    if tri_label is None:
        tri_label = np.full(len(result.triangles), bodies[0][0], dtype=np.int32)
        bodies_for_map = [(bodies[0][0], np.concatenate([f for _, f in bodies]))]
    else:
        bodies_for_map = bodies
    face_map = face_map_per_body(SV, SF, bodies_for_map, result.vertices, result.triangles,
                                 tri_label)
    return result, face_map, (regions if len(bodies) > 1 else None)
