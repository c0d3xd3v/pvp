import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    property var summary: ({ boundaries: 0, unassigned: 0, tets: 0 })

    function open() {
        summary = PreProcCtrl.getExportSummary()
        exportDialog.open()
    }

    Dialog {
        id: exportDialog
        title: "Export"
        modal: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(400, Overlay.overlay ? Overlay.overlay.width - 40 : 400)

        property var formats: PreProcCtrl.getExportFormats()
        property int formatIndex: 0
        readonly property var currentFormat: formats[formatIndex]

        footer: DialogButtonBox {
            Button {
                text: "Export"
                highlighted: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }
            Button {
                text: "Cancel"
                flat: true
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        ColumnLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 8

            Label { text: "Format" }
            ComboBox {
                id: formatBox
                Layout.fillWidth: true
                model: exportDialog.formats
                textRole: "label"
                currentIndex: exportDialog.formatIndex
                onCurrentIndexChanged: exportDialog.formatIndex = currentIndex
            }

            CheckBox {
                id: quadraticBox
                text: "Quadratic elements (Tet10)"
                enabled: exportDialog.currentFormat ? exportDialog.currentFormat.quadratic : false
                checked: false
                ToolTip.text: enabled
                              ? "Emit second-order tetrahedra with straight midside nodes."
                              : "Not supported by the selected format."
                ToolTip.visible: hovered
            }

            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.7
                text: root.summary.tets + " tetrahedra, "
                      + root.summary.boundaries + " boundary condition(s)"
                      + (root.summary.unassigned > 0
                         ? "; " + root.summary.unassigned + " unassigned faces are exported as 'default'."
                         : ".")
            }
        }

        onAccepted: saveDialog.open()
    }

    FileDialog {
        id: saveDialog
        title: "Export"
        fileMode: FileDialog.SaveFile
        nameFilters: {
            if (!exportDialog.currentFormat) return ["All files (*)"]
            var ext = exportDialog.currentFormat.ext.replace(".", "")
            return [exportDialog.currentFormat.label + " (*" + exportDialog.currentFormat.ext + ")"]
        }
        defaultSuffix: exportDialog.currentFormat
                       ? exportDialog.currentFormat.ext.replace(".", "")
                       : ""
        onAccepted: {
            var fmt = exportDialog.currentFormat
            var quadratic = quadraticBox.enabled && quadraticBox.checked
            var err = PreProcCtrl.exportVolume(saveDialog.selectedFile.toString(),
                                               fmt.key, quadratic)
            if (err !== "") {
                errorLabel.text = err
                errorDialog.open()
            }
        }
    }

    Dialog {
        id: errorDialog
        title: "Export failed"
        modal: true
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Ok
        Label { id: errorLabel; wrapMode: Text.WordWrap }
    }
}
