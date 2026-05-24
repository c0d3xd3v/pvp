import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QmlVtk 1.0

Window {
    id: appWindow
    width: 600
    height: 600
    visible: true

    VTKItem {
        id: vtkitem
        objectName: "vtkitem"
        anchors.fill: parent

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            propagateComposedEvents: true

            onClicked: function() {
                settingsPane.close()
            }

            onPressed: function(mouse) {
                settingsPane.close()
                mouse.accepted = true;
                this.parent.onMousePressed(
                    mouse.x, mouse.y, mouse.button,
                    mouse.buttons, mouse.modifiers);
            }

            onPositionChanged: function(mouse) {
                this.parent.onMouseMove(mouse.x, mouse.y, mouse.button,
                                        mouse.buttons, mouse.modifiers);
            }

            onWheel: function(wheel) {
                this.parent.onMouseWheel(wheel.angleDelta, wheel.buttons,
                                 wheel.inverted, wheel.modifiers,
                                 wheel.pixelDelta, wheel.x, wheel.y);
            }
        }

    }

    // 🔧 DropArea AUF ERSTER EBENE - reagiert auf gesamtes Fenster
    DropArea {
        id: globalDropArea
        anchors.fill: parent
        keys: ["text/uri-list"]

        // Sichtbares Feedback beim Drüberziehen
        Rectangle {
            anchors.fill: parent
            color: "#4400ff00"  // Halbtransparentes Grün
            border.color: "green"
            border.width: 3
            opacity: parent.containsDrag ? 0.5 : 0  // Nur beim Drüberziehen sichtbar
            Behavior on opacity { NumberAnimation { duration: 100 } }
        }

        // Wird aufgerufen, wenn Dateien abgelegt werden
        onDropped: function(drop) {
            console.log("🟢 Dateien wurden abgelegt:", drop.urls[0]);

            // An Python/Backend weiterreichen
            if (typeof MainCtrl !== "undefined") {
                //MainCtrl.handleDroppedFiles(drop.urls);
                MainCtrl.loadMesh(drop.urls[0])
            } else {
                console.warn("❌ MainCtrl nicht verfügbar");
            }

            drop.acceptProposedAction();
        }

        // Verhindert, dass das VTKItem die Events "frisst"
        onEntered: function(drag) {
            console.log("Dateien werden über das Fenster gezogen");
            drag.acceptProposedAction();
        }
    }

    SidePage {
        id: settingsPane
        height: 36
        width: 36
    }

    // ✅ DIESE FUNKTION WIRD ALS LETZTES AUFGERUFEN
    Component.onCompleted: {
        // Hier den Controller benachrichtigen
        if (typeof MainCtrl !== "undefined") {
            //MainCtrl.notify_qml_ready();
        } else {
            console.warn("MainCtrl ist noch nicht verfügbar");
        }
    }

}
