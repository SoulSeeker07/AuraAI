import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: sidebar
    color: Theme.panel
    width: 220

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        Button { text: "Chat" }
        Button { text: "History" }
        Button { text: "Plugins" }
        Button { text: "Settings" }
        Rectangle { height: 1; color: Theme.background }
        Text { text: "Aura v0.1"; color: Theme.secondary }
    }
}
