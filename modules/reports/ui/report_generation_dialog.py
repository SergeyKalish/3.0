"""
Диалог выбора параметров отчёта.
"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton

# Константы для типов сортировки
SORT_BY_EXIT_TIME = "by_exit_time"  # По времени выхода (текущий)
SORT_BY_POSITION_BLOCKS = "by_position_blocks"  # По позициям (блоками)

SORT_OPTIONS = {
    SORT_BY_EXIT_TIME: "По времени выхода",
    SORT_BY_POSITION_BLOCKS: "По позициям (блоками)"
}


class ReportGenerationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Настройки отчёта")
        self.layout = QVBoxLayout()

        # Выбор формата
        size_layout = QHBoxLayout()
        size_label = QLabel("Формат листа:")
        self.size_combo = QComboBox()
        self.size_combo.addItems(["A4", "A3"])
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.size_combo)
        self.layout.addLayout(size_layout)

        # Выбор порядка сортировки
        sort_layout = QHBoxLayout()
        sort_label = QLabel("Порядок заполнения:")
        self.sort_combo = QComboBox()
        for key, value in SORT_OPTIONS.items():
            self.sort_combo.addItem(value, key)
        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self.sort_combo)
        self.layout.addLayout(sort_layout)

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
        :return: tuple (page_size, sort_order)
        """
        page_size = self.size_combo.currentText()
        sort_order = self.sort_combo.currentData()
        return page_size, sort_order
