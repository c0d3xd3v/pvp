"""Readers for the input formats (see formats.py). Each returns a Mesh or
ResultMesh; the heavy libraries are imported on use to keep startup fast."""
import contextlib
import locale

import numpy as np

from pvp.fileio.formats import file_kind
from pvp.model.mesh import Mesh, ResultMesh


@contextlib.contextmanager
def _c_numeric_locale():
    """igl/meshio parse ASCII numbers with the C library: a German locale
    would read "1.5" as 1."""
    old = locale.getlocale(locale.LC_NUMERIC)
    locale.setlocale(locale.LC_NUMERIC, "C")
    try:
        yield
    finally:
        locale.setlocale(locale.LC_NUMERIC, old)


def read_surface(path: str, scale: float = 1.0) -> Mesh:
    """STL/OBJ. These carry no units: the user picks one when opening and
    `scale` converts to mm, so everything downstream sees mm."""
    import igl      # ~0.3 s
    with _c_numeric_locale():
        sv, sf = igl.read_triangle_mesh(path)
        V, _, _, F = igl.remove_duplicate_vertices(sv, sf, epsilon=1e-7)
    return Mesh(vertices=V * float(scale), triangles=F)


def _read_vol(path: str) -> Mesh:
    import ngsolve as ngs
    ngs_mesh = ngs.Mesh(path)
    ngmesh = ngs_mesh.ngmesh
    # Element lists are read via Python: converting them with np.array()
    # depends on the netgen version. PointId.nr is 1-based.
    V = [[p[0], p[1], p[2]] for p in ngmesh.Points()]
    F = [[v.nr - 1 for v in el.vertices] for el in ngmesh.Elements2D()]
    T = [[v.nr - 1 for v in el.vertices] for el in ngmesh.Elements3D()]

    # The BC number is FaceDescriptor.bc, not el.index: that is the face
    # descriptor's index, and netgen may insert default descriptors.
    fd_to_bc: dict[int, int] = {}
    bcs = []
    for el in ngmesh.Elements2D():
        fd = int(el.index)
        if fd not in fd_to_bc:
            try:
                fd_to_bc[fd] = int(ngmesh.GetFaceDescriptor(fd).bc)
            except Exception:
                fd_to_bc[fd] = fd
        bcs.append(fd_to_bc[fd])

    try:
        names = {i + 1: name for i, name in enumerate(ngs_mesh.GetBoundaries())}
    except Exception:
        names = {}
    return Mesh(vertices=V, triangles=F, tetrahedra=T, triangle_bcs=bcs, bc_names=names)


def _read_msh(path: str) -> Mesh:
    import meshio
    with _c_numeric_locale():
        m = meshio.read(path)
    F = m.cells_dict["triangle"]
    return Mesh(vertices=m.points, triangles=F, tetrahedra=m.cells_dict["tetra"],
                triangle_bcs=np.ones(len(F), dtype=np.int32))


def read_volume(path: str) -> Mesh:
    """.vol (Netgen, with boundary names) or .msh (Gmsh)."""
    return _read_vol(path) if path.lower().endswith(".vol") else _read_msh(path)


def read_result(path: str) -> ResultMesh:
    """Surface with point fields (.vtk)."""
    import meshio
    with _c_numeric_locale():
        m = meshio.read(path)
    blocks = [c.data for c in m.cells if c.type == "triangle"]
    if not blocks:
        raise ValueError(f"{path}: no triangle cells")
    fields = {name: np.asarray(d) for name, d in m.point_data.items()}
    return ResultMesh(vertices=m.points, triangles=np.vstack(blocks), fields=fields)


def read_mesh(path: str, scale: float = 1.0) -> Mesh | ResultMesh:
    kind = file_kind(path)
    if kind == "surface":
        return read_surface(path, scale)
    if kind == "volume":
        return read_volume(path)
    if kind == "result":
        return read_result(path)
    raise ValueError(f"unsupported file: {path}")
