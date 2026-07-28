import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: searchBox
    height: 48
    radius: 12
    color: Styles.Colors.background
    property alias text: input.text

    signal focusInput()

    TextField {
        id: input
        anchors.fill: parent
        anchors.margins: 10
        placeholderText: "Ask anything..."
        font.pixelSize: 16
        color: Styles.Colors.text

        Keys.onReleased: {
            if (event.key === Qt.Key_Escape) {
                // bubble up; parent overlay handles closing
            }
        }
    }

    function focusInput() {
        input.forceActiveFocus()
    }
}
