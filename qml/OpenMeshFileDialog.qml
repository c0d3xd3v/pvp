import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    property string __pendingPath: ""

    function open() {
        nativeDialog.open()
    }

    function openWithPath(url) {
        var path = url.toString()
        if (path.endsWith(".vtk")) {
            root.__pendingPath = url
            resultTypeDialog.open()
        } else {
            MainCtrl.loadMesh(url)
        }
    }

    FileDialog {
        id: nativeDialog
        title: "Select File"

        onAccepted: {
            var path = nativeDialog.selectedFile.toString()
            if (path.endsWith(".vtk")) {
                root.__pendingPath = nativeDialog.selectedFile
                resultTypeDialog.open()
            } else {
                MainCtrl.loadMesh(nativeDialog.selectedFile)
            }
        }
        onRejected: {}
    }

    Dialog {
        id: resultTypeDialog
        title: "Result Type"
        modal: true
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Ok | Dialog.Cancel

        ColumnLayout {
            RadioButton {
                id: modalRadio
                text: "Modal"
                checked: true
            }
            RadioButton {
                id: transientRadio
                text: "Transient"
            }
        }

        onAccepted: {
            if (modalRadio.checked) {
                MainCtrl.loadMesh(root.__pendingPath)
            } else {
                notImplementedDialog.open()
            }
        }
    }

    Dialog {
        id: notImplementedDialog
        title: "Not implemented"
        modal: true
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Ok

        Label {
            text: "Transient results are not yet implemented."
        }
    }
}
