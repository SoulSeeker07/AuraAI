import QtQuick 2.0
import QtQuick.Controls 2.0

Rectangle {
    id: root
    height: 48
    color: Theme.panel
    border.color: Theme.border
    border.width: 1

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        text: "Aura"
        color: Theme.text
        font.pixelSize: 16
        font.bold: true
    }
}
