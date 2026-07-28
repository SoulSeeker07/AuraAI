import QtQuick 2.0

Rectangle {
    width: 12
    height: 12
    radius: 6
    color: controller.connection_state === "Connected" ? "#4F8CFF" : controller.connection_state === "Connecting" ? "#F59E0B" : controller.connection_state === "Reconnecting" ? "#F59E0B" : "#EF4444"
}
