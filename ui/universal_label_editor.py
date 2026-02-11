# ui/universal_label_editor.py
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QButtonGroup, QCheckBox, QFrame, QSizePolicy
    # Убрали QFontMetrics из QtWidgets
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QFontMetrics # <-- QFontMetrics импортируем из QtGui

class UniversalLabelEditor(QWidget):
    """
    Виджет для универсальной разметки.
    Содержит:
    - QComboBox для выбора диапазона воспроизведения.
    - Панель с QCheckBox для выбора типа метки (только один активен).
    - Кнопку для установки метки выбранного типа в текущее время плеера.
    """
    # Сигнал, эмитируемый при запросе установки метки
    labelSet = pyqtSignal(str) # Передаёт выбранный label_type

    def __init__(self, video_player_widget=None):
        super().__init__()

        # self.label_types = ["Сегмент", "Пауза", "ЧИИ", "Смена"] # Старый список
        self.label_types = ["Сегмент", "Пауза", "Смена", "Гол", "Удаление"] # Обновлённый список без "ЧИИ"

        # --- НОВОЕ: Сохраняем ссылку на VideoPlayerWidget ---
        self.video_player_widget = video_player_widget
        # --- КОНЕЦ НОВОГО ---

        # --- UI ---
        layout = QVBoxLayout(self) # Основной вертикальный макет для виджета

        # --- 1. Новый горизонтальный макет для range_selector ---
        range_layout = QHBoxLayout() # Новый макет для QLabel и QComboBox

        range_selector_label = QLabel("Режим воспроизведения:")
        # Увеличиваем шрифт для QLabel
        range_font = QFont()
        range_font.setPointSize(10) # Увеличено в 2 раза (примерно)
        range_font.setBold(True)
        range_selector_label.setFont(range_font)

        self.range_selector = QComboBox()
        # Увеличиваем шрифт для QComboBox
        combo_font = QFont()
        combo_font.setPointSize(10) # Увеличено в 2 раза (примерно)
        combo_font.setBold(True)
        self.range_selector.setFont(combo_font)
        # Заполняем его позже извне (например, из MainWindow)
        self.range_selector.addItem("Всё видео")

        # Добавляем QLabel и QComboBox в новый горизонтальный макет
        range_layout.addWidget(range_selector_label)
        range_layout.addWidget(self.range_selector)

        # Добавляем горизонтальный макет в основной вертикальный
        layout.addLayout(range_layout)
        # ---

        # --- 2. Разделитель ---
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # --- 3. Горизонтальный макет для панели типа метки и кнопки ---
        editor_layout = QHBoxLayout()

        # --- 3.1. Панель с QCheckBox для выбора типа метки ---
        # Создаём QButtonGroup для логики "только один активен"
        self.label_type_group = QButtonGroup(self)
        self.label_type_group.setExclusive(True) # Включаем эксклюзивность

        # Вертикальный макет для чекбоксов
        checkbox_layout = QVBoxLayout()

        for label_type in self.label_types:
            cb = QCheckBox(label_type)
            # Увеличиваем шрифт для QCheckBox
            cb_font = QFont()
            cb_font.setPointSize(10) # Увеличено в 2 раза (примерно)
            cb_font.setBold(True)
            cb.setFont(cb_font)
            self.label_type_group.addButton(cb)
            checkbox_layout.addWidget(cb)

        # Устанавливаем первый чекбокс как активный по умолчанию
        if self.label_type_group.buttons():
            self.label_type_group.buttons()[0].setChecked(True)

        # Добавляем вертикальный макет чекбоксов в горизонтальный макет редактора
        editor_layout.addLayout(checkbox_layout)

        # --- 3.2. Кнопка установки метки ---
        self.set_label_button = QPushButton()
        self.set_label_button.clicked.connect(self._on_button_clicked)
        # Подключаем сигнал изменения выбора в группе к обновлению текста кнопки
        self.label_type_group.buttonToggled.connect(self._on_checkbox_toggled)
        # Стилизуем кнопку
        button_font = QFont()
        button_font.setPointSize(10) # Увеличиваем шрифт ещё больше, чтобы соответствовать или быть крупнее чекбоксов
        button_font.setBold(True)
        self.set_label_button.setFont(button_font)
        # self.set_label_button.setStyleSheet("border: 2px solid black;") # Пример рамки, можно добавить

        # Инициализируем текст кнопки
        initial_checked = self.label_type_group.checkedButton()
        if initial_checked:
            self._update_button_text(initial_checked.text())

        # Добавляем кнопку в горизонтальный макет редактора
        editor_layout.addWidget(self.set_label_button)

        # Добавляем горизонтальный макет редактора в основной вертикальный
        layout.addLayout(editor_layout)

    def _update_button_text(self, current_label_type: str):
        """Обновляет текст кнопки в зависимости от выбранного типа метки."""
        self.set_label_button.setText(f"Поставить '{current_label_type}'")

    def _on_checkbox_toggled(self, button, checked):
        """Обработчик изменения состояния QCheckBox в группе."""
        if checked:
            # Обновляем текст кнопки только если чекбокс стал активным
            self._update_button_text(button.text())

    def _on_button_clicked(self):
        """Обработчик нажатия кнопки 'Поставить метку'."""
        selected_button = self.label_type_group.checkedButton()
        if selected_button:
            selected_type = selected_button.text()
            # Эмитируем сигнал с типом меткиs
            self.labelSet.emit(selected_type)
        self.video_player_widget.setFocus()
        

    def handle_hotkey_pressed(self):
        """
        Метод, который вызывается из MainWindow при нажатии горячей клавиши '1'.
        Имитирует нажатие кнопки.
        """
        self._on_button_clicked()

    # --- Новый метод для получения текущего выбранного типа ---
    def get_current_label_type(self) -> str:
        """
        Возвращает текст активного (отмеченного) QCheckBox.
        Возвращает пустую строку, если ни один не активен (хотя по логике всегда должен быть один).
        """
        selected_button = self.label_type_group.checkedButton()
        return selected_button.text() if selected_button else ""
    # --- Конец нового метода ---

    # --- Новый метод для получения QComboBox range_selector ---
    def get_range_selector(self) -> QComboBox:
        """Возвращает QComboBox для выбора диапазона."""
        return self.range_selector
    # --- Конец нового метода ---

    def set_current_label_type(self, label_type: str):
        """
        Устанавливает активный чекбокс по переданному типу метки.
        """
        for button in self.label_type_group.buttons():
            if button.text() == label_type:
                button.setChecked(True)
                self._update_button_text(label_type)
                break