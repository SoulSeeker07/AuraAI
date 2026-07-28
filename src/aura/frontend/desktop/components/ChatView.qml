import QtQuick 2.0

ListView {
    id: root
    clip: true
    spacing: 10

    delegate: Rectangle {
        width: ListView.view.width
        color: "transparent"
        implicitHeight: messageText.implicitHeight + 24

        Text {
            id: messageText
            width: parent.width - 32
            x: 16
            text: modelData.text
            wrapMode: Text.Wrap
            color: modelData.role === "assistant" ? "#FFFFFF" : "#DDE7FF"
            font.pixelSize: 16
        }
    }
}
