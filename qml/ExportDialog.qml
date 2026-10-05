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
        width: Math.min(360, Overlay.overlay ? Overlay.overlay.width - 40 : 360)

        // More formats/settings go here later; each entry: label, file filter, suffix
        property var formats: [
            { label: "Netgen volume mesh (.vol)", filter: "Netgen volume mesh (*.vol)", suffix: "vol" }
        ]

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
        nameFilters: [exportDialog.formats[formatBox.currentIndex].filter]
        defaultSuffix: exportDialog.formats[formatBox.currentIndex].suffix
        onAccepted: {
            var err = PreProcCtrl.exportVolume(saveDialog.selectedFile.toString())
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
