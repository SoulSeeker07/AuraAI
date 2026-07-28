import QtQuick 2.0

ListView {
    id: root
    clip: true
    spacing: 10
    delegate: MessageBubble {}
}
