import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Item {
    id: partitionsRoot

    implicitHeight: partitionsColumn.implicitHeight + 10   // + top/bottom margins

    property var partitions: PreProcCtrl.getPartitions()

    Connections {
        target: PreProcCtrl
        function onPartitionsChanged() { partitionsRoot.partitions = PreProcCtrl.getPartitions() }
        function onSessionChanged()    { partitionsRoot.partitions = PreProcCtrl.getPartitions() }
    }

    ColumnLayout {
        id: partitionsColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        anchors.leftMargin: 5
        anchors.rightMargin: 5

        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: inputField
                placeholderText: "New boundary name…"
                Layout.fillWidth: true
                onAccepted: addPartition()
            }
            ToolButton {
                text: "+"
                font.pixelSize: 18
                enabled: inputField.text.trim() !== ""
                onClicked: addPartition()
            }
        }

        ListView {
            Layout.fillWidth: true
            // grows with its entries up to ~6 rows, then scrolls internally
            Layout.preferredHeight: Math.min(contentHeight, 250)
            model: partitionsRoot.partitions
            clip: true
            spacing: 2

            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: 40
                color: modelData.selected
                       ? Qt.rgba(Material.accent.r, Material.accent.g, Material.accent.b, 0.18)
                       : (index % 2 === 0 ? Qt.rgba(1, 1, 1, 0.03) : "transparent")
                border.color: modelData.selected ? Material.accent : Qt.rgba(1, 1, 1, 0.10)
                border.width: modelData.selected ? 2 : 1

                // Declared BEFORE the RowLayout so it sits underneath — the delete
                // Button gets its own clicks; clicks on empty row area fall through here.
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (modelData.selected) {
                            PreProcCtrl.selectPartition(-1)
                        } else {
                            PreProcCtrl.selectPartition(modelData.id)
                        }
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 8

                    Rectangle {
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                        radius: 3
                        color: modelData.color
                        border.color: Qt.rgba(1, 1, 1, 0.25)
                        border.width: 1
                    }
                    Label {
                        text: modelData.name
                        Layout.fillWidth: true
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    ToolButton {
                        text: "×"
                        implicitWidth: 32
                        onClicked: PreProcCtrl.deletePartition(modelData.id)
                    }
                }
            }
            ScrollBar.vertical: ScrollBar { }
        }
    }

    function addPartition() {
        let name = inputField.text.trim()
        if (name === "") return
        PreProcCtrl.createPartition(name)
        inputField.clear()
    }
}
