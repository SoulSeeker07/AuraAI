import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: inputBar
    width: parent.width
    height: 48
    color: "transparent"

    TextInput {
        anchors.fill: parent
        placeholderText: "Ask anything..."
        font.pixelSize: 14
    }
}
