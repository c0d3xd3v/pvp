"""Gmsh .msh v2.2 writer: round-trip via meshio for linear and quadratic
output. meshio parses the physical names + element tags into cell_data, which
lets us verify BC-group fidelity without pulling in gmsh itself."""
import numpy as np
import meshio
import pytest

from fileio.MshWriter import write_msh_v2
from fileio.export_model import ExportMesh, BCGroup


def _split_cube_faces(P, F):
    """Partition the unit-cube boundary into the 6 face BCs by coordinate."""
    groups = []
    for name, pred in [
        ("xmin", np.all(np.isclose(P[F][:, :, 0], 0.0), axis=1)),
        ("xmax", np.all(np.isclose(P[F][:, :, 0], 1.0), axis=1)),
        ("ymin", np.all(np.isclose(P[F][:, :, 1], 0.0), axis=1)),
        ("ymax", np.all(np.isclose(P[F][:, :, 1], 1.0), axis=1)),
        ("zmin", np.all(np.isclose(P[F][:, :, 2], 0.0), axis=1)),
        ("zmax", np.all(np.isclose(P[F][:, :, 2], 1.0), axis=1)),
    ]:
        groups.append(BCGroup(name, np.where(pred)[0]))
    return groups


@pytest.fixture
def cube_mesh(unit_cube):
    P, T, F = unit_cube
    return ExportMesh(nodes=P, tets=T, surface_tri=F,
                      bc_groups=_split_cube_faces(P, F))


def _read_cells(path):
    m = meshio.read(path)
    # meshio returns one CellBlock per element type; group by name
    return m, {cb.type: cb for cb in m.cells}


def test_linear_roundtrip(tmp_path, cube_mesh):
    path = tmp_path / "cube.msh"
    write_msh_v2(str(path), cube_mesh, quadratic=False)

    m, cells = _read_cells(str(path))
    assert m.points.shape == (cube_mesh.nodes.shape[0], 3)
    assert np.allclose(m.points, cube_mesh.nodes)

    assert set(cells) == {"triangle", "tetra"}
    assert cells["tetra"].data.shape == cube_mesh.tets.shape
    assert cells["triangle"].data.shape == cube_mesh.surface_tri.shape

    # Physical names: 6 BCs + Volume
    names = {k: v for k, v in m.field_data.items()}
    assert set(names) == {"xmin", "xmax", "ymin", "ymax", "zmin", "zmax", "Volume"}
    # BC tags are dim=2
    for n in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
        assert names[n][1] == 2
    assert names["Volume"][1] == 3


def test_linear_bc_tags_match_groups(tmp_path, cube_mesh):
    """Each triangle must carry the tag of its BC group — i.e. a BC's triangle
    count in the file matches the group's triangle count."""
    path = tmp_path / "cube.msh"
    write_msh_v2(str(path), cube_mesh, quadratic=False)
    m = meshio.read(str(path))

    tri_block = next(cb for cb in m.cells if cb.type == "triangle")
    tri_phys = m.cell_data_dict["gmsh:physical"]["triangle"]
    name_to_tag = {name: tag for name, (tag, _dim) in m.field_data.items()}

    for g in cube_mesh.bc_groups:
        tag = name_to_tag[g.name]
        count = int((tri_phys == tag).sum())
        assert count == len(g.triangles), (
            f"BC '{g.name}': file has {count} triangles, group has {len(g.triangles)}"
        )


def test_quadratic_roundtrip(tmp_path, cube_mesh):
    path = tmp_path / "cube.msh"
    write_msh_v2(str(path), cube_mesh, quadratic=True)
    m, cells = _read_cells(str(path))

    assert "tetra10" in cells, f"cell types: {list(cells)}"
    assert "triangle6" in cells

    # Each tet gained 6 midside columns; each triangle gained 3.
    assert cells["tetra10"].data.shape == (cube_mesh.tets.shape[0], 10)
    assert cells["triangle6"].data.shape == (cube_mesh.surface_tri.shape[0], 6)

    # Midside node count = unique undirected tet edges
    T = cube_mesh.tets
    pairs = np.sort(np.vstack([
        T[:, [0, 1]], T[:, [1, 2]], T[:, [0, 2]],
        T[:, [0, 3]], T[:, [1, 3]], T[:, [2, 3]],
    ]), axis=1)
    assert m.points.shape[0] == cube_mesh.nodes.shape[0] + len(np.unique(pairs, axis=0))


def test_quadratic_midside_lies_on_edge(tmp_path, cube_mesh):
    """After round-trip through meshio, each Tet10 midside node (as recorded
    in the file) must still lie at the midpoint of the right local edge.
    meshio converts Gmsh's node order to its canonical order on read, which
    happens to coincide with ours — so cols 4..9 can be compared directly."""
    path = tmp_path / "cube.msh"
    write_msh_v2(str(path), cube_mesh, quadratic=True)
    m, cells = _read_cells(str(path))

    pts = m.points
    tet10 = cells["tetra10"].data
    for i, (a, b) in enumerate([(0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3)]):
        mids = pts[tet10[:, 4 + i]]
        expected = 0.5 * (pts[tet10[:, a]] + pts[tet10[:, b]])
        assert np.allclose(mids, expected), f"midside col {4 + i} off edge {(a, b)}"
