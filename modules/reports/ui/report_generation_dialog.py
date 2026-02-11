"""
Диалог выбора параметров отчёта.
"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton

class ReportGenerationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Настройки отчёта")
        self.layout = QVBoxLayout()

        # Выбор формата (единственный параметр)
        size_layout = QHBoxLayout()
        size_label = QLabel("Формат листа:")
        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A3"])
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.size_combo)
        self.layout.addLayout(size_layout)

        # Кнопки OK/Cancel
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Отмена")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(buttons_layout)

        self.setLayout(self.layout)

    def get_selected_params(self):
        """
        Возвращает выбранные параметры.
        :return: tuple (page_size,) — режим больше не выбирается
        """
        return self.size_combo.currentText()