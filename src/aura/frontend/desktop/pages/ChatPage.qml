import QtQuick 2.0
import QtQuick.Controls 2.0
import QtQuick.Layouts 1.0

Rectangle {
    color: "transparent"
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "Chat"
            color: Theme.text
            font.pixelSize: 22
            font.bold: true
        }

        ChatList {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: controller.messages
        }

        InputBar {
            Layout.fillWidth: true
        }
    }
}
