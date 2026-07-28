import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: chat
    color: "transparent"
    anchors.fill: parent

    property var messages: []

    ScrollView {
        anchors.fill: parent
        contentItem: Column {
            id: messagesColumn
            width: parent.width
            spacing: 8
        }
    }

    function appendMessage(text) {
        var component = Qt.createComponent("./MessageBubble.qml")
        if (component.status === Component.Ready) {
            var obj = component.createObject(messagesColumn, {"text": text})
            messagesColumn.addItem ? messagesColumn.addItem(obj) : null
        } else {
            console.log("Failed to create MessageBubble:", component.errorString())
        }
    }

    Component.onCompleted: {
        appendMessage("Welcome to Aura\nHow can I help you today?")
    }
}
