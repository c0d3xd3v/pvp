"""Operations that replace or extend the project: opening files, taking over
a mesher result, the .pvp project file. They only change the Project; the
controllers show the result."""
from pathlib import Path

import numpy as np

from pvp.fileio import project_h5
from pvp.fileio.readers import read_surface, read_volume
from pvp.model.mesh import Mesh
from pvp.model.project import Project
from pvp.services.boundary_transfer import BoundarySnapshot, apply_snapshot
from pvp.services.export import DEFAULT_GROUP


def open_surface(project: Project, path: str, scale: float = 1.0):
    """STL/OBJ as a new project; `scale` converts the file's unit to mm."""
    project.start(Path(path).name, read_surface(path, scale), source_path=path)


def open_volume(project: Project, path: str):
    """A .vol/.msh carries surface + volume (+ boundary names): a new project
    with one shared mesh, and partitions from the named boundaries."""
    mesh = read_volume(path)
    project.start(Path(path).name, mesh, volume=mesh, source_path=path)
    for bc, name in mesh.bc_names.items():
        name = (name or "").strip()
        faces = np.flatnonzero(mesh.triangle_bcs == bc)
        # "default" is what export writes for unassigned triangles: reading it
        # back as unassigned keeps the round trip idempotent.
        if not name or name.lower() == DEFAULT_GROUP or faces.size == 0:
            continue
        pid = project.partitions.add(name, record=False)
        project.partitions.assign_faces(faces, pid, record=False)


def take_mesh_result(project: Project, vertices, triangles, tetrahedra,
                     name: str, boundaries: BoundarySnapshot | None = None):
    """A mesher result replaces the geometry: the surface is the tet
    boundary, the volume the tet set. The input file and mesher parameters
    stay. With `boundaries`, the partitions from before meshing are
    transferred onto the new surface."""
    mesh = Mesh(vertices=vertices, triangles=triangles, tetrahedra=tetrahedra)
    project.start(name, mesh, volume=mesh)
    if boundaries is not None:
        apply_snapshot(project, boundaries)


def add_bounding_box(project: Project):
    from pvp.geometry.bounding_box import bounding_box_mesh
    project.background = bounding_box_mesh(project.surface.vertices)


def save_project_file(project: Project, path: str) -> str:
    """Write the project to a .pvp file; returns the path written."""
    if not path.endswith(project_h5.EXTENSION):
        path += project_h5.EXTENSION
    surf, parts = project.surface, project.partitions
    ids = parts.ids_per_cell()
    state = project_h5.ProjectState(
        surface_vertices=surf.vertices,
        surface_triangles=surf.triangles,
        partition_ids=ids if ids is not None else np.zeros(len(surf.triangles), dtype=np.int32),
        partitions=parts.all(),
        next_partition_id=parts.next_id(),
        current_partition=parts.current_id(),
        normal_angle=project.normal_angle,
        source_name=project.source_name,
        source_bytes=project.source_bytes,
        mesher_name=project.mesher_name,
        mesher_params=dict(project.mesher_params),
    )
    if project.volume is not None and project.volume.has_tetrahedra:
        state.volume_vertices = project.volume.vertices
        state.volume_triangles = project.volume.triangles
        state.volume_tetrahedra = project.volume.tetrahedra
    project_h5.save_project(path, state)
    return path


def open_project_file(project: Project, path: str):
    """Replace the project with a .pvp file. Raises if it can't be read
    (the project is unchanged then)."""
    state = project_h5.load_project(path)
    surface = Mesh(vertices=state.surface_vertices, triangles=state.surface_triangles)
    volume = None
    if state.has_volume:
        volume = Mesh(vertices=state.volume_vertices, triangles=state.volume_triangles,
                      tetrahedra=state.volume_tetrahedra)
        if (np.array_equal(state.volume_vertices, state.surface_vertices)
                and np.array_equal(state.volume_triangles, state.surface_triangles)):
            surface = volume    # as after meshing / loading a .vol: one shared mesh
    project.start(Path(path).stem, surface, volume=volume)
    project.source_name, project.source_bytes = state.source_name, state.source_bytes
    project.mesher_name, project.mesher_params = state.mesher_name, dict(state.mesher_params)
    project.normal_angle = state.normal_angle
    project.partitions.restore(state.partitions, state.partition_ids,
                               state.next_partition_id, state.current_partition)
