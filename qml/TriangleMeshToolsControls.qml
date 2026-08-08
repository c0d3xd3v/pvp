import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "partitioning"
import "meshtools"

Item {
    id: meshToolsRoot
    Layout.fillWidth: true
    Layout.fillHeight: true

    property var meshRoles: PreProcCtrl.getMeshRoles()

    Connections {
        target: PreProcCtrl
        function onSessionChanged() { meshRoles = PreProcCtrl.getMeshRoles() }
    }

    ColumnLayout {
        anchors.fill: parent

        // Mesh roles panel
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Repeater {
                model: meshToolsRoot.meshRoles
                delegate: RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "[" + modelData.role[0].toUpperCase() + "]"
                        opacity: modelData.loaded ? 1.0 : 0.3
                        font.bold: modelData.loaded
                    }
                    Label {
                        text: modelData.loaded ? modelData.name : "—"
                        opacity: modelData.loaded ? 0.8 : 0.3
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Button {
                    text: "BG Mesh"
                    Layout.fillWidth: true
                    enabled: PreProcCtrl.getMeshRoles()[0].loaded
                    onClicked: PreProcCtrl.createBackgroundMesh()
                }
            }
        }

        MeshtoolsList {
            Layout.fillWidth: true
        }
        PartitionList {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
