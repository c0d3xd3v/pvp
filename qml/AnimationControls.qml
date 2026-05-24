import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: animationControls

    ColumnLayout {
        id: columnLayout
        anchors.fill: parent
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        
        Button {
            Layout.fillWidth: true
            text: "start"
        }

        Item {
            id: item1
            width: 200
            height: 200
            Layout.fillHeight: true
            Layout.fillWidth: true
        }
    }
}
