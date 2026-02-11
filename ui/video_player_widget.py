# Ниже находится содержимое файла: ..\4.0\1.0\ui\video_player_widget.py

# ui/video_player_widget.py

import sys
import os
import cv2
import time
from typing import List, Optional
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QComboBox, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont, QMouseEvent

# === Допустимые значения скорости: от -3.0 до +3.0 с шагом 0.2, без 0 ===
SPEED_VALUES = [round(x * 0.2, 1) for x in range(-15, 0)] + [round(x * 0.2, 1) for x in range(1, 16)]
# → [-3.0, -2.8, ..., -0.2, 0.2, ..., 2.8, 3.0]

class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Используем текущий диапазон слайдера для вычисления значения
            val = self.minimum() + (self.maximum() - self.minimum()) * event.x() / self.width()
            self.setValue(int(val))
            self.sliderReleased.emit()
        super().mousePressEvent(event)

class VideoPlaybackController:
    """
    Класс, отвечающий за ядро воспроизведения и базовую логику "схлопывания".
    """
    def __init__(self):
        self.video_path = None
        self.cap = None
        self.fps = 30.0
        self.total_frames = 0
        self.total_duration_sec = 0.0
        self.current_frame = 0
        self.current_time_sec = 0.0
        self.playing = False
        self.speed = 1.0
        self.last_frame_time = 0.0
        # --- Новые поля для "схлопывания" ---
        self.nav_start_global = 0.0  # Начало доступной области (глобальное время)
        self.nav_end_global = 0.0    # Конец доступной области (глобальное время)
        self.nav_start_local = 0.0   # Смещение для отображения локального времени (глобальное время начала интервала)
        self.nav_duration = 0.0      # Длительность доступной области (для отображения локального времени)

    def load_video(self, path):
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise IOError("Не удалось открыть видео")
        self.video_path = path
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.total_duration_sec = self.total_frames / self.fps
        self.current_frame = 0
        self.current_time_sec = 0.0
        # Сброс "схлопывания" при загрузке видео
        self.set_navigation_bounds(0.0, self.total_duration_sec)
        self.playing = False
        self.speed = 1.0

    def set_navigation_bounds(self, start_sec: float, end_sec: float):
        """
        Устанавливает границы доступной области навигации.
        start_sec и end_sec - глобальные таймкоды.
        """
        self.nav_start_global = max(0.0, min(self.total_duration_sec, start_sec))
        self.nav_end_global = max(self.nav_start_global, min(self.total_duration_sec, end_sec))
        self.nav_start_local = self.nav_start_global
        self.nav_duration = self.nav_end_global - self.nav_start_global
        # Ограничиваем текущее время новыми границами
        self.current_time_sec = max(self.nav_start_global, min(self.nav_end_global, self.current_time_sec))

    def get_navigation_bounds(self):
        """Возвращает текущие границы навигации."""
        return self.nav_start_global, self.nav_end_global

    def get_current_time(self):
        return self.current_time_sec

    def get_total_duration(self):
        return self.total_duration_sec

    def is_playing(self):
        return self.playing

    def get_local_time_for_display(self):
        """Возвращает локальное время для отображения на UI."""
        return max(0.0, min(self.nav_duration, self.current_time_sec - self.nav_start_local))

    def get_local_duration_for_display(self):
        """Возвращает локальную длительность для отображения на UI."""
        return self.nav_duration

    def set_speed(self, new_speed):
        if new_speed not in SPEED_VALUES:
            new_speed = min(SPEED_VALUES, key=lambda x: abs(x - new_speed))
        self.speed = new_speed

    def toggle_play(self):
        if not self.playing and abs(self.speed) < 0.2:
            self.set_speed(1.0)
        self.playing = not self.playing
        if self.playing:
            self.last_frame_time = time.time()
        else:
            self.last_frame_time = 0.0

    def playback_step(self):
        if not self.cap or not self.playing:
            return

        now = time.time()
        elapsed = now - self.last_frame_time
        self.last_frame_time = now

        self.current_time_sec += elapsed * self.speed
        # Ограничиваем время границами "схлопывания"
        if self.current_time_sec <= self.nav_start_global:
            self.current_time_sec = self.nav_start_global
            self.playing = False
        elif self.current_time_sec >= self.nav_end_global:
            self.current_time_sec = self.nav_end_global
            self.playing = False

        self.current_frame = int(round(self.current_time_sec * self.fps))

    def seek_to_time(self, seconds):
        # seconds - глобальное время
        self.current_time_sec = max(self.nav_start_global, min(self.nav_end_global, seconds))
        self.current_frame = int(round(self.current_time_sec * self.fps))
        # --- Новое: обновляем last_frame_time при ручной установке времени ---
        self.last_frame_time = time.time()
        # ---

    def seek_delta(self, delta_sec):
        new_time = self.current_time_sec + delta_sec
        self.seek_to_time(new_time)
     # --- Новое: обновляем last_frame_time при ручной установке времени ---
        self.last_frame_time = time.time()
    # ---

    def cleanup(self):
        if self.cap:
            self.cap.release()
        self.cap = None

