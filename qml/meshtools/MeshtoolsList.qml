import QtQuick
import QtQuick.Controls
import QtQuick.Layouts


GridLayout {
    Layout.fillWidth: true
    Layout.preferredHeight: implicitHeight   // passt sich Inhalt an
    columns: 4
    columnSpacing: 8
    rowSpacing: 8

    property int tbSize: 40

    ToolButton { 
        Layout.preferredWidth: tbSize; 
        Layout.preferredHeight: tbSize; 
        text: "Center"
        ToolTip.visible: hovered
        ToolTip.text: "Ansicht zentrieren"
        ToolTip.delay: 500   // Millisekunden, bis der Tooltip erscheint
        onClicked: function() {
            SelectionCtrl.center_to_geometric_center()
        }
    }
}
