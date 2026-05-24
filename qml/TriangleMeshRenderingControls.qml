import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        Switch {
            id: wireframeSwitch
            opacity: 0.789
            text: qsTr("show triangle outline")
            display: AbstractButton.TextOnly
            Layout.fillWidth: true
            Layout.columnSpan: 1
            onCheckedChanged: function() {
                SceneCtrl.toogleWireframe(checked)
            }
        }
    }
}
