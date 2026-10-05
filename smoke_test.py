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
    "partitioning/PartitionList.qml",
]


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

    m = unit_cube.GenerateMesh(maxh=0.5)
    P = np.array([[p[0], p[1], p[2]] for p in m.Points()])
    F = np.array([[int(v.nr) - 1 for v in e.vertices] for e in m.Elements2D()])
    r = FTetWildMesher().mesh(P, F, {"ideal_edge_length_rel": 0.3, "eps_rel": 0.001})
    print(f"  fTetWild ok: {len(r.tetrahedra)} tets")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "cube.vol")
        write_vol(path, r.vertices, r.tetrahedra, r.triangles,
                  [("wall", list(range(len(r.triangles))))])
        vol = ngsolve.Integrate(1, ngsolve.Mesh(path))
    if abs(vol - 1.0) > 1e-2:
        raise RuntimeError(f"exported volume {vol}, expected 1")
    print(f"  .vol export ok: volume {vol:.4f}")


def run() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])   # noqa: F841  needed for QML engine
    try:
        import vtk
        print(f"  vtk ok: {vtk.vtkVersion.GetVTKVersion()}")
        _check_qml()
        _check_meshing_and_export()
    except Exception:
        traceback.print_exc()
        print("SMOKE TEST FAILED")
        return 1
    print("SMOKE TEST OK")
    return 0
