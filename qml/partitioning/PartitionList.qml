import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ListModel {
        id: listModel
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        
        // Eingabezeile
        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: inputField
                placeholderText: "Neuen Eintrag ..."
                Layout.fillWidth: true
                onAccepted: addItem()
            }
            Button {
                text: "+"
                onClicked: addItem()
            }
        }

        // Scrollbare Liste
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true   // nimmt den gesamten verbleibenden Platz
            model: listModel
            clip: true
            spacing: 2

            delegate: Rectangle {
                width: ListView.view.width
                height: 50
                color: index % 2 === 0 ? "#f8f8f8" : "#ffffff"
                border.color: "#ddd"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    Text {
                        text: model.itemText
                        font.pixelSize: 16
                        Layout.fillWidth: true
                        verticalAlignment: Text.AlignVCenter
                    }
                    Button {
                        text: "delete"
                        onClicked: listModel.remove(index)
                    }
                }
            }
            ScrollBar.vertical: ScrollBar { }
        }
    }

    function addItem() {
        let newText = inputField.text.trim()
        if (newText !== "") {
            listModel.append({ "itemText": newText })
            inputField.clear()
        }
    }
}