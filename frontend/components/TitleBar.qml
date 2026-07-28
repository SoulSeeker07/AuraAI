import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: titlebar
    property string title: ""
    height: 52
    color: "transparent"

    // windowObj should be set by the parent (ApplicationWindow)
    property var windowObj: null

    Row {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        Text {
            id: titleText
            text: title
            color: "white"
            font.pixelSize: 16
            verticalAlignment: Text.AlignVCenter
        }

        Item { Layout.fillWidth: true }

        Button {
            id: minBtn
            text: "–"
            onClicked: if (windowObj) windowObj.showMinimized()
            background: Rectangle { color: "transparent" }
        }

        Button {
            id: maxBtn
            text: "▢"
            onClicked: if (windowObj) windowObj.showMaximized()
            background: Rectangle { color: "transparent" }
        }

        Button {
            id: closeBtn
            text: "✕"
            onClicked: if (windowObj) windowObj.close()
            background: Rectangle { color: "transparent" }
        }
    }

    MouseArea {
        anchors.fill: parent
        drag.target: null
        onPressed: {
            // store initial press position if needed
        }
        onPositionChanged: {
            if (!windowObj) return
            // Move the window by delta - uses mouse.previousX/Y to compute delta
            windowObj.x += mouse.x - mouse.previousX
            windowObj.y += mouse.y - mouse.previousY
        }
        onDoubleClicked: {
            if (windowObj) windowObj.showMaximized()
        }
    }
}
