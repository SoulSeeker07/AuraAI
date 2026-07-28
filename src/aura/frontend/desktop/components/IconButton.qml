import QtQuick 2.0

Rectangle {
    width: 32
    height: 32
    radius: 8
    color: "transparent"
    border.color: "#2A3142"
    border.width: 1

    Text {
        anchors.centerIn: parent
        text: "•"
        color: "#FFFFFF"
        font.pixelSize: 16
    }
}
