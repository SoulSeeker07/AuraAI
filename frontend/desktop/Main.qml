import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15

ApplicationWindow {
    id: window
    visible: true
    width: 1000
    height: 700
    color: Theme.background
    flags: Qt.FramelessWindowHint

    title: "Aura"

    Rectangle {
        anchors.fill: parent
        color: Theme.background

        Column {
            anchors.fill: parent

            // Title bar
            TitleBar {
                id: titleBar
                width: parent.width
                height: 44
            }

            Row {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: titleBar.bottom
                anchors.bottom: parent.bottom

                // Sidebar
                Sidebar {
                    id: sidebar
                    width: 220
                }

                // Main chat area
                Rectangle {
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.left: sidebar.right
                    anchors.right: parent.right
                    color: Theme.panel

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        ChatView {
                            id: chatView
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: parent.height - 120
                        }

                        InputBar {
                            id: inputBar
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 64
                            onSend: {
                                DesktopController.send(text)
                                inputBar.text = ""
                            }
                        }
                    }
                }
            }
        }
    }

    // Status overlay (simple)
    Text {
        id: statusText
        text: "Status: " + (DesktopController ? "Starting..." : "No backend")
        color: Theme.secondary
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 8
        font.pixelSize: 12
    }

    Connections {
        target: DesktopController
        onStatus: {
            statusText.text = "Status: " + status
        }
        onMessageReceived: {
            chatView.appendMessage(message)
        }
    }
}
