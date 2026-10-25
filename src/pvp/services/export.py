"""Volume-mesh export: the project's tets + boundary partitions as an
ExportMesh, written in one of the formats of fileio/formats.py."""
import numpy as np

from pvp.fileio.export_model import BCGroup, ExportMesh
from pvp.fileio.formats import EXPORT_FORMATS
from pvp.model.partitions import Partitions
from pvp.model.project import Project

DEFAULT_GROUP = "default"   # unassigned triangles; read back as unassigned


def collect_bc_groups(partitions: Partitions, n_triangles: int) -> list[BCGroup]:
    """One group per non-empty partition. Every triangle must end up in some
    group, otherwise the exported surface has holes; unassigned triangles go
    into a "default" group."""
    ids = partitions.ids_per_cell()
    if ids is None:
        return [BCGroup(DEFAULT_GROUP, np.arange(n_triangles, dtype=np.int64))]
    if len(ids) != n_triangles:
        raise ValueError(f"surface has {len(ids)} triangles but the volume mesh "
                         f"boundary has {n_triangles}; they must be the same surface")
    groups = []
    assigned = np.zeros(n_triangles, dtype=bool)
    for p in partitions.all():
        faces = np.flatnonzero(ids == p.id)
        if faces.size:
            groups.append(BCGroup(p.name, faces.astype(np.int64)))
            assigned[faces] = True
    unassigned = np.flatnonzero(~assigned)
    if unassigned.size:
        groups.append(BCGroup(DEFAULT_GROUP, unassigned.astype(np.int64)))
    return groups


def build_export_mesh(project: Project) -> ExportMesh:
    vol = project.volume
    return ExportMesh(nodes=vol.vertices, tets=vol.tetrahedra, surface_tri=vol.triangles,
                      bc_groups=collect_bc_groups(project.partitions, len(vol.triangles)))


def export_summary(project: Project) -> dict:
    """Numbers shown in the export dialog."""
    if not project.can_export_volume():
        return {"boundaries": 0, "unassigned": 0, "tets": 0}
    try:
        groups = collect_bc_groups(project.partitions, len(project.volume.triangles))
    except ValueError:
        groups = []
    return {"boundaries": sum(g.name != DEFAULT_GROUP for g in groups),
            "unassigned": sum(len(g.triangles) for g in groups if g.name == DEFAULT_GROUP),
            "tets": len(project.volume.tetrahedra)}


def export_volume(project: Project, path: str, format_key: str, quadratic: bool = False) -> tuple[str, ExportMesh]:
    """Write the volume mesh; returns the path actually written (extension
    added if missing) and the exported mesh. Raises on errors."""
    fmt = EXPORT_FORMATS.get(format_key)
    if fmt is None:
        raise ValueError(f"Unknown export format: {format_key!r}")
    if not project.can_export_volume():
        raise ValueError("No volume mesh to export.")
    if not path.endswith(fmt.ext):
        path += fmt.ext
    mesh = build_export_mesh(project)
    if fmt.quadratic:
        fmt.writer(path, mesh, quadratic=bool(quadratic))
    else:
        fmt.writer(path, mesh)
    return path, mesh
