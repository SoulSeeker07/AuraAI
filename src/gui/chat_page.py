from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ChatPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Chat page"))
