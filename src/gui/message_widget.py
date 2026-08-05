from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MessageWidget(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text))
