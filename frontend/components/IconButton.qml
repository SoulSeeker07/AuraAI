import QtQuick 2.15
import QtQuick.Controls 2.15

Button {
    id: iconBtn
    property alias iconText: label.text
    background: Rectangle { color: "transparent" }
    contentItem: Text { id: label; text: ""; color: Styles.Colors.text; font.pixelSize: 16 }
}
