"""Operations that replace or extend the project: opening files, taking over
a mesher result, the .pvp project file. They only change the Project; the
controllers show the result."""
from pathlib import Path

import numpy as np

from pvp.fileio import project_h5
from pvp.fileio.readers import read_surface, read_volume
from pvp.model.mesh import Mesh
from pvp.model.project import Project
from pvp.services import multibody
from pvp.services.boundary_transfer import closest_cells
from pvp.services.export import DEFAULT_GROUP


def open_surface(project: Project, path: str, scale: float = 1.0):
    """STL/OBJ as a new project; `scale` converts the file's unit to mm."""
    project.start(Path(path).name, read_surface(path, scale), source_path=path)


def open_volume(project: Project, path: str):
    """A .vol/.msh carries surface + volume (+ boundary names): its boundary
    is the input surface (same triangle order), partitions come from the
    named boundaries."""
    mesh = read_volume(path)
    project.start(Path(path).name, mesh.surface_only(), source_path=path)
    project.set_volume(mesh, np.arange(len(mesh.triangles)))
    for bc, name in mesh.bc_names.items():
        name = (name or "").strip()
        faces = np.flatnonzero(mesh.triangle_bcs == bc)
        # "default" is what export writes for unassigned triangles: reading it
        # back as unassigned keeps the round trip idempotent.
        if not name or name.lower() == DEFAULT_GROUP or faces.size == 0:
            continue
        pid = project.partitions.add(name, record=False)
        project.partitions.assign_faces(faces, pid, record=False)


def take_mesh_result(project: Project, vertices, triangles, tetrahedra, face_map=None,
                     regions=None):
    """A mesher result becomes the volume; the input surface and its
    partitions stay. face_map (surface triangle per boundary triangle) is
    computed when not given — the mesher worker does it off the GUI thread.
    regions: body per tet (None: a single region)."""
    mesh = Mesh(vertices=vertices, triangles=triangles, tetrahedra=tetrahedra)
    if face_map is None:
        face_map = mesh_face_map(project, mesh, regions)
    project.set_volume(mesh, face_map, regions)


def mesh_face_map(project: Project, volume: Mesh, regions=None) -> np.ndarray:
    """Closest surface triangle (of the meshed components) per volume
    boundary triangle; with regions only among the triangles of the body
    the boundary triangle belongs to."""
    faces = project.meshed_faces()
    surf = project.surface
    if regions is None:
        return faces[closest_cells(surf.vertices, surf.triangles[faces],
                                   volume.vertices, volume.triangles)]
    bodies = multibody.body_faces(project.surface_components, project.meshed_components)
    tri_label = multibody.boundary_regions(volume.tetrahedra, regions, volume.triangles)
    return multibody.face_map_per_body(surf.vertices, surf.triangles, bodies,
                                       volume.vertices, volume.triangles, tri_label)


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
        surface_components=project.surface_components,
        meshed_components=project.meshed_components,
        partitions=parts.all(),
        next_partition_id=parts.next_id(),
        current_partition=parts.current_id(),
        normal_angle=project.normal_angle,
        source_name=project.source_name,
        source_bytes=project.source_bytes,
        mesher_name=project.mesher_name,
        mesher_params=dict(project.mesher_params),
        mesh_mode=project.mesh_mode,
    )
    if project.volume is not None and project.volume.has_tetrahedra:
        state.volume_vertices = project.volume.vertices
        state.volume_triangles = project.volume.triangles
        state.volume_tetrahedra = project.volume.tetrahedra
        state.volume_surface_faces = project.volume_face_map
        state.volume_regions = project.volume_regions
    project_h5.save_project(path, state)
    return path


def open_project_file(project: Project, path: str):
    """Replace the project with a .pvp file. Raises if it can't be read
    (the project is unchanged then)."""
    state = project_h5.load_project(path)
    surface = Mesh(vertices=state.surface_vertices, triangles=state.surface_triangles)
    volume, face_map = None, state.volume_surface_faces
    if state.has_volume:
        volume = Mesh(vertices=state.volume_vertices, triangles=state.volume_triangles,
                      tetrahedra=state.volume_tetrahedra)
        if face_map is None and np.array_equal(state.volume_triangles, state.surface_triangles):
            # older files: the surface was the volume boundary itself
            surface = volume.surface_only()
            face_map = np.arange(len(volume.triangles))
    project.start(Path(path).stem, surface)
    if state.surface_components is not None and state.meshed_components is not None:
        project.set_components(state.surface_components, state.meshed_components)
    if volume is not None:
        regions = state.volume_regions
        if regions is not None and len(regions) != len(volume.tetrahedra):
            regions = None      # inconsistent file: fall back to a single region
        project.set_volume(volume, face_map if face_map is not None
                           else mesh_face_map(project, volume, regions), regions)
    project.source_name, project.source_bytes = state.source_name, state.source_bytes
    project.mesher_name, project.mesher_params = state.mesher_name, dict(state.mesher_params)
    project.mesh_mode = state.mesh_mode
    project.normal_angle = state.normal_angle
    project.partitions.restore(state.partitions, state.partition_ids,
                               state.next_partition_id, state.current_partition)
