import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: sidebar
    width: 220
    color: "transparent"

    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        Text { text: "Aura"; color: "#FFFFFF"; font.pixelSize: 18 }
        Text { text: "OS companion"; color: "#9BA1AE"; font.pixelSize: 12 }
    }
}
