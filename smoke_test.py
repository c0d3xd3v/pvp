"""`pvp --smoke-test`: checks without a window that a (packaged) build is
complete — Qt/QML incl. Material style, VTK, Netgen/NGSolve, libigl and the
fTetWild module — by compiling all QML files, meshing a small cube and
round-tripping it through the .vol export. Exit code 0 = OK.
"""
import os
import sys
import tempfile
import traceback


QML_FILES = [
    "main.qml", "SidePage.qml", "ToolbarPage.qml", "ExportDialog.qml",
    "OpenMeshFileDialog.qml", "SolutionControl.qml",
    "TriangleMeshRenderingControls.qml", "TriangleMeshToolsControls.qml",
    "MeshingStatusPanel.qml",
    "partitioning/PartitionList.qml",
]


def _check_vtk():
    # The app imports only a subset of VTK (visualization/vtk/vtklib.py). Some
    # of it is needed solely for object-factory overrides, which would only fail
    # later at render time — check that those resolve to the real implementations.
    from visualization.vtk import vtklib as vtk
    impl = {
        "vtkPolyDataMapper": vtk.vtkPolyDataMapper().GetClassName(),
        "vtkRenderer": vtk.vtkRenderer().GetClassName(),
        "vtkTextRenderer": vtk.vtkTextRenderer.GetInstance().GetClassName(),
        "interactor style": vtk.vtkRenderWindowInteractor().GetInteractorStyle().GetClassName(),
    }
    expected = {
        "vtkPolyDataMapper": "vtkOpenGLPolyDataMapper",
        "vtkRenderer": "vtkOpenGLRenderer",
        "vtkTextRenderer": "vtkMathTextFreeTypeTextRenderer",
        "interactor style": "vtkInteractorStyleSwitch",
    }
    if impl != expected:
        raise RuntimeError(f"VTK factory overrides missing: got {impl}, expected {expected}")
    print(f"  vtk ok: {vtk.vtkVersion.GetVTKVersion()}, factories {sorted(set(impl.values()))}")


def _check_qml():
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    import visualization.qtquick.VTKItem  # noqa: F401  registers QmlVtk
    from resources import resources       # noqa: F401  qrc:/ data

    engine = QQmlEngine()
    engine.addImportPath(':/qml/')
    for name in QML_FILES:
        comp = QQmlComponent(engine, QUrl(f"qrc:/qml/{name}"))
        if comp.isError():
            raise RuntimeError(f"{name}: " + "; ".join(e.toString() for e in comp.errors()))
        print(f"  qml ok: {name}")


def _check_meshing_and_export():
    import numpy as np
    import ngsolve
    from netgen.csg import unit_cube
    from meshing.FTetWildMesher import FTetWildMesher
    from fileio.NetgenVolWriter import write_vol
    from fileio.export_model import ExportMesh, BCGroup

    m = unit_cube.GenerateMesh(maxh=0.5)
    P = np.array([[p[0], p[1], p[2]] for p in m.Points()])
    F = np.array([[int(v.nr) - 1 for v in e.vertices] for e in m.Elements2D()])
    # Unit cube bbox diagonal = sqrt(3) ≈ 1.732; pick coarse abs params for speed.
    r = FTetWildMesher().mesh(P, F, {"ideal_edge_length": 0.52, "eps": 0.0017})
    print(f"  fTetWild ok: {len(r.tetrahedra)} tets")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "cube.vol")
        write_vol(path, ExportMesh(
            nodes=r.vertices, tets=r.tetrahedra, surface_tri=r.triangles,
            bc_groups=[BCGroup("wall", np.arange(len(r.triangles)))]))
        vol = ngsolve.Integrate(1, ngsolve.Mesh(path))
    if abs(vol - 1.0) > 1e-2:
        raise RuntimeError(f"exported volume {vol}, expected 1")
    print(f"  .vol export ok: volume {vol:.4f}")


def run() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])   # noqa: F841  needed for QML engine
    try:
        _check_vtk()
        _check_qml()
        _check_meshing_and_export()
    except Exception:
        traceback.print_exc()
        print("SMOKE TEST FAILED")
        return 1
    print("SMOKE TEST OK")
    return 0
