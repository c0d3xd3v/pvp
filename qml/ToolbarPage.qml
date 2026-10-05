import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: toolbarLayout
    height: 32
    spacing: 0
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.topMargin: 0
    anchors.leftMargin: 0
    anchors.rightMargin: 0

    property int btnSize: 32

    RoundButton {
        Layout.preferredWidth: btnSize
        Layout.preferredHeight: btnSize
        padding: 6
        flat: true
        icon.source: "qrc:/icons/settings.svg"
        display: AbstractButton.IconOnly
        onClicked: function() {
            height_range.to = appWindow.height - 20
            width_range.to = sidebarWidth
            widthAnim.start()
            heightAnim.start()
        }
    }

    RoundButton {
        Layout.preferredWidth: btnSize
        Layout.preferredHeight: btnSize
        padding: 6
        flat: true
        icon.name: "folder"
        display: AbstractButton.IconOnly
        onClicked: function() {
            fileDialog.open()
        }
    }

    RoundButton {
        id: exportButton
        objectName: "exportButton"
        Layout.preferredWidth: btnSize
        Layout.preferredHeight: btnSize
        padding: 6
        flat: true
        icon.source: "qrc:/icons/export.svg"
        display: AbstractButton.IconOnly
        enabled: PreProcCtrl.canExportVolume()
        ToolTip.visible: hovered
        ToolTip.text: "Export"
        ToolTip.delay: 500
        onClicked: exportDialog.open()

        Connections {
            target: PreProcCtrl
            function onSessionChanged() { exportButton.enabled = PreProcCtrl.canExportVolume() }
        }
    }

    Item {
        Layout.fillHeight: true
        Layout.fillWidth: true
    }

    RoundButton {
        id: roundButton
        Layout.preferredWidth: btnSize
        Layout.preferredHeight: btnSize
        padding: 6
        flat: true
        checkable: true
        display: AbstractButton.IconOnly
        icon.source: checked ? "qrc:/icons/keep.svg" : "qrc:/icons/keep_off.svg"
        onToggled: isFixed = checked
    }
}
