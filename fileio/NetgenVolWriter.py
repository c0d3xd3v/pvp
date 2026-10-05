import numpy as np
import netgen.meshing as nm


def _orient_tets(P, T):
    """Netgen's own meshes use tets with negative det(p1-p0, p2-p0, p3-p0);
    flip any element that has the other orientation."""
    d = np.einsum('ij,ij->i',
                  np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]),
                  P[T[:, 3]] - P[T[:, 0]])
    T = T.copy()
    flip = d > 0
    T[flip, 2], T[flip, 3] = T[flip, 3], T[flip, 2].copy()
    return T


def _orient_boundary(P, T, F):
    """Boundary faces need a right-hand normal pointing out of the domain
    (FaceDescriptor domin=1, domout=0). Use the opposite vertex of the tet
    adjacent to each face to decide."""
    opposite = {}
    for t in T:
        for j in range(4):
            face = tuple(sorted((t[(j + 1) % 4], t[(j + 2) % 4], t[(j + 3) % 4])))
            opposite[face] = t[j]
    F = F.copy()
    for i, f in enumerate(F):
        k = opposite.get(tuple(sorted(f)))
        if k is None:
            raise ValueError(f"surface triangle {i} {tuple(f)} is not a face of any tet")
        n = np.cross(P[f[1]] - P[f[0]], P[f[2]] - P[f[0]])
        if np.dot(n, P[k] - P[f[0]]) > 0:   # normal points into the tet
            F[i, 1], F[i, 2] = F[i, 2], F[i, 1]
    return F


def write_vol(path, vertices, tetrahedra, triangles, groups):
    """Write a Netgen .vol volume mesh.

    vertices   (N, 3) coordinates
    tetrahedra (K, 4) 0-based vertex indices
    triangles  (M, 3) 0-based vertex indices of the boundary surface
    groups     [(bc_name, [triangle indices]), ...] — every triangle should be
               in exactly one group, otherwise the exported surface has holes.
    """
    P = np.asarray(vertices, dtype=np.float64)
    T = _orient_tets(P, np.asarray(tetrahedra, dtype=np.int64))
    F = _orient_boundary(P, T, np.asarray(triangles, dtype=np.int64))

    mesh = nm.Mesh(dim=3)
    pids = [mesh.Add(nm.MeshPoint(nm.Point3d(*p))) for p in P]

    for i, (name, indices) in enumerate(groups):
        fd = mesh.Add(nm.FaceDescriptor(bc=i + 1, domin=1, domout=0, surfnr=i + 1))
        # SetBCName is 0-based (index into netgen's names array) even though
        # bc numbers themselves are 1-based.
        mesh.SetBCName(i, name)
        for k in indices:
            mesh.Add(nm.Element2D(fd, [pids[v] for v in F[k]]))

    for t in T:
        mesh.Add(nm.Element3D(1, [pids[v] for v in t]))

    mesh.Save(path)
