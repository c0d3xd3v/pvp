import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    property string __pendingPath: ""

    // STL / OBJ carry no unit metadata, so we ask before scaling to mm.
    readonly property var __unitChoices: [
        { label: "Millimeters (mm)", scale: 1.0 },
        { label: "Centimeters (cm)", scale: 10.0 },
        { label: "Meters (m)",       scale: 1000.0 },
        { label: "Inches (in)",      scale: 25.4 },
    ]


    function open() {
        nativeDialog.open()
    }

    function openWithPath(url) {
        var kind = MainCtrl.fileKind(url.toString())
        if (kind === "result") {
            root.__pendingPath = url
            resultTypeDialog.open()
        } else if (kind === "surface") {
            root.__pendingPath = url
            unitsDialog.open()
        } else {
            MainCtrl.loadMesh(url)
        }
    }

    FileDialog {
        id: nativeDialog
        title: "Select File"

        onAccepted: {
            var kind = MainCtrl.fileKind(nativeDialog.selectedFile.toString())
            if (kind === "result") {
                root.__pendingPath = nativeDialog.selectedFile
                resultTypeDialog.open()
            } else if (kind === "surface") {
                root.__pendingPath = nativeDialog.selectedFile
                unitsDialog.open()
            } else {
                MainCtrl.loadMesh(nativeDialog.selectedFile)
            }
        }
        onRejected: {}
    }

    Dialog {
        id: unitsDialog
        title: "File units"
        modal: true
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Ok | Dialog.Cancel

        ColumnLayout {
            Label {
                text: "STL and OBJ files have no units — pick the source and we scale to millimeters."
                wrapMode: Text.WordWrap
                Layout.preferredWidth: 320
                opacity: 0.8
            }
            Repeater {
                model: root.__unitChoices
                delegate: RadioButton {
                    required property int index
                    required property var modelData
                    text: modelData.label
                    checked: index === 0
                    ButtonGroup.group: unitsGroup
                    property real scale: modelData.scale
                }
            }
            ButtonGroup { id: unitsGroup }
        }

        onAccepted: {
            var scale = 1.0
            if (unitsGroup.checkedButton)
                scale = unitsGroup.checkedButton.scale
            MainCtrl.loadMesh(root.__pendingPath, scale)
        }
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
