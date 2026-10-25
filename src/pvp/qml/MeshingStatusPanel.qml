import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// Floating overlay that only appears while the mesher is running. Shows
// stage/elapsed time plus live max-energy and vertex/tet counts emitted
// from fTetWild's optimization loop. All state is wired straight from
// MeshingCtrl so the panel owns no mesher logic of its own.
Rectangle {
    id: root
    visible: active
    radius: 6
    color: Qt.rgba(0, 0, 0, 0.72)
    border.color: Qt.rgba(1, 1, 1, 0.12)
    border.width: 1
    implicitWidth: content.implicitWidth + 24
    implicitHeight: content.implicitHeight + 16
    z: 100

    property bool  active:        false
    property string stage:        ""
    property real  fraction:      NaN
    property real  maxEnergy:     NaN
    property int   vertexCount:   -1
    property int   tetCount:      -1
    property double startedAt:    0
    property int   elapsedSec:    0

    function _formatElapsed(sec) {
        var m = Math.floor(sec / 60);
        var s = sec % 60;
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    function _formatCount(n) {
        // Thousands separators without locale fuss (Qt.locale().toString on an
        // int gives "12,345.00" on some locales — we want "12,345").
        return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    Connections {
        target: MeshingCtrl
        function onMeshingStarted() {
            root.active = true
            root.stage = "Starting…"
            root.fraction = NaN
            root.maxEnergy = NaN
            root.vertexCount = -1
            root.tetCount = -1
            root.startedAt = Date.now()
            root.elapsedSec = 0
        }
        function onMeshingFinished(success) {
            root.active = false
        }
        function onProgressChanged(stage, fraction, maxEnergy, vNum, tNum) {
            root.stage = stage
            root.fraction = fraction
            if (!isNaN(maxEnergy))
                root.maxEnergy = maxEnergy
            if (vNum >= 0)
                root.vertexCount = vNum
            if (tNum >= 0)
                root.tetCount = tNum
        }
    }

    Timer {
        interval: 500; repeat: true; running: root.active
        onTriggered: root.elapsedSec =
            Math.floor((Date.now() - root.startedAt) / 1000)
    }

    ColumnLayout {
        id: content
        anchors.centerIn: parent
        spacing: 3

        RowLayout {
            spacing: 8
            BusyIndicator {
                running: root.active
                Layout.preferredWidth: 18
                Layout.preferredHeight: 18
            }
            Label {
                text: root.stage
                color: "white"
                font.bold: true
            }
        }

        Label {
            text: "⧗ " + root._formatElapsed(root.elapsedSec)
            color: "white"
            opacity: 0.75
            font.pixelSize: 11
        }

        // Divider only once we have metrics to show
        Rectangle {
            Layout.fillWidth: true
            visible: !isNaN(root.maxEnergy) || root.vertexCount >= 0
            height: 1
            color: Qt.rgba(1, 1, 1, 0.15)
            Layout.topMargin: 2
            Layout.bottomMargin: 2
        }

        Label {
            visible: !isNaN(root.maxEnergy)
            text: "Max energy: " + root.maxEnergy.toFixed(2)
            color: "white"
            font.pixelSize: 11
        }
        Label {
            visible: root.vertexCount >= 0
            text: "Vertices: " + root._formatCount(root.vertexCount)
            color: "white"
            font.pixelSize: 11
        }
        Label {
            visible: root.tetCount >= 0
            text: "Tets: " + root._formatCount(root.tetCount)
            color: "white"
            font.pixelSize: 11
        }
    }
}
