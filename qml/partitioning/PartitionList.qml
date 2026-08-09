import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: partitionsRoot

    property var partitions: PreProcCtrl.getPartitions()

    Connections {
        target: PreProcCtrl
        function onPartitionsChanged() { partitionsRoot.partitions = PreProcCtrl.getPartitions() }
        function onSessionChanged()    { partitionsRoot.partitions = PreProcCtrl.getPartitions() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        anchors.leftMargin: 5
        anchors.rightMargin: 5

        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: inputField
                placeholderText: "Neuer Randbedingungs-Name ..."
                Layout.fillWidth: true
                onAccepted: addPartition()
            }
            Button {
                text: "+"
                enabled: inputField.text.trim() !== ""
                onClicked: addPartition()
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: partitionsRoot.partitions
            clip: true
            spacing: 2

            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: 40
                color: modelData.selected ? "#cfe2ff"
                     : (index % 2 === 0 ? "#f8f8f8" : "#ffffff")
                border.color: modelData.selected ? "#0d6efd" : "#ddd"
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
                        border.color: "#666"
                        border.width: 1
                    }
                    Text {
                        text: modelData.name
                        font.pixelSize: 14
                        Layout.fillWidth: true
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    Button {
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
