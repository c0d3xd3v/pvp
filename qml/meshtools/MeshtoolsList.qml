import QtQuick
import QtQuick.Controls
import QtQuick.Layouts


GridLayout {
    Layout.fillWidth: true
    Layout.preferredHeight: implicitHeight   // fits its content
    columns: 4
    columnSpacing: 8
    rowSpacing: 8

    property int tbSize: 40

    ToolButton { 
        Layout.minimumWidth: tbSize;
        Layout.preferredHeight: tbSize; 
        text: "Center"
        ToolTip.visible: hovered
        ToolTip.text: "Center view"
        ToolTip.delay: 500   // ms until the tooltip appears
        onClicked: function() {
            SelectionCtrl.center_to_geometric_center()
        }
    }
}
