"""CalculiX .inp writer: node/element round-trip via meshio + geometric check
on *SURFACE face numbers (parsed from the raw text, since meshio skips
*SURFACE blocks)."""
import re

import numpy as np
import meshio
import pytest

from pvp.fileio.InpWriter import (
    write_inp_calculix, write_inp_abaqus, _OPPOSITE_LOCAL_TO_FACE,
    _INSTANCE_NAME,
)
from pvp.fileio.export_model import ExportMesh, BCGroup


def _two_bc_groups(P, F):
    on_x0 = np.where(np.all(np.isclose(P[F][:, :, 0], 0.0), axis=1))[0]
    rest = np.setdiff1d(np.arange(len(F)), on_x0)
    return [BCGroup("inlet", on_x0), BCGroup("wall", rest)]


@pytest.fixture
def cube_mesh(unit_cube):
    P, T, F = unit_cube
    return ExportMesh(nodes=P, tets=T, surface_tri=F,
                      bc_groups=_two_bc_groups(P, F))


def _read_text(path):
    with open(path) as f:
        return f.read()


def _parse_surface(text, name):
    """Return [(eid, face_number), ...] for *SURFACE, NAME=name."""
    m = re.search(
        rf"\*SURFACE,\s*NAME={re.escape(name)},[^\n]*\n(.*?)(?=\n\*|\Z)",
        text, flags=re.DOTALL,
    )
    assert m, f"*SURFACE {name!r} not found"
    out = []
    for line in m.group(1).strip().splitlines():
        eid_s, face_s = line.split(",")
        out.append((int(eid_s), int(face_s.strip().lstrip("S"))))
    return out


def test_linear_meshio_roundtrip(tmp_path, cube_mesh):
    path = tmp_path / "cube.inp"
    write_inp_calculix(str(path), cube_mesh, quadratic=False)

    m = meshio.read(str(path))
    assert m.points.shape == cube_mesh.nodes.shape
    assert np.allclose(m.points, cube_mesh.nodes)
    (tetra,) = [cb for cb in m.cells if cb.type == "tetra"]
    assert tetra.data.shape == cube_mesh.tets.shape
    assert np.array_equal(tetra.data, cube_mesh.tets)


def test_quadratic_meshio_roundtrip(tmp_path, cube_mesh):
    path = tmp_path / "cube.inp"
    write_inp_calculix(str(path), cube_mesh, quadratic=True)

    m = meshio.read(str(path))
    (tetra10,) = [cb for cb in m.cells if cb.type == "tetra10"]
    assert tetra10.data.shape == (cube_mesh.tets.shape[0], 10)
    assert np.array_equal(tetra10.data[:, :4], cube_mesh.tets)

    # Midside geometry: col 4..9 of our tet10 are edges
    #   (0,1), (1,2), (0,2), (0,3), (1,3), (2,3)  — Abaqus-style canonical.
    pts = m.points
    for i, (a, b) in enumerate([(0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3)]):
        mids = pts[tetra10.data[:, 4 + i]]
        expected = 0.5 * (pts[tetra10.data[:, a]] + pts[tetra10.data[:, b]])
        assert np.allclose(mids, expected), f"midside col {4 + i} off edge {(a, b)}"


def test_surface_face_numbers_point_at_right_face(tmp_path, cube_mesh):
    """For every *SURFACE entry (eid, S<face>), the three corner nodes of the
    face must match the surface triangle in the BC group. This verifies the
    face-numbering table geometrically, which is the pitfall the roadmap
    warned about."""
    path = tmp_path / "cube.inp"
    write_inp_calculix(str(path), cube_mesh, quadratic=False)
    text = _read_text(str(path))

    face_to_opposite = {v: k for k, v in _OPPOSITE_LOCAL_TO_FACE.items()}

    for g in cube_mesh.bc_groups:
        pairs = _parse_surface(text, g.name)
        assert len(pairs) == len(g.triangles)
        for (eid, face), tri_idx in zip(pairs, g.triangles):
            tet = cube_mesh.tets[eid - 1]
            opp = face_to_opposite[face]
            face_vertices = frozenset(int(tet[j]) for j in range(4) if j != opp)
            assert face_vertices == frozenset(int(v) for v in cube_mesh.surface_tri[tri_idx])


def test_nset_names_present(tmp_path, cube_mesh):
    path = tmp_path / "cube.inp"
    write_inp_calculix(str(path), cube_mesh, quadratic=False)
    text = _read_text(str(path))
    for g in cube_mesh.bc_groups:
        assert f"*NSET, NSET={g.name}" in text


@pytest.mark.parametrize("quadratic", [False, True])
def test_abaqus_meshio_roundtrip(tmp_path, cube_mesh, quadratic):
    path = tmp_path / "cube.inp"
    write_inp_abaqus(str(path), cube_mesh, quadratic=quadratic)

    m = meshio.read(str(path))
    tet_type = "tetra10" if quadratic else "tetra"
    (tetra,) = [cb for cb in m.cells if cb.type == tet_type]
    assert tetra.data.shape[0] == cube_mesh.tets.shape[0]
    assert np.array_equal(tetra.data[:, :4], cube_mesh.tets)


def test_abaqus_structure_and_surface_qualified(tmp_path, cube_mesh):
    """The part/assembly wrapping and INSTANCE= references on *NSET /
    *SURFACE are what makes this an Abaqus deck rather than a CalculiX one."""
    path = tmp_path / "cube.inp"
    write_inp_abaqus(str(path), cube_mesh, quadratic=False)
    text = _read_text(str(path))

    assert "*PART, NAME=" in text
    assert "*END PART" in text
    assert "*ASSEMBLY, NAME=" in text
    assert "*INSTANCE, NAME=" in text
    assert "*END ASSEMBLY" in text

    for g in cube_mesh.bc_groups:
        assert f"*NSET, NSET={g.name}, INSTANCE={_INSTANCE_NAME}" in text
        # Surface entries must be qualified with the instance name, otherwise
        # Abaqus can't resolve element ids inside the assembly.
        m = re.search(
            rf"\*SURFACE,\s*NAME={re.escape(g.name)},[^\n]*\n(.*?)(?=\n\*|\Z)",
            text, flags=re.DOTALL,
        )
        for line in m.group(1).strip().splitlines():
            assert line.startswith(f"{_INSTANCE_NAME}."), line
