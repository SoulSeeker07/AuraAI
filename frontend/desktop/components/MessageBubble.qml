import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: bubble
    width: parent.width
    color: Theme.card
    radius: 10
    property string text: ""

    Text {
        anchors.fill: parent
        anchors.margins: 12
        text: bubble.text
        color: Theme.text
        wrapMode: Text.Wrap
    }
}
