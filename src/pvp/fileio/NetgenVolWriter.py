import numpy as np

from pvp.fileio.export_model import ExportMesh


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


def write_vol(path: str, mesh: ExportMesh):
    """Write a Netgen .vol volume mesh. Linear tets only (Netgen's own format
    carries that; quadratic export goes to Gmsh/CalculiX instead)."""
    P = mesh.nodes
    T = _orient_tets(P, mesh.tets)
    F = _orient_boundary(P, T, mesh.surface_tri)

    import netgen.meshing as nm   # ~0.15 s, only needed for .vol export

    out = nm.Mesh(dim=3)
    # nm.Pnt: Point3d was removed in newer netgen releases (e.g. 6.2.2608)
    pids = [out.Add(nm.MeshPoint(nm.Pnt(*p))) for p in P]

    # Domains 1..R, one per region; a boundary face descriptor per
    # (BC, domain) pair, since each face descriptor has a single domin.
    regions = mesh.regions if mesh.regions is not None else np.zeros(len(T), dtype=np.int64)
    used = [i for i in range(max(len(mesh.region_names), 1)) if np.any(regions == i)]
    domain = {r: d + 1 for d, r in enumerate(used)}
    tri_region = mesh.surface_regions()
    surfnr = 0
    for i, g in enumerate(mesh.bc_groups):
        tris = np.asarray(g.triangles, dtype=np.int64)
        for r in np.unique(tri_region[tris]):
            surfnr += 1
            fd = out.Add(nm.FaceDescriptor(bc=i + 1, domin=domain[int(r)], domout=0,
                                           surfnr=surfnr))
            for k in tris[tri_region[tris] == r]:
                out.Add(nm.Element2D(fd, [pids[v] for v in F[k]]))
    for i, g in enumerate(mesh.bc_groups):
        # SetBCName is 0-based (index into netgen's names array) even though
        # bc numbers themselves are 1-based; it names every face descriptor
        # with that bc number.
        out.SetBCName(i, g.name)

    for t, r in zip(T, regions):
        out.Add(nm.Element3D(domain[int(r)], [pids[v] for v in t]))
    if mesh.regions is not None:
        for r, d in domain.items():
            out.SetMaterial(d, mesh.region_names[r])

    out.Save(path)
