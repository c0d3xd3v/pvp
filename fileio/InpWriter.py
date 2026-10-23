"""CalculiX / Abaqus .inp writer.

Emits a stand-alone deck with a single volume element set and, per BC, an
*NSET of the surface nodes and an *SURFACE referencing tet faces. Element
types: C3D4 (linear) or C3D10 (quadratic); face numbering follows the
CalculiX manual, which Abaqus inherits.
"""
import numpy as np

from fileio.export_model import (
    ExportMesh, add_midside_nodes, tri6_connectivity,
)


# CalculiX C3D4 face numbering (manual, section "Four-node tetrahedral element"):
#   Face 1: nodes 1-2-3   (opposite local node 4 → 0-based idx 3)
#   Face 2: nodes 1-4-2   (opposite local node 3 → 0-based idx 2)
#   Face 3: nodes 2-4-3   (opposite local node 1 → 0-based idx 0)
#   Face 4: nodes 3-4-1   (opposite local node 2 → 0-based idx 1)
# C3D10 uses the same face numbers (midside nodes are implied by the element).
_OPPOSITE_LOCAL_TO_FACE = {0: 3, 1: 4, 2: 2, 3: 1}

# Abaqus limits data lines to 16 entries. 10 keeps lines comfortably short.
_NSET_WIDTH = 10


def _tet_face_lookup(tets: np.ndarray) -> dict:
    """{frozenset(3 corner vertex ids) → (eid 1-based, face number)}.

    Every boundary triangle is a face of exactly one tet; interior faces are
    shared by two tets and overwrite each other here, which is fine because
    they never appear as surface triangles."""
    out = {}
    for eid0 in range(tets.shape[0]):
        t = tets[eid0]
        for k in range(4):
            face = frozenset(int(t[j]) for j in range(4) if j != k)
            out[face] = (eid0 + 1, _OPPOSITE_LOCAL_TO_FACE[k])
    return out


def _write_nset(f, name: str, node_ids_1based: np.ndarray) -> None:
    f.write(f"*NSET, NSET={name}\n")
    for i in range(0, len(node_ids_1based), _NSET_WIDTH):
        chunk = node_ids_1based[i : i + _NSET_WIDTH]
        f.write(", ".join(str(int(n)) for n in chunk) + "\n")


def write_inp_calculix(path: str, mesh: ExportMesh, quadratic: bool = False) -> None:
    """Write mesh as a CalculiX .inp deck. If quadratic, emit C3D10; otherwise
    C3D4. BC groups are each emitted as a *NSET (unique nodes on the group's
    surface) plus a *SURFACE referencing tet faces."""
    if quadratic:
        nodes, tet_conn, edge_midnode = add_midside_nodes(mesh.nodes, mesh.tets)
        elem_type = "C3D10"
        bc_tri_conn = tri6_connectivity(mesh.surface_tri, edge_midnode)
    else:
        nodes = mesh.nodes
        tet_conn = mesh.tets
        elem_type = "C3D4"
        bc_tri_conn = mesh.surface_tri

    face_lookup = _tet_face_lookup(mesh.tets)

    with open(path, "w") as f:
        f.write("*HEADING\nExported by pvp\n")

        f.write("*NODE\n")
        for i in range(nodes.shape[0]):
            x, y, z = nodes[i]
            f.write(f"{i + 1}, {x:.17g}, {y:.17g}, {z:.17g}\n")

        f.write(f"*ELEMENT, TYPE={elem_type}, ELSET=Volume\n")
        for eid0 in range(tet_conn.shape[0]):
            row = tet_conn[eid0]
            node_str = ", ".join(str(int(v) + 1) for v in row)
            f.write(f"{eid0 + 1}, {node_str}\n")

        for g in mesh.bc_groups:
            unique_nodes = np.unique(bc_tri_conn[g.triangles].ravel()) + 1
            _write_nset(f, g.name, unique_nodes)

            f.write(f"*SURFACE, NAME={g.name}, TYPE=ELEMENT\n")
            for tri_idx in g.triangles:
                tri = mesh.surface_tri[tri_idx]
                key = frozenset(int(v) for v in tri)
                eid, face = face_lookup[key]
                f.write(f"{eid}, S{face}\n")
