import QtQuick 2.0
import QtQuick.Controls 2.0
import QtQuick.Layouts 1.0

Window {
    id: root
    visible: controller.visible
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    width: 620
    height: 420
    color: "transparent"
    x: (Screen.width / 2) - (width / 2)
    y: Screen.height * 0.18

    Rectangle {
        anchors.fill: parent
        radius: 24
        color: Theme.panel
        border.color: Theme.border
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "Aura"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: controller.connection_state
                    color: controller.connection_state === "Connected" ? Theme.accent : Theme.secondary
                    font.pixelSize: 13
                }
            }

            ListView {
                id: overlayMessages
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: controller.messages
                clip: true
                spacing: 8
                delegate: Rectangle {
                    width: ListView.view.width
                    color: "transparent"
                    implicitHeight: messageText.implicitHeight + 12
                    Text {
                        id: messageText
                        text: modelData.text
                        wrapMode: Text.Wrap
                        color: Theme.text
                        font.pixelSize: 15
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                TextField {
                    id: inputField
                    Layout.fillWidth: true
                    placeholderText: "Ask anything..."
                    color: Theme.text
                    background: Rectangle { color: Theme.background; radius: 12; border.color: Theme.border }
                    Keys.onEscapePressed: controller.hide()
                    Keys.onEnterPressed: controller.send_message(inputField.text)
                    Keys.onReturnPressed: controller.send_message(inputField.text)
                }

                Button {
                    text: "Send"
                    onClicked: controller.send_message(inputField.text)
                }
            }
        }
    }
}
