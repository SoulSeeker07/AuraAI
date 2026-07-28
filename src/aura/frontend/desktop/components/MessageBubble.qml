import QtQuick 2.0

Rectangle {
    width: ListView.view.width
    color: "transparent"
    implicitHeight: bubbleText.implicitHeight + 24

    Rectangle {
        anchors.left: modelData.role === "assistant" ? undefined : parent.left
        anchors.right: modelData.role === "assistant" ? parent.right : undefined
        width: Math.min(parent.width * 0.75, bubbleText.implicitWidth + 24)
        radius: 16
        color: modelData.role === "assistant" ? Theme.panel : Theme.accent
        border.color: Theme.border
        border.width: 1
        implicitHeight: bubbleText.implicitHeight + 20

        Text {
            id: bubbleText
            anchors.fill: parent
            anchors.margins: 12
            text: modelData.text
            wrapMode: Text.Wrap
            color: Theme.text
            font.pixelSize: 15
        }
    }
}
