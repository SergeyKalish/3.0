# ui/report_viewer_window.py

import io
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap


class ReportViewerWindow(QMainWindow):
    """
    Окно просмотра сгенерированного отчёта.
    Изображение всегда вписано в доступную область окна с сохранением пропорций.
    Поддерживает обновление отчёта через callback.
    """

    closing = pyqtSignal()

    def __init__(self, pil_image, title="Отчёт", refresh_callback=None, parent=None):
        super().__init__(parent)
        self.pil_image = pil_image
        self.refresh_callback = refresh_callback
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

        self.auto_refresh_checkbox = QCheckBox("Автообновление")
        button_layout.addWidget(self.auto_refresh_checkbox)

        button_layout.addStretch()
        layout.addLayout(button_layout)

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

    def closeEvent(self, event):
        self.closing.emit()
        super().closeEvent(event)

    def on_refresh_clicked(self):
        """Обработчик нажатия кнопки 'Обновить'."""
        if self.refresh_callback is None:
            QMessageBox.warning(self, "Предупреждение", "Обновление недоступно.")
            return

        try:
            new_image, new_title = self.refresh_callback()
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
