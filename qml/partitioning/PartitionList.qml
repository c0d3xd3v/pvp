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

        // Pick-angle threshold: BFS from the clicked face stops at edges
        // where the dihedral angle exceeds this value (degrees). Label floats
        // above the control, like a focused Material TextField's placeholder.
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Label {
                text: "pick angle (°)"
                font.pixelSize: 10
                opacity: 0.65
                Layout.leftMargin: 4
                Layout.alignment: Qt.AlignLeft
                ToolTip.text: "Max angle between neighbouring triangle normals "
                              + "when flood-filling a selection (degrees)."
                ToolTip.visible: angleHover.hovered
                ToolTip.delay: 400
                HoverHandler { id: angleHover }
            }
            SpinBox {
                id: angleSpin
                from: 0
                to: 180
                stepSize: 1
                editable: true
                value: Math.round(SelectionCtrl.getNormalCompareAngle())
                Layout.fillWidth: true
                onValueModified: SelectionCtrl.set_normal_compare_angle(value)
            }
        }

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
                id: delegateRoot
                required property var modelData
                required property int index
                width: ListView.view.width
                // Grow with contents so the ToolButton (implicit ~48 with Material)
                // doesn't force the row's RowLayout taller than the Rectangle and
                // push the label/swatch off-center.
                height: Math.max(40, rowLayout.implicitHeight + 8)
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
                    id: rowLayout
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 8

                    Rectangle {
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                        Layout.alignment: Qt.AlignVCenter
                        radius: 3
                        color: modelData.color
                        border.color: Qt.rgba(1, 1, 1, 0.25)
                        border.width: 1
                    }
                    Label {
                        text: modelData.name
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    ToolButton {
                        text: "×"
                        implicitWidth: 32
                        Layout.alignment: Qt.AlignVCenter
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
