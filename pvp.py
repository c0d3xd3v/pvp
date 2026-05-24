import os
import sys

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QGuiApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtQml     import QQmlApplicationEngine

from MainCtrl          import MainCtrl
from qml.vtk.VTKItem   import VTKItem
from resources         import resources


if __name__ == "__main__":
    QHPT = Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(QHPT)

    app = QApplication()
    engine = QQmlApplicationEngine()
    mainctrl = MainCtrl()

    mainctrl.set_cmd_args(sys.argv)

    engine.addImportPath(':/qml/')
    engine.load('qrc:/qml/main.qml')

    toplevel = engine.rootObjects()[0]
    mainctrl.setupInternal(engine, toplevel.findChild(VTKItem, "vtkitem"))

    app.exec()
