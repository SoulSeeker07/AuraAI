import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: title
    color: Theme.panel
    anchors.left: parent.left
    anchors.right: parent.right
    height: 44

    property alias window: Window

    Row {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        Text {
            text: "✨ Aura"
            color: Theme.text
            font.pixelSize: 16
            anchors.verticalCenter: parent.verticalCenter
        }

        Rectangle { width: 8; color: "transparent" }

        Item { Layout.fillWidth: true }

        // Window controls (non-functional placeholders)
        Row {
            spacing: 8
            anchors.verticalCenter: parent.verticalCenter

            Button {
                text: "_"
                onClicked: {
                    // TODO: minimize
                }
            }
            Button {
                text: "□"
                onClicked: {
                    // TODO: maximize
                }
            }
            Button {
                text: "✕"
                onClicked: {
                    Qt.quit()
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        drag.target: parent
        drag.axis: Drag.XandYAxis
        // Simple drag; production should use window startSystemMove()
    }
}
