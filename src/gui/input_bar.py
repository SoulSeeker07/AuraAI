from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton


class InputBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.input = QLineEdit()
        self.send_button = QPushButton("Send")
        layout.addWidget(self.input)
        layout.addWidget(self.send_button)
