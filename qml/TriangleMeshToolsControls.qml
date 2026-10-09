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
                property string stageLabel: ""
                property real stageFraction: NaN
                property double startedAt: 0
                property int elapsedSec: 0

                function resetParams() {
                    var pv = {};
                    for (var i = 0; i < schema.length; i++) pv[schema[i].name] = schema[i].default;
                    paramValues = pv;
                }
                onSchemaChanged: resetParams()
                Component.onCompleted: resetParams()

                function formatElapsed(sec) {
                    var m = Math.floor(sec / 60);
                    var s = sec % 60;
                    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                }

                Connections {
                    target: MeshingCtrl
                    function onMeshingStarted() {
                        meshingTab.meshing = true
                        meshingTab.stageLabel = "Starting…"
                        meshingTab.stageFraction = NaN
                        meshingTab.startedAt = Date.now()
                        meshingTab.elapsedSec = 0
                    }
                    function onMeshingFinished(success) {
                        meshingTab.meshing = false
                        meshingTab.stageLabel = success ? "Done" : "Cancelled / failed"
                        meshingTab.stageFraction = success ? 1.0 : NaN
                    }
                    function onProgressChanged(stage, fraction) {
                        meshingTab.stageLabel = stage
                        meshingTab.stageFraction = fraction
                    }
                }

                Timer {
                    interval: 500; repeat: true; running: meshingTab.meshing
                    onTriggered: meshingTab.elapsedSec =
                        Math.floor((Date.now() - meshingTab.startedAt) / 1000)
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

                // Status row — appears whenever we have something to show
                RowLayout {
                    Layout.fillWidth: true
                    visible: meshingTab.meshing || meshingTab.stageLabel !== ""
                    spacing: 6
                    BusyIndicator {
                        running: meshingTab.meshing
                        visible: meshingTab.meshing
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                    }
                    Label {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: meshingTab.stageLabel
                    }
                    Label {
                        visible: meshingTab.meshing
                        opacity: 0.7
                        text: "⧗ " + meshingTab.formatElapsed(meshingTab.elapsedSec)
                    }
                }
                ProgressBar {
                    Layout.fillWidth: true
                    visible: meshingTab.meshing || meshingTab.stageFraction === 1.0
                    from: 0; to: 1
                    indeterminate: isNaN(meshingTab.stageFraction)
                    value: isNaN(meshingTab.stageFraction) ? 0 : meshingTab.stageFraction
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
