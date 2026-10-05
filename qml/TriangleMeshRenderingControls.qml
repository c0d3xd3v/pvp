import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    spacing: 2

    Switch {
        id: wireframeSwitch
        text: qsTr("show triangle outline")
        display: AbstractButton.TextOnly
        Layout.fillWidth: true
        onCheckedChanged: SceneCtrl.toogleWireframe(checked)
    }

    Switch {
        id: clipSwitch
        text: qsTr("clip plane")
        display: AbstractButton.TextOnly
        Layout.fillWidth: true
        onCheckedChanged: SceneCtrl.setClippingEnabled(checked)
    }

    GridLayout {
        columns: 3
        Layout.fillWidth: true
        visible: clipSwitch.checked

        property string currentAxis: "x"

        Repeater {
            model: [
                { label: "+x", axis: "x"  },
                { label: "−x", axis: "-x" },
                { label: "+y", axis: "y"  },
                { label: "−y", axis: "-y" },
                { label: "+z", axis: "z"  },
                { label: "−z", axis: "-z" }
            ]
            delegate: Button {
                required property var modelData
                text: modelData.label
                Layout.fillWidth: true
                highlighted: parent.currentAxis === modelData.axis
                onClicked: {
                    parent.currentAxis = modelData.axis
                    SceneCtrl.setClipAxis(modelData.axis)
                }
            }
        }
    }
}
