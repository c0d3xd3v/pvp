import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QmlVtk 1.0

ApplicationWindow {
    id: appWindow
    width: 600
    height: 600
    visible: true
    // Compact Material controls: Material defaults are touch-sized; this makes
    // them more desktop-friendly. All child controls inherit the font.
    font.pixelSize: 12

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

            onReleased: function(mouse) {
                mouse.accepted = true;
                this.parent.onMouseReleased(
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

    // DropArea at top level — reacts to drops anywhere in the window
    DropArea {
        id: globalDropArea
        anchors.fill: parent
        keys: ["text/uri-list"]

        // Visual feedback while dragging over
        Rectangle {
            anchors.fill: parent
            color: "#4400ff00"  // semi-transparent green
            border.color: "green"
            border.width: 3
            opacity: parent.containsDrag ? 0.5 : 0  // only visible while dragging
            Behavior on opacity { NumberAnimation { duration: 100 } }
        }

        // Called when files are dropped
        onDropped: function(drop) {
            console.log("Files dropped:", drop.urls[0]);

            // Hand over to the Python backend
            if (typeof MainCtrl !== "undefined") {
                settingsPane.openFile(drop.urls[0])
            } else {
                console.warn("MainCtrl not available");
            }

            drop.acceptProposedAction();
        }

        // Keeps the VTKItem from swallowing the events
        onEntered: function(drag) {
            console.log("Files dragged over the window");
            drag.acceptProposedAction();
        }
    }

    SidePage {
        id: settingsPane
        height: 36
        width: 36
    }

    // Called last, once the window is complete
    Component.onCompleted: {
        // Notify the controller here
        if (typeof MainCtrl !== "undefined") {
            //MainCtrl.notify_qml_ready();
        } else {
            console.warn("MainCtrl not available yet");
        }
    }

}
