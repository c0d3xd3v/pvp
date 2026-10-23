"""Gmsh .msh writers.

MSH 2.2 ASCII is the broadest-compatibility target (every CalculiX/ccx,
Elmer, OpenFOAM, meshio build understands it); MSH 4.1 adds explicit
entities (one surface per BC, one volume), which some newer tools prefer.
Each BC becomes a dim=2 Physical Name; all tets land in a dim=3 Physical
"Volume".
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


def _prepare_output(mesh: ExportMesh, quadratic: bool):
    """Return (nodes, tris_out, tets_out, surf_type, vol_type), shared between
    v2 and v4 writers. Gmsh element types: 2/4 linear, 9/11 quadratic."""
    if quadratic:
        nodes, tet10, edge_midnode = add_midside_nodes(mesh.nodes, mesh.tets)
        tets_out = tet10[:, TET10_TO_GMSH]
        tris_out = tri6_connectivity(mesh.surface_tri, edge_midnode)
        return nodes, tris_out, tets_out, 9, 11
    return mesh.nodes, mesh.surface_tri, mesh.tets, 2, 4


def write_msh_v2(path: str, mesh: ExportMesh, quadratic: bool = False) -> None:
    """Write mesh as Gmsh MSH 2.2 ASCII. If quadratic, emit Tet10 + Tri6
    (type 11 / 9); otherwise Tet4 + Tri3 (type 4 / 2)."""
    nodes, tris_out, tets_out, surf_type, vol_type = _prepare_output(mesh, quadratic)
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


def write_msh_v4(path: str, mesh: ExportMesh, quadratic: bool = False) -> None:
    """Write mesh as Gmsh MSH 4.1 ASCII. One surface entity per BC (carrying
    its Physical Name), one volume entity. Nodes are grouped under the volume
    entity (meshio and gmsh both accept this; the spec only asks that every
    node belongs to *some* entity)."""
    nodes, tris_out, tets_out, surf_type, vol_type = _prepare_output(mesh, quadratic)
    phys, bc_tag, vol_tag = _assign_physical_tags(mesh)

    # Element ids are 1-based and share one namespace across entities.
    bb_min = nodes.min(axis=0)
    bb_max = nodes.max(axis=0)
    bbox = f"{bb_min[0]:.17g} {bb_min[1]:.17g} {bb_min[2]:.17g} " \
           f"{bb_max[0]:.17g} {bb_max[1]:.17g} {bb_max[2]:.17g}"

    n_surfaces = len(mesh.bc_groups)
    volume_entity_tag = 1
    n_nodes = nodes.shape[0]
    n_tris = tris_out.shape[0]
    n_tets = tets_out.shape[0]

    with open(path, "w") as f:
        f.write("$MeshFormat\n4.1 0 8\n$EndMeshFormat\n")

        f.write("$PhysicalNames\n")
        f.write(f"{len(phys)}\n")
        for dim, tag, name in phys:
            f.write(f'{dim} {tag} "{name}"\n')
        f.write("$EndPhysicalNames\n")

        f.write("$Entities\n")
        f.write(f"0 0 {n_surfaces} 1\n")
        # Surface entity per BC: tag, bbox, numPhys phys, numBoundingCurves(=0)
        for i, _ in enumerate(mesh.bc_groups):
            surf_tag = i + 1
            f.write(f"{surf_tag} {bbox} 1 {bc_tag[i]} 0\n")
        # One volume entity carrying all tets
        f.write(f"{volume_entity_tag} {bbox} 1 {vol_tag} 0\n")
        f.write("$EndEntities\n")

        # All nodes in one block tied to the volume entity.
        f.write("$Nodes\n")
        f.write(f"1 {n_nodes} 1 {n_nodes}\n")
        f.write(f"3 {volume_entity_tag} 0 {n_nodes}\n")
        for i in range(n_nodes):
            f.write(f"{i + 1}\n")
        for p in nodes:
            f.write(f"{p[0]:.17g} {p[1]:.17g} {p[2]:.17g}\n")
        f.write("$EndNodes\n")

        # Elements: one block per BC (surfaces) + one block for the volume.
        total_elems = n_tris + n_tets
        n_blocks = n_surfaces + (1 if n_tets else 0)
        f.write("$Elements\n")
        f.write(f"{n_blocks} {total_elems} 1 {total_elems}\n")
        eid = 1
        for i, g in enumerate(mesh.bc_groups):
            surf_tag = i + 1
            k = len(g.triangles)
            f.write(f"2 {surf_tag} {surf_type} {k}\n")
            for row in tris_out[g.triangles]:
                node_str = " ".join(str(v + 1) for v in row)
                f.write(f"{eid} {node_str}\n")
                eid += 1
        if n_tets:
            f.write(f"3 {volume_entity_tag} {vol_type} {n_tets}\n")
            for row in tets_out:
                node_str = " ".join(str(v + 1) for v in row)
                f.write(f"{eid} {node_str}\n")
                eid += 1
        f.write("$EndElements\n")
