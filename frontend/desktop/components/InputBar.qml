import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: input
    color: Theme.panel
    height: 64
    property alias text: inputField.text
    signal onSend(string)

    Row {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        Button { text: "📎" }
        Button { text: "🎤" }

        TextField {
            id: inputField
            placeholderText: "Type your message..."
            anchors.verticalCenter: parent.verticalCenter
            focus: true
            onAccepted: input.onSend(text)
            width: parent.width - 180
        }

        Button {
            text: "➜"
            onClicked: {
                input.onSend(inputField.text)
            }
        }
    }
}
