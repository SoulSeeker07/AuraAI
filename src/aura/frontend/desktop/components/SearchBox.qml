import QtQuick 2.0
import QtQuick.Controls 2.0

TextField {
    placeholderText: "Search"
    color: Theme.text
    background: Rectangle {
        color: Theme.panel
        radius: Metrics.radiusSmall
        border.color: Theme.border
        border.width: 1
    }
}
