import QtQuick 2.0
import QtQuick.Controls 2.0

Rectangle {
    id: root
    width: 240
    color: Theme.sidebar
    border.color: Theme.border
    border.width: 1
    signal pageChanged(string page)

    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Repeater {
            model: [{label: "New Chat", page: "chat"}, {label: "History", page: "history"}, {label: "Plugins", page: "plugins"}, {label: "Settings", page: "settings"}, {label: "About", page: "about"}]
            delegate: Rectangle {
                width: parent.width
                height: 42
                color: "transparent"
                border.color: Theme.border
                border.width: 1
                radius: Metrics.radiusSmall

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.pageChanged(modelData.page)
                }

                Text {
                    anchors.centerIn: parent
                    text: modelData.label
                    color: Theme.secondary
                    font.pixelSize: 15
                }
            }
        }
    }
}
