import os
import sys

# Packaged builds ignore PYTHONUNBUFFERED; flush log lines as they come.
sys.stdout.reconfigure(line_buffering=True)

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Material Dark theme for all QtQuick.Controls widgets
os.environ["QT_QUICK_CONTROLS_MATERIAL_THEME"]   = "Dark"
os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"]  = "Teal"
os.environ["QT_QUICK_CONTROLS_MATERIAL_PRIMARY"] = "BlueGrey"
# Dense = desktop-sized controls (default Material sizing is touch-oriented)
os.environ["QT_QUICK_CONTROLS_MATERIAL_VARIANT"] = "Dense"

from PySide6.QtCore            import Qt
from PySide6.QtGui             import QGuiApplication
from PySide6.QtWidgets         import QApplication
from PySide6.QtQml             import QQmlApplicationEngine
from PySide6.QtQuickControls2  import QQuickStyle


def _compile_resources():
    """Regenerate resources/resources.py with pyside6-rcc when it is missing or
    older than the .qrc or any file it lists (QML, icons, ...). The generated
    file is not tracked in git."""
    import re
    import subprocess
    from pathlib import Path

    res_dir = Path(__file__).resolve().parent / "resources"
    qrc, out = res_dir / "resources.qrc", res_dir / "resources.py"
    sources = [qrc] + [res_dir / f for f in re.findall(r"<file[^>]*>([^<]+)</file>", qrc.read_text())]
    newest = max(s.stat().st_mtime for s in sources if s.exists())
    if not out.exists() or out.stat().st_mtime < newest:
        print("Compiling Qt resources ...")
        subprocess.check_call(["pyside6-rcc", str(qrc), "-o", str(out)])


# In a packaged build (PyInstaller) resources.py is bundled and pyside6-rcc absent.
if not getattr(sys, "frozen", False):
    _compile_resources()

if "--smoke-test" in sys.argv:
    from PySide6.QtQuickControls2 import QQuickStyle as _style
    import smoke_test
    _style.setStyle("Material")
    sys.exit(smoke_test.run())

# VTK loads its OpenGL functions via GLX; with Qt's native Wayland backend the
# packaged app hangs in VTK's context init. Use X11 (XWayland on Wayland
# desktops) unless the user picked a platform explicitly.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from controllers.MainCtrl         import MainCtrl
from visualization.qtquick.VTKItem import VTKItem
from resources                     import resources


if __name__ == "__main__":
    QHPT = Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(QHPT)

    app = QApplication()
    QQuickStyle.setStyle("Material")
    engine = QQmlApplicationEngine()
    mainctrl = MainCtrl()
    mainctrl.set_cmd_args(sys.argv)

    engine.addImportPath(':/qml/')
    mainctrl.setupContext(engine)
    engine.load('qrc:/qml/main.qml')

    toplevel = engine.rootObjects()[0]
    mainctrl.setupInternal(toplevel.findChild(VTKItem, "vtkitem"))

    app.exec()
