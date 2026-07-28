import QtQuick 2.0
import QtQuick.Controls 2.0
import QtQuick.Layouts 1.0

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 820
    minimumWidth: 900
    minimumHeight: 650
    title: "Aura"
    color: Theme.background
    flags: Qt.FramelessWindowHint | Qt.Window

    property string currentPage: "chat"

    Rectangle {
        anchors.fill: parent
        color: Theme.background
        radius: Metrics.radiusLarge
        border.color: Theme.border
        border.width: 1

        RowLayout {
            anchors.fill: parent
            spacing: 0

            Sidebar {
                Layout.preferredWidth: 240
                Layout.fillHeight: true
                onPageChanged: function(page) { root.currentPage = page }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                TitleBar {
                    Layout.fillWidth: true
                }

                StatusBar {
                    Layout.fillWidth: true
                }

                Loader {
                    id: pageLoader
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: currentPage === "history" ? "pages/HistoryPage.qml" : currentPage === "plugins" ? "pages/PluginPage.qml" : currentPage === "settings" ? "pages/SettingsPage.qml" : "pages/ChatPage.qml"
                }
            }
        }
    }
}