class VideoPlayerWidget(QWidget):
    positionChanged = pyqtSignal(float)
    playbackStateChanged = pyqtSignal(bool)
    speedChanged = pyqtSignal(float)
    videoLoaded = pyqtSignal(str, float, float)
    pointHotkeyPressed = pyqtSignal() # <-- Новый сигнал Клавиша '1'
    # --- НОВОЕ: Сигналы для "прилипания" ---
    snapToPreviousRequested = pyqtSignal() # Клавиша '8'
    snapToNextRequested = pyqtSignal()     # Клавиша '9'
    # --- КОНЕЦ НОВОГО ---

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.controller = VideoPlaybackController()
        self.display_mode = "low"
        self.timer = QTimer()
        self.timer.timeout.connect(self.playback_step)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.video_label = QLabel("Загрузите видео")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.setFixedSize(1440, 810)
        self.video_label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.video_label, alignment=Qt.AlignCenter)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont("Arial", 10))
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)

        self.slider = ClickableSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)
        self.slider.sliderReleased.connect(self.on_slider_released)
        layout.addWidget(self.slider)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFocusPolicy(Qt.NoFocus)
        self.play_btn.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.play_btn)

        self.reverse_btn = QPushButton("◀ Reverse")
        self.reverse_btn.setFocusPolicy(Qt.NoFocus)
        self.reverse_btn.clicked.connect(self.toggle_reverse)
        ctrl_layout.addWidget(self.reverse_btn)

        self.speed_label = QLabel("Speed: +1.0x")
        ctrl_layout.addWidget(self.speed_label)

        # --- Новое: кнопки ±300 сек ---
        for delta, text in [(-300, "<<< -300s"), (-30, "←30s"), (-5, "←5s"), (5, "→5s"), (30, "→30s"), (300, "+300s >>>")]:
            btn = QPushButton(text)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _, d=delta: self.seek_delta(d))
            # Уменьшаем размер шрифта для новых кнопок, чтобы вместились
            if abs(delta) == 300:
                btn.setFont(QFont("Arial", 8))
            ctrl_layout.addWidget(btn)
        # --- Конец нового ---

        layout.addLayout(ctrl_layout)

        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(10)
        quality_layout.addWidget(QLabel("Качество:"))
        self.quality_combo = QComboBox()
        self.quality_combo.setFocusPolicy(Qt.NoFocus)
        self.quality_combo.addItems([
            "Низкое (480×270 → 1440×810)",
            "Среднее (960×540 → 1440×810)",
            "Высокое (до 1440×810)"
        ])
        self.quality_combo.setCurrentIndex(0)
        self.quality_combo.currentIndexChanged.connect(self.on_quality_changed)
        quality_layout.addWidget(self.quality_combo)
        layout.addLayout(quality_layout)

        self.setLayout(layout)

    def on_quality_changed(self, index):
        modes = ["low", "medium", "high"]
        self.display_mode = modes[index]
        self.show_current_frame()

    def load_video(self, path):
        try:
            self.controller.load_video(path)
            self.videoLoaded.emit(path, self.controller.total_duration_sec, self.controller.fps)
            self.update_ui()
            self.show_current_frame()
        except IOError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть видео:\n{str(e)}")

    def set_navigation_bounds(self, start_sec: float, end_sec: float):
        """Устанавливает границы навигации через контроллер."""
        self.controller.set_navigation_bounds(start_sec, end_sec)
        self.update_ui()

    def toggle_play(self):
        self.controller.toggle_play()
        self.play_btn.setText("⏸ Pause" if self.controller.playing else "▶ Play")
        self.playbackStateChanged.emit(self.controller.playing)
        if self.controller.playing:
            self.timer.start(20)
        else:
            self.timer.stop()
        self.update_ui()

    def toggle_reverse(self):
        # --- Изменение: умножаем текущую скорость на -1 ---
        new_speed = -self.controller.speed
        self.controller.set_speed(new_speed) # set_speed уже обновляет self.controller.speed
        # --- Новое: обновляем last_frame_time ---
        self.controller.last_frame_time = time.time()
        # ---
        self.update_speed_ui()
        self.controller.playing = True
        self.play_btn.setText("⏸ Pause")
        self.playbackStateChanged.emit(True)
        if not self.timer.isActive():
            self.timer.start(20)

    # --- Новое: выносим обновление UI скорости в отдельный метод ---
    def update_speed_ui(self):
        sign = "+" if self.controller.speed >= 0 else ""
        self.speed_label.setText(f"Speed: {sign}{self.controller.speed:.1f}x")
        self.speedChanged.emit(self.controller.speed)

    def set_speed(self, new_speed):
        self.controller.set_speed(new_speed)
        # --- Изменение: вызываем общий метод обновления UI скорости ---
        self.update_speed_ui()
        # ---
        if self.controller.playing:
            self.controller.last_frame_time = time.time() # Обновить таймер при смене скорости
        self.update_ui()

    def playback_step(self):
        self.controller.playback_step()
        self.show_current_frame()
        self.update_ui()
        self.positionChanged.emit(self.controller.current_time_sec)

    def show_current_frame(self):
        if not self.controller.cap:
            return
        self.controller.cap.set(cv2.CAP_PROP_POS_FRAMES, self.controller.current_frame)
        ret, frame = self.controller.cap.read()
        if not ret:
            return
        h_orig, w_orig = frame.shape[:2]
        if self.display_mode == "low":
            render_w, render_h = 480, 270
        elif self.display_mode == "medium":
            render_w, render_h = 960, 540
        else:
            if w_orig > 1440 or h_orig > 810:
                scale = min(1440 / w_orig, 810 / h_orig)
                render_w = int(w_orig * scale)
                render_h = int(h_orig * scale)
            else:
                render_w, render_h = w_orig, h_orig

        if (w_orig, h_orig) != (render_w, render_h):
            frame = cv2.resize(frame, (render_w, render_h), interpolation=cv2.INTER_AREA)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        scaled_pixmap = pixmap.scaled(1440, 810, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)

    def update_ui(self):
        # Отображаем локальное время для текущей области "схлопывания"
        local_time = self.controller.get_local_time_for_display()
        local_duration = self.controller.get_local_duration_for_display()

        curr_h = int(local_time // 3600)
        curr_m = int((local_time % 3600) // 60)
        curr_s = int(local_time % 60)
        total_h = int(local_duration // 3600)
        total_m = int((local_duration % 3600) // 60)
        total_s = int(local_duration % 60)
        curr_str = f"{curr_h:02d}:{curr_m:02d}:{curr_s:02d}"
        total_str = f"{total_h:02d}:{total_m:02d}:{total_s:02d}"
        self.time_label.setText(f"{curr_str} / {total_str}")

        # Обновляем слайдер в локальных координатах
        self.slider.setMaximum(int(local_duration * 10))
        slider_val = int(local_time * 10)
        self.slider.blockSignals(True)
        self.slider.setValue(slider_val)
        self.slider.blockSignals(False)

    def on_slider_released(self):
        # Получаем значение слайдера в локальных координатах
        local_time = self.slider.value() / 10.0
        # Преобразуем в глобальное время
        global_time = self.controller.nav_start_local + max(0.0, min(self.controller.nav_duration, local_time))
        # Устанавливаем через контроллер
        self.controller.seek_to_time(global_time)
        self.show_current_frame()
        self.update_ui()
        self.positionChanged.emit(self.controller.current_time_sec)
        #if self.controller.playing:
        #    self.toggle_play() # Останавливаем при перемотке
        
        # --- Новое: устанавливаем фокус на VideoPlayerWidget после перемотки слайдером ---
        self.setFocus()
        # ---

# --- Новое: метод для перехода к глобальному времени ---
    def go_to_time(self, global_time_sec: float):
        """
        Переходит к указанному *глобальному* времени.
        Обновляет состояние контроллера и UI.
        """
        # Устанавливаем время в контроллере (он принимает глобальное время)
        self.controller.seek_to_time(global_time_sec)
        # Обновляем отображение кадра и UI (включая слайдер, время)
        self.show_current_frame()
        self.update_ui()
        self.positionChanged.emit(self.controller.current_time_sec) # Опционально, если нужно сигнализировать
    # --- Конец нового ---


    def seek_delta(self, delta_sec):
        self.controller.seek_delta(delta_sec)
        self.show_current_frame()
        self.update_ui()
        self.positionChanged.emit(self.controller.current_time_sec)
        if self.controller.playing:
            self.toggle_play() # Останавливаем при перемотке

    def keyPressEvent(self, event):
        key = event.key()
        text = event.text().lower()
        if key == Qt.Key_Space:
            self.toggle_play()
        elif key == Qt.Key_Right:
            modifiers = event.modifiers()
            if modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
                self.seek_delta(300)
            elif modifiers == Qt.ControlModifier:
                self.seek_delta(5)
            elif modifiers == Qt.ShiftModifier:
                self.seek_delta(30)
            else:
                self.seek_delta(0.5)
        elif key == Qt.Key_Left:
            modifiers = event.modifiers()
            if modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
                self.seek_delta(-300)
            elif modifiers == Qt.ControlModifier:
                self.seek_delta(-5)
            elif modifiers == Qt.ShiftModifier:
                self.seek_delta(-30)
            else:
                self.seek_delta(-0.5)
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            try:
                idx = SPEED_VALUES.index(self.controller.speed)
                if idx < len(SPEED_VALUES) - 1:
                    self.set_speed(SPEED_VALUES[idx + 1])
            except ValueError:
                self.set_speed(1.0)
        elif key == Qt.Key_Minus:
            try:
                idx = SPEED_VALUES.index(self.controller.speed)
                if idx > 0:
                    self.set_speed(SPEED_VALUES[idx - 1])
            except ValueError:
                self.set_speed(1.0)
        elif key == Qt.Key_0:
            self.set_speed(1.0)
        elif text == '~' or text == '`' or text == 'Ё'or text == 'ё':
            self.toggle_reverse()
            # --- НОВОЕ: Проверка клавиш '8' и '9' ---
        elif event.key() == Qt.Key_8:
            print("[DEBUG VideoPlayer] Нажата клавиша '8'.")
            # Эмит сигнала о запросе "прилипания" к предыдущему элементу
            self.snapToPreviousRequested.emit()
            return # Выходим, чтобы не вызывать super().keyPressEvent()
        elif event.key() == Qt.Key_9:
            print("[DEBUG VideoPlayer] Нажата клавиша '9'.")
            # Эмит сигнала о запросе "прилипания" к следующему элементу
            self.snapToNextRequested.emit()
            return # Выходим, чтобы не вызывать super().keyPressEvent()
        # --- КОНЕЦ НОВОГО ---


        # --- Новое: обработка клавиши '1' ---
        elif key == Qt.Key_1:
            # Сигнализируем, что нажата горячая клавиша '1'
            self.pointHotkeyPressed.emit()
        # --- Конец нового ---
        else:
      # Игнорируем другие клавиши, чтобы они могли быть обработаны другими виджетами
            # (например, кнопкой set_point_button в SegmentEditor, если бы она могла получить событие)
            # Однако, из-за текущей логики, событие вряд ли дойдет до неё напрямую.
            event.ignore() # <-- Опционально, но обычно правильно игнорировать необработанные клавиши
        # super().keyPressEvent(event) # <-- Не вызываем, так как обрабатываем или игнорируем

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.video_label.geometry().contains(event.pos()):
                self.toggle_play()
        super().mousePressEvent(event)

    def get_current_time(self):
        return self.controller.get_current_time()

    def get_total_duration(self):
        return self.controller.get_total_duration()

    def is_playing(self):
        return self.controller.is_playing()

    def cleanup(self):
        self.timer.stop()
        self.controller.cleanup()
# Конец содержимого файла: ..\4.0\1.0\ui\video_player_widget.py


