import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "partitioning"
import "meshtools"

Item {
    Layout.fillWidth: true
    Layout.fillHeight: true

    ColumnLayout {
        anchors.fill: parent
        MeshtoolsList {
            Layout.fillWidth: true
        }
        PartitionList {
            Layout.fillWidth: true
            Layout.fillHeight: true
        } 
    }   
}
