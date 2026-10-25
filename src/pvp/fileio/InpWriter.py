"""CalculiX / Abaqus .inp writers.

Both target C3D4 (linear) / C3D10 (quadratic) tets with per-BC *NSET and
*SURFACE sidesets. CalculiX gets a flat deck; Abaqus wraps the mesh in
*PART / *INSTANCE / *ASSEMBLY, which its CAE workflow expects. Face
numbering follows the Abaqus manual (CalculiX inherits it).
"""
import numpy as np

from pvp.fileio.export_model import (
    ExportMesh, add_midside_nodes, tri6_connectivity,
)


# Abaqus/CalculiX C3D4 face numbering:
#   Face 1: nodes 1-2-3   (opposite local node 4 → 0-based idx 3)
#   Face 2: nodes 1-4-2   (opposite local node 3 → 0-based idx 2)
#   Face 3: nodes 2-4-3   (opposite local node 1 → 0-based idx 0)
#   Face 4: nodes 3-4-1   (opposite local node 2 → 0-based idx 1)
# C3D10 uses the same face numbers (midside nodes are implied by the element).
_OPPOSITE_LOCAL_TO_FACE = {0: 3, 1: 4, 2: 2, 3: 1}

# Abaqus limits data lines to 16 entries. 10 keeps lines comfortably short.
_NSET_WIDTH = 10


def _prepare_output(mesh: ExportMesh, quadratic: bool):
    """Return (nodes, tet_conn, bc_tri_conn, elem_type) for both writers.
    bc_tri_conn carries Tri6 nodes in quadratic mode so *NSETs pick up the
    midside nodes on the BC surface along with the corners."""
    if quadratic:
        nodes, tet_conn, edge_midnode = add_midside_nodes(mesh.nodes, mesh.tets)
        return nodes, tet_conn, tri6_connectivity(mesh.surface_tri, edge_midnode), "C3D10"
    return mesh.nodes, mesh.tets, mesh.surface_tri, "C3D4"


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


def _write_nodes(f, nodes: np.ndarray) -> None:
    f.write("*NODE\n")
    for i in range(nodes.shape[0]):
        x, y, z = nodes[i]
        f.write(f"{i + 1}, {x:.17g}, {y:.17g}, {z:.17g}\n")


def _write_elements(f, tet_conn: np.ndarray, elem_type: str, elset: str) -> None:
    f.write(f"*ELEMENT, TYPE={elem_type}, ELSET={elset}\n")
    for eid0 in range(tet_conn.shape[0]):
        node_str = ", ".join(str(int(v) + 1) for v in tet_conn[eid0])
        f.write(f"{eid0 + 1}, {node_str}\n")


def _write_nset(f, name: str, node_ids_1based: np.ndarray, instance: str | None = None) -> None:
    attrs = f"NSET={name}"
    if instance is not None:
        attrs += f", INSTANCE={instance}"
    f.write(f"*NSET, {attrs}\n")
    for i in range(0, len(node_ids_1based), _NSET_WIDTH):
        chunk = node_ids_1based[i : i + _NSET_WIDTH]
        f.write(", ".join(str(int(n)) for n in chunk) + "\n")


def _write_surface(f, name: str, entries: list, instance: str | None = None) -> None:
    """entries: iterable of (eid_1based, face_number). instance qualifies the
    element id (Abaqus assembly-level *SURFACE needs 'instance.eid')."""
    f.write(f"*SURFACE, NAME={name}, TYPE=ELEMENT\n")
    prefix = f"{instance}." if instance else ""
    for eid, face in entries:
        f.write(f"{prefix}{eid}, S{face}\n")


def _surface_entries(mesh: ExportMesh, group, face_lookup: dict):
    for tri_idx in group.triangles:
        key = frozenset(int(v) for v in mesh.surface_tri[tri_idx])
        yield face_lookup[key]


def write_inp_calculix(path: str, mesh: ExportMesh, quadratic: bool = False) -> None:
    """Write mesh as a flat CalculiX .inp deck. If quadratic, emit C3D10;
    otherwise C3D4. BC groups are each emitted as a *NSET (unique nodes on
    the group's surface) plus a *SURFACE referencing tet faces."""
    nodes, tet_conn, bc_tri_conn, elem_type = _prepare_output(mesh, quadratic)
    face_lookup = _tet_face_lookup(mesh.tets)

    with open(path, "w") as f:
        f.write("*HEADING\nExported by pvp\n")
        _write_nodes(f, nodes)
        _write_elements(f, tet_conn, elem_type, "Volume")

        for g in mesh.bc_groups:
            unique_nodes = np.unique(bc_tri_conn[g.triangles].ravel()) + 1
            _write_nset(f, g.name, unique_nodes)
            _write_surface(f, g.name, _surface_entries(mesh, g, face_lookup))


_PART_NAME = "pvp-part"
_INSTANCE_NAME = "pvp-part-1"
_ASSEMBLY_NAME = "pvp-assembly"


def write_inp_abaqus(path: str, mesh: ExportMesh, quadratic: bool = False) -> None:
    """Write mesh as an Abaqus .inp deck using *PART / *INSTANCE / *ASSEMBLY.
    Nodes and elements live inside the part; *NSET and *SURFACE live at
    assembly level with INSTANCE= references, which is what Abaqus/CAE's
    load and BC definitions expect."""
    nodes, tet_conn, bc_tri_conn, elem_type = _prepare_output(mesh, quadratic)
    face_lookup = _tet_face_lookup(mesh.tets)

    with open(path, "w") as f:
        f.write("*HEADING\nExported by pvp\n")

        f.write(f"*PART, NAME={_PART_NAME}\n")
        _write_nodes(f, nodes)
        _write_elements(f, tet_conn, elem_type, "Volume")
        f.write("*END PART\n")

        f.write(f"*ASSEMBLY, NAME={_ASSEMBLY_NAME}\n")
        f.write(f"*INSTANCE, NAME={_INSTANCE_NAME}, PART={_PART_NAME}\n")
        f.write("*END INSTANCE\n")

        for g in mesh.bc_groups:
            unique_nodes = np.unique(bc_tri_conn[g.triangles].ravel()) + 1
            _write_nset(f, g.name, unique_nodes, instance=_INSTANCE_NAME)
            _write_surface(f, g.name, _surface_entries(mesh, g, face_lookup),
                           instance=_INSTANCE_NAME)

        f.write("*END ASSEMBLY\n")
