import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: toolbarLayout
    height: 32
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.topMargin: 0
    anchors.leftMargin: 0
    anchors.rightMargin: 0

    RoundButton {
        opacity: 0.402
        text: ""
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
        opacity: 0.402
        text: ""
        //icon.source: "qrc:/icons/settings.svg"
        icon.name: "folder"
        display: AbstractButton.IconOnly
        onClicked: function() {
            fileDialog.open()
        }
    }

    Item {
        Layout.fillHeight: true
        Layout.fillWidth: true
    }

    RoundButton {
        id: roundButton
        opacity: 0.413
        padding: 6
        checked: false
        checkable: true
        highlighted: false
        flat: false
        display: AbstractButton.IconOnly
        icon.source: "qrc:/icons/keep_off.svg"
        onToggled: if(checked) {
                        isFixed = true
                    } else if(!checked) {
                        isFixed = false
                    }
    }
}