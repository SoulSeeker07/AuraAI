import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15

Window {
    id: overlay
    objectName: "overlayWindow"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    visibility: Window.Windowed
    color: "transparent"
    modality: Qt.NonModal
    visible: false

    property int panelWidth: 720
    property int panelHeight: 390

    Rectangle {
        id: panel
        width: overlay.panelWidth
        height: overlay.panelHeight
        radius: 18
        color: "#1A1D29"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: Math.max(70, (Screen.height / 7))
        opacity: 1.0

        // content using basic QtQuick items (avoid Layouts dependency)
        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Text {
                text: "✨ Aura"
                color: "#FFFFFF"
                font.pixelSize: 20
            }

            Text {
                text: "Ask me anything..."
                color: "#9BA1AE"
                font.pixelSize: 14
            }

            TextField {
                id: input
                objectName: "input"
                placeholderText: "Ask anything..."
                anchors.left: parent.left
                anchors.right: parent.right
                height: 40
                font.pixelSize: 16
                color: "#FFFFFF"
                focus: visible

                Keys.onReleased: {
                    if (event.key === Qt.Key_Escape) {
                        overlay.visible = false
                    }
                }
            }

            Item {
                id: toolsRow
                anchors.left: parent.left
                anchors.right: parent.right
                height: 40

                Text {
                    id: toolsText
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 0
                    text: "📎    🎤"
                    color: "#FFFFFF"
                    font.pixelSize: 20
                }

                Button {
                    id: sendBtn
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    text: "➜"
                    onClicked: { input.text = "" }
                }
            }
        }

        Behavior on opacity { NumberAnimation { duration: 220 } }
    }

    function showOverlay() {
        overlay.visible = true
        overlay.opacity = 1.0
        var screen = Qt.application.screens[0]
        x = Math.floor((screen.availableWidth - panel.width) / 2)
        y = Math.floor(screen.availableY + Math.max(70, screen.availableHeight / 7))
        Qt.callLater(function(){ input.forceActiveFocus(); })
    }

    function hideOverlay() {
        overlay.visible = false
    }

    Keys.onReleased: {
        if (event.key === Qt.Key_Escape) overlay.visible = false
    }
}
