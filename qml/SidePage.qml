import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    property bool isFixed: false
    property var renderControlsComp: null
    property var solutionControlsComp: null
    property var meshToolsControlsComp: null
    property var sidebarWidth: 220

    id: sidePanel
    x:10
    y:10
    width: sidebarWidth
    height: 400
    visible: true
    clip: true

    OpenMeshFileDialog {id: fileDialog}
    ExportDialog {id: exportDialog}

    function openFile(url) {
        fileDialog.openWithPath(url)
    }

    function close() {
        if(!isFixed)
        {
            sidePanel.anchors.top = undefined
            sidePanel.anchors.bottom  = undefined
            height_range.to = toolbarLayout.height
            width_range.to = height_range.to //*2.2
            widthAnim.start()
            heightAnim.start()
        }
    }

    function addCompCrl(comp, layout)
    {
        if (comp.status === Component.Ready) {
            var controlsComp = comp.createObject(layout, {
                "Layout.fillWidth": true,
                "visible": true
            });

            if (!controlsComp) {
                console.log("Error creating renderControlsComp");
            }
            return controlsComp;
        } else {
            console.log("Error loading component:", comp.errorString());
        }
        return null;
    }

    // Connect to the Python signal
    function handleLoadedData(dataType) {
        var hasPointData = dataType === "results";
        //console.log("Received signal in QML: meshLoaded")
        //console.log(hasPointData)

        contentScroll.contentItem.contentY = 0

        if (meshToolsControlsComp) meshToolsControlsComp.destroy();
        if (solutionControlsComp) solutionControlsComp.destroy();
        if (renderControlsComp) renderControlsComp.destroy();

        renderControlsComp = Qt.createComponent("TriangleMeshRenderingControls.qml");
        renderControlsComp = addCompCrl(renderControlsComp, renderingControlLayout);
        
        if(hasPointData) {
            solutionControlsComp = Qt.createComponent("SolutionControl.qml");
            solutionControlsComp = addCompCrl(solutionControlsComp, renderingControlLayout);
        } else {
            meshToolsControlsComp = Qt.createComponent("TriangleMeshToolsControls.qml");
            meshToolsControlsComp = addCompCrl(meshToolsControlsComp, renderingControlLayout);
        }
    }
    
    Connections {
        id: meshLoadedConnection
        target: MainCtrl
        onMeshLoaded: function(dataType){ handleLoadedData(dataType) }
    }

    SequentialAnimation on width {
        id: widthAnim
        running: false
        PropertyAnimation {id: width_range; to: 50 }
    }
    SequentialAnimation on height {
        id: heightAnim
        running: false
        PropertyAnimation {id: height_range; to: 50 }
        onFinished: function() {

            if(sidePanel.height != toolbarLayout.height)
            {
                sidePanel.anchors.top = sidePanel.parent.top
                sidePanel.anchors.left  = sidePanel.parent.left
                sidePanel.anchors.bottom  = sidePanel.parent.bottom
                sidePanel.anchors.bottomMargin = 10
                sidePanel.anchors.topMargin = 10
                sidePanel.anchors.leftMargin = 10
                sidePanel.anchors.rightMargin = 10
            }
        }
    }

    Component.onCompleted: function() {
        // close the sidebar on start up.
        console.log("sidebar completed ... ")
        meshLoadedConnection.target = MainCtrl
        close()
    }

    Rectangle {
        // Translucent Material Dark surface so the 3D view shows through slightly
        color: Qt.rgba(Material.background.r, Material.background.g, Material.background.b, 0.88)
        anchors.fill: parent
        radius: 8
        border.color: Qt.rgba(1, 1, 1, 0.12)
        border.width: 1

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            anchors.topMargin: 0
            anchors.bottomMargin: 0
            anchors.leftMargin: 0
            anchors.rightMargin: 0
            focus: false
            hoverEnabled: true
            drag.threshold: 10
            onClicked: {
                if(width_range.to === sidebarWidth){
                }else{
                    height_range.to = appWindow.height - 20
                    width_range.to = sidebarWidth
                    widthAnim.start()
                    heightAnim.start()
                }
                forceActiveFocus()
            }

            ToolbarPage {id: toolbarLayout}
            
            // Everything below the toolbar scrolls as one area when the
            // window is too short. Children must report implicitHeight.
            ScrollView {
                id: contentScroll
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: toolbarLayout.bottom
                anchors.bottom: parent.bottom
                anchors.topMargin: 5
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                anchors.bottomMargin: 6
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                // Slim bar; Material fades AsNeeded bars out when idle, so keep
                // it visible whenever there actually is more content to scroll to.
                ScrollBar.vertical: ScrollBar {
                    parent: contentScroll
                    x: contentScroll.width - width
                    y: contentScroll.topPadding
                    width: 6
                    height: contentScroll.availableHeight
                    policy: contentScroll.contentHeight > contentScroll.height
                            ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                }
                // keep content clear of the vertical scrollbar
                rightPadding: ScrollBar.vertical.policy === ScrollBar.AlwaysOn
                              ? ScrollBar.vertical.width + 4 : 0

                ColumnLayout {
                    id: renderingControlLayout
                    width: contentScroll.availableWidth
                }
            }
        }
    }
}
