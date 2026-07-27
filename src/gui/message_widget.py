from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class MessageWidget(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text))
