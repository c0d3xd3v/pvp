import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: solutionRoot
    property bool isVectorValued: false
    property real animTime: 0
    Layout.fillWidth: true
    Layout.margins: 5

    NumberAnimation {
        id: numAnim
        target: solutionRoot
        property: "animTime"
        from: 0.0
        to: 1.0
        duration: 2000
        loops: Animation.Infinite
        running: false
    }

    onAnimTimeChanged: ResultCtrl.setAnimationTime(animTime)

    function updateFunctionList() {
            comboBox.model = ResultCtrl.getFunctionNames()
    }
    
    function updateVectorDisplacement() {
        var s = parseFloat(displacementScaling.text)
        var c = switchVectorValued.checked
        ResultCtrl.apply_vector_field_on_position(c, s)
    }

    SequentialAnimation {
        id: resize_details
        NumberAnimation {
            target: vectorValuedControls;
            id: navvc_
            property: "height";
            to: 0;
            duration: 1
        }
    }
    SequentialAnimation {
        id: resize_details_open
        NumberAnimation {
            target: vectorValuedControls;
            id: navvc
            property: "height";
            to: 100;
            duration: 1
        }
    }
    
    Component.onCompleted: function() {
        navvc.to = vectorValuedControls.height
        navvc_.to = vectorValuedControls.height - animationControls.height 
        close()
        updateFunctionList()
        MainCtrl.meshLoaded.connect(updateFunctionList)
    }
    
    RowLayout {
        id: dieseRow
        Label {
            opacity: 0.789
            text: qsTr("Gridfunction")
            Layout.preferredWidth: implicitWidth
        }
        ComboBox {
            id: comboBox
            opacity: 0.789
            Layout.fillWidth: true
            onCurrentTextChanged: function() {
                if(MainCtrl !== undefined && ResultCtrl.getFunctionNames().length > 0) {
                    numAnim.running = false
                    animationButton.icon.source = "qrc:/icons/pqVcrPlay.svg"
                    ResultCtrl.selectFunctionByName(currentText)
                    vectorValuedControls.visible = ResultCtrl.isCurrentFieldVectorValued()
                    if(vectorValuedControls.visible)
                        updateVectorDisplacement()
                }
            }
        }
    }

    ColumnLayout {
        id:vectorValuedControls
        Layout.fillWidth: true
        clip: true

        RowLayout {
            spacing: 1
            Label {
                opacity: 0.789
                text: qsTr("displacement")
                Layout.preferredWidth: implicitWidth
                Layout.margins: 0
            }
            Switch {
                Layout.margins: 0
                id: switchVectorValued
                text: qsTr("")
                checked: true
                onCheckedChanged: {
                    if(!checked) 
                    {
                        resize_details.start()
                        vectorValuedControls.implicitHeight = vectorValuedControls.height - animationControls.implicitHeight
                        animationControls.opacity = 0;
                        //animationControls.visible = false;
                        placeHolder.visible = true;
                        displacementScaling.enabled = false;
                        //animationTimer.running = false;
                        numAnim.running = false;
                        animationButton.icon.source = "qrc:/icons/pqVcrPlay.svg"
                    }else {
                        resize_details_open.start()
                        vectorValuedControls.implicitHeight = vectorValuedControls.height + animationControls.implicitHeight
                        animationControls.opacity = 1;
                        //animationControls.visible = true;
                        placeHolder.visible = false;
                        displacementScaling.enabled = true;
                    }
                    updateVectorDisplacement()
                }
            }
            Label {
                opacity: 0.789
                text: qsTr("scale")
                Layout.fillWidth: false
                enabled: displacementScaling.enabled
            }
            TextField {
                id: displacementScaling
                opacity: 0.789
                Layout.fillWidth: true
                placeholderText: qsTr("Text Field")
                text: "1.0"
                validator: DoubleValidator {
                    bottom: 1.0
                }
                onEditingFinished: {
                    if (acceptableInput) {
                        updateVectorDisplacement()
                    }
                }
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: vectorValuedControls.opacity === 0 ? 1 : 0
        }
        ColumnLayout {
            function roundToDecimals(num, decimals) {
                return Math.round(num * 10 ** decimals) / 10 ** decimals;
            }
            id:animationControls
            Layout.fillWidth: true
            Layout.preferredHeight: switchVectorValued.checked ? implicitHeight : 0
            clip: true
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Label {
                    text: "Animation"
                }
                /*
                ComboBox {
                    id: animationType
                    Layout.fillWidth: true
                    model: ["periodic"]
                }
                */
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Button {
                    id: animationButton
                    Layout.fillWidth: true
                    icon.source: "qrc:/icons/pqVcrPlay.svg"
                    onClicked: function() {
                        if(numAnim.running === false)
                        {
                            icon.source = "qrc:/icons/pqVcrPause.svg"
                            numAnim.running = true

                        }else {
                            icon.source = "qrc:/icons/pqVcrPlay.svg"
                            numAnim.running = false
                        }
                    }
                }
                /*
                Slider {
                    id: animationSlider
                    Layout.fillWidth: true
                    onValueChanged: function() {
                        var t = animationControls.roundToDecimals(animationSlider.value, 3);
                        MainCtrl.animationTimeout(t);
                    }
                }
                */
            }


        }
        Item {
            id:placeHolder
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
