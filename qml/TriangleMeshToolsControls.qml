import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

import "partitioning"

Item {
    id: meshToolsRoot
    Layout.fillWidth: true
    implicitHeight: toolsColumn.implicitHeight

    property var meshRoles: PreProcCtrl.getMeshRoles()

    Connections {
        target: PreProcCtrl
        function onSessionChanged() { meshRoles = PreProcCtrl.getMeshRoles() }
    }

    ColumnLayout {
        id: toolsColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top

        // Mesh roles panel (shared header, above tabs)
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
        }

        TabBar {
            id: tabBar
            Layout.fillWidth: true
            background: Item {}   // blend into the translucent sidebar
            TabButton { text: "Boundaries"; width: implicitWidth; leftPadding: 10; rightPadding: 10 }
            TabButton { text: "Meshing"; leftPadding: 10; rightPadding: 10 }
        }

        StackLayout {
            id: tabStack
            currentIndex: tabBar.currentIndex
            Layout.fillWidth: true
            // only the active tab counts; StackLayout would use the tallest one
            Layout.preferredHeight: children[currentIndex] ? children[currentIndex].implicitHeight : 0
            onCurrentIndexChanged: PreProcCtrl.setPickingEnabled(currentIndex === 0)
            Component.onCompleted: PreProcCtrl.setPickingEnabled(currentIndex === 0)

            // Tab 1: Surface partitioning (BCs)
            ColumnLayout {
                PartitionList {
                    Layout.fillWidth: true
                }
            }

            // Tab 2: BG mesh + Mesher
            ColumnLayout {
                id: meshingTab
                spacing: 8

                property string currentMesher: {
                    var m = MeshingCtrl.getMeshers();
                    return m.length > 0 ? m[0] : "";
                }
                property var schema: MeshingCtrl.getSchema(currentMesher)
                property var paramValues: ({})
                property bool meshing: false

                function resetParams() {
                    var pv = {};
                    for (var i = 0; i < schema.length; i++) pv[schema[i].name] = schema[i].default;
                    paramValues = pv;
                }
                onSchemaChanged: resetParams()
                Component.onCompleted: resetParams()

                Connections {
                    target: MeshingCtrl
                    function onMeshingStarted()         { meshingTab.meshing = true  }
                    function onMeshingFinished(success) { meshingTab.meshing = false }
                }

                Button {
                    text: "Create BG Mesh"
                    Layout.fillWidth: true
                    enabled: meshToolsRoot.meshRoles[0].loaded
                    onClicked: PreProcCtrl.createBackgroundMesh()
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(1, 1, 1, 0.12) }

                Label { text: "Mesher"; font.bold: true }
                ComboBox {
                    Layout.fillWidth: true
                    model: MeshingCtrl.getMeshers()
                    currentIndex: 0
                    onCurrentTextChanged: meshingTab.currentMesher = currentText
                }

                Repeater {
                    model: meshingTab.schema
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Label {
                            text: modelData.label
                            Layout.preferredWidth: 130
                            elide: Text.ElideRight
                            ToolTip.text: modelData.tooltip || ""
                            ToolTip.visible: modelData.tooltip && ma.hovered
                            HoverHandler { id: ma }
                        }
                        TextField {
                            Layout.fillWidth: true
                            text: Number(modelData.default).toString()
                            horizontalAlignment: TextInput.AlignRight
                            selectByMouse: true
                            validator: DoubleValidator {
                                bottom: modelData.min
                                top:    modelData.max
                                decimals: 6
                                notation: DoubleValidator.StandardNotation
                            }
                            onTextChanged: {
                                var v = parseFloat(text);
                                if (!isNaN(v)) meshingTab.paramValues[modelData.name] = v;
                            }
                        }
                    }
                }

                Button {
                    text: meshingTab.meshing ? "Cancel" : "Run"
                    Layout.fillWidth: true
                    enabled: meshingTab.meshing
                             || (meshToolsRoot.meshRoles[0].loaded
                                 && meshingTab.currentMesher !== "")
                    Material.background: meshingTab.meshing
                                         ? Material.color(Material.Red, Material.Shade700)
                                         : undefined
                    onClicked: {
                        if (meshingTab.meshing) MeshingCtrl.cancelMesher()
                        else MeshingCtrl.runMesher(meshingTab.currentMesher,
                                                   meshingTab.paramValues)
                    }
                }
            }
        }
    }
}
