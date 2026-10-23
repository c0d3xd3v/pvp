"""Gmsh .msh writers.

MSH 2.2 ASCII is the broadest-compatibility target (every CalculiX/ccx,
Elmer, OpenFOAM, meshio build understands it). Each BC becomes a dim=2
Physical Name; all tets land in a dim=3 Physical "Volume".
"""
import numpy as np

from fileio.export_model import (
    ExportMesh, add_midside_nodes, tri6_connectivity, TET10_TO_GMSH,
)


_VOLUME_PHYS = "Volume"


def _assign_physical_tags(mesh: ExportMesh):
    """BC groups get tags 1..N (dim=2), the volume gets tag N+1 (dim=3).
    Physical tags share one integer namespace across dims in MSH 2.2."""
    phys = []       # (dim, tag, name)
    bc_tag = {}     # bc_group index -> tag
    for i, g in enumerate(mesh.bc_groups):
        tag = i + 1
        phys.append((2, tag, g.name))
        bc_tag[i] = tag
    vol_tag = len(mesh.bc_groups) + 1
    phys.append((3, vol_tag, _VOLUME_PHYS))
    return phys, bc_tag, vol_tag


def _triangle_phys_tags(mesh: ExportMesh, bc_tag: dict) -> np.ndarray:
    """One physical tag per surface triangle, picked from its BC group.
    Triangles that don't appear in any group get tag 0, which Gmsh treats as
    'no physical group' — we flag that as an error instead, since the
    preprocessor's "default" group should already absorb unassigned faces."""
    n = mesh.surface_tri.shape[0]
    tags = np.zeros(n, dtype=np.int64)
    for i, g in enumerate(mesh.bc_groups):
        tags[g.triangles] = bc_tag[i]
    missing = int((tags == 0).sum())
    if missing:
        raise ValueError(f"{missing} surface triangles are not in any BC group")
    return tags


def write_msh_v2(path: str, mesh: ExportMesh, quadratic: bool = False) -> None:
    """Write mesh as Gmsh MSH 2.2 ASCII. If quadratic, emit Tet10 + Tri6
    (type 11 / 9); otherwise Tet4 + Tri3 (type 4 / 2)."""
    if quadratic:
        nodes, tet10, edge_midnode = add_midside_nodes(mesh.nodes, mesh.tets)
        tets_out = tet10[:, TET10_TO_GMSH]
        tris_out = tri6_connectivity(mesh.surface_tri, edge_midnode)
        vol_type, surf_type = 11, 9
    else:
        nodes = mesh.nodes
        tets_out = mesh.tets
        tris_out = mesh.surface_tri
        vol_type, surf_type = 4, 2

    phys, bc_tag, vol_tag = _assign_physical_tags(mesh)
    tri_phys = _triangle_phys_tags(mesh, bc_tag)

    # Node and element ids are 1-based in MSH 2.2.
    with open(path, "w") as f:
        f.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")

        f.write("$PhysicalNames\n")
        f.write(f"{len(phys)}\n")
        for dim, tag, name in phys:
            f.write(f'{dim} {tag} "{name}"\n')
        f.write("$EndPhysicalNames\n")

        f.write("$Nodes\n")
        f.write(f"{nodes.shape[0]}\n")
        for i, p in enumerate(nodes, start=1):
            f.write(f"{i} {p[0]:.17g} {p[1]:.17g} {p[2]:.17g}\n")
        f.write("$EndNodes\n")

        f.write("$Elements\n")
        f.write(f"{tris_out.shape[0] + tets_out.shape[0]}\n")
        eid = 1
        # Surface triangles first (common convention; makes BC groups easy to
        # eyeball). Two tags per element: physical tag, elementary tag.
        for row, tag in zip(tris_out, tri_phys):
            node_str = " ".join(str(v + 1) for v in row)
            f.write(f"{eid} {surf_type} 2 {tag} {tag} {node_str}\n")
            eid += 1
        for row in tets_out:
            node_str = " ".join(str(v + 1) for v in row)
            f.write(f"{eid} {vol_type} 2 {vol_tag} {vol_tag} {node_str}\n")
            eid += 1
        f.write("$EndElements\n")
