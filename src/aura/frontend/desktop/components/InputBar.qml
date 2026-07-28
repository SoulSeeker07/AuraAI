import QtQuick 2.0
import QtQuick.Controls 2.0
import QtQuick.Layouts 1.0

Rectangle {
    color: "#171B26"
    border.color: "#2A3142"
    border.width: 1
    height: 84

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        TextField {
            id: inputField
            Layout.fillWidth: true
            placeholderText: "Type a message…"
            color: "#FFFFFF"
            background: Rectangle { color: "#0F1117"; radius: 10; border.color: "#2A3142" }
        }

        Button {
            text: "Send"
            onClicked: controller.send_message(inputField.text)
        }
    }
}
