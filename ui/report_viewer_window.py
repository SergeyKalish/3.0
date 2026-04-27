# ui/report_viewer_window.py

import io
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QSizePolicy, QButtonGroup
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap


class ReportViewerWindow(QMainWindow):
    """
    Окно просмотра сгенерированного отчёта.
    Изображение всегда вписано в доступную область окна с сохранением пропорций.
    Поддерживает переключение между Матч/Периоды и обновление.
    """

    def __init__(self, pil_image, title="Отчёт", mode_text="Всё видео",
                 generate_callback=None, parent=None):
        super().__init__(parent)
        self.pil_image = pil_image
        self.generate_callback = generate_callback
        self.current_mode = mode_text
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Панель кнопок
        button_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        button_layout.addWidget(self.refresh_button)

        button_layout.addSpacing(20)

        # Группа переключателей режимов
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        self.mode_buttons = {}

        for btn_text in ["Матч", "Период 1", "Период 2", "Период 3"]:
            btn = QPushButton(btn_text)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            self.mode_button_group.addButton(btn)
            self.mode_buttons[btn_text] = btn
            button_layout.addWidget(btn)

        self.mode_button_group.buttonClicked.connect(self.on_mode_changed)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Устанавливаем начальную нажатую кнопку
        self._select_mode_button(mode_text)

        # Контейнер для изображения (занимает всё оставшееся пространство)
        self.image_container = QWidget()
        self.image_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self.image_container, stretch=1)

        # QLabel для отображения изображения
        self.image_label = QLabel(self.image_container)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: lightgray;")

        # Первоначальная отрисовка
        self._update_pixmap()

    def _select_mode_button(self, mode_text: str):
        """Выбирает и нажимает кнопку, соответствующую режиму."""
        mapping = {
            "Всё видео": "Матч",
            "Период 1": "Период 1",
            "Период 2": "Период 2",
            "Период 3": "Период 3",
        }
        btn_text = mapping.get(mode_text)
        if btn_text and btn_text in self.mode_buttons:
            self.mode_buttons[btn_text].setChecked(True)

    def _mode_text_from_button(self, btn_text: str) -> str:
        """Преобразует текст кнопки в mode_text для генерации отчёта."""
        mapping = {
            "Матч": "Всё видео",
            "Период 1": "Период 1",
            "Период 2": "Период 2",
            "Период 3": "Период 3",
        }
        return mapping.get(btn_text, "Всё видео")

    def on_mode_changed(self, button):
        """Обработчик переключения режима кнопками."""
        new_mode = self._mode_text_from_button(button.text())
        if new_mode == self.current_mode:
            return
        self.current_mode = new_mode
        self._regenerate()

    def on_refresh_clicked(self):
        """Обработчик нажатия кнопки 'Обновить'."""
        self._regenerate()

    def _regenerate(self):
        """Перегенерирует отчёт для текущего режима."""
        if self.generate_callback is None:
            QMessageBox.warning(self, "Предупреждение", "Генерация отчёта недоступна.")
            return

        try:
            new_image, new_title = self.generate_callback(self.current_mode)
            self.pil_image = new_image
            self.setWindowTitle(new_title)
            self._update_pixmap()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка обновления отчёта",
                f"Не удалось обновить отчёт:\n{str(e)}\n\nОкно будет закрыто."
            )
            self.close()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def _pil_to_pixmap(self, pil_image):
        """Конвертирует PIL Image в QPixmap через PNG-буфер."""
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG')
        buffer.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def _update_pixmap(self):
        """Обновляет QLabel с масштабированием изображения под размер контейнера."""
        if self.pil_image is None:
            self.image_label.setText("Нет изображения")
            return

        try:
            pixmap = self._pil_to_pixmap(self.pil_image)
            # Размеры контейнера минус небольшой отступ
            container_w = max(1, self.image_container.width() - 4)
            container_h = max(1, self.image_container.height() - 4)

            scaled = pixmap.scaled(
                container_w,
                container_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            # Центрируем label внутри контейнера
            label_x = (self.image_container.width() - scaled.width()) // 2
            label_y = (self.image_container.height() - scaled.height()) // 2
            self.image_label.setGeometry(label_x, label_y, scaled.width(), scaled.height())
        except Exception as e:
            self.image_label.setText(f"Ошибка отображения изображения:\n{str(e)}")
            print(f"[DEBUG ReportViewerWindow] Ошибка отображения: {e}")
