import QtQuick.Dialogs


FileDialog {
    id: fileDialog
    title: "Select File"
    //currentFolder: StandardPaths.documentsLocation

    onAccepted: {
        MainCtrl.loadMesh(fileDialog.selectedFile)
    }
    onRejected: {
        console.log("File dialog rejected")
    }
}
