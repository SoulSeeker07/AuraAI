import QtQuick 2.0
import QtQuick.Layouts 1.0

Rectangle {
    height: 44
    color: Theme.panel
    border.color: Theme.border
    border.width: 1

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Rectangle {
            width: 10
            height: 10
            radius: 5
            color: controller.connection_state === "Connected" ? Theme.accent : "#EF4444"
        }

        Text {
            text: controller.connection_state
            color: Theme.text
            font.pixelSize: 13
        }
    }
}
