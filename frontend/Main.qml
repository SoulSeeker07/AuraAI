import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

import "./components" as Components
import "./styles" as Styles

ApplicationWindow {
    id: root
    visible: true
    width: 1000
    height: 650
    title: "Aura AI"
    color: Styles.Colors.background
    flags: Qt.FramelessWindowHint

    Component.onCompleted: {
        root.x = (Screen.width - root.width) / 2
        root.y = (Screen.height - root.height) / 6
        enterAnim.running = true
    }

    // simple shadow rectangle behind the panel
    Rectangle {
        id: shadowHost
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 38
        width: root.width - 120
        height: root.height - 120
        radius: Styles.Colors.radius + 6
        color: "#000000"
        opacity: 0.22
    }

    // Main panel with rounded corners
    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 32
        width: root.width - 120
        height: root.height - 120
        radius: Styles.Colors.radius
        color: Styles.Colors.surface
        opacity: 0.0
        scale: 0.95

        // content
        Column {
            id: content
            anchors.fill: parent
            anchors.margins: 0

            Components.TitleBar {
                id: titleBar
                windowObj: root
                title: "✨ Aura"
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: titleBar.bottom
                anchors.bottom: parent.bottom
                color: "transparent"

                Column {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 12

                    Text {
                        text: "Welcome to Aura"
                        color: Styles.Colors.text
                        font.pixelSize: 20
                    }

                    Text {
                        text: "Milestone 1.2 — Premium window"
                        color: Styles.Colors.secondary
                        font.pixelSize: 14
                    }

                    Rectangle { height: 8; color: "transparent" }
                }
            }
        }

        Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }
        Behavior on scale { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }

        SequentialAnimation {
            id: enterAnim
            running: false
            PropertyAction { target: panel; property: "opacity"; value: 0.0 }
            PropertyAction { target: panel; property: "scale"; value: 0.95 }
            NumberAnimation { target: panel; property: "opacity"; from: 0.0; to: 1.0; duration: 220 }
            NumberAnimation { target: panel; property: "scale"; from: 0.95; to: 1.0; duration: 220 }
        }
    }
}
