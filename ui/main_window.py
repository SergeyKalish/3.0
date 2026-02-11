# ui/main_window.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMenuBar, QStatusBar, QFileDialog,
    QMessageBox, QLabel, QMenu, QSizePolicy, QPushButton, QCheckBox
)
from PyQt5.QtCore import Qt, QSettings, QEvent, QTimer # Добавлен QTimer
from PyQt5.QtGui import QKeySequence, QFont # Добавлен QKeySequence для горячих клавиш, QFont для стилей
import os
import json
from model.project import Project, GenericLabel, CalculatedRange # Импортируем нужные классы
from ui.video_player_widget import VideoPlayerWidget
from utils.helpers import load_project_from_file, save_project_to_file
# --- Новые импорты ---
from ui.universal_label_editor import UniversalLabelEditor
from ui.labels_tree_widget import LabelsTreeWidget
from modules.smart import SMARTProcessor # <-- Новый импорт
from ui.protocol_validation_widget import ProtocolValidationWidget
# - Новые импорты -
from ui.timeline_widget import TimelineWidget # Импортируем TimelineWidget
# - Конец новых импортов -
from ui.lineup_module_widget import LineupModuleWidget
# --- Конец новых импортов ---
from typing import Dict, Any
from PyQt5.QtWidgets import QStackedWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hockey Tagger 4.0")
        # self.setGeometry(100, 100, 1600, 900) # Убираем фиксированный размер окна
        # Хранение пути проекта
        self.project_file_path: str = ""
        # Недавние проекты
        self.recent_projects: list = []
        self.max_recent_projects = 5
        # Настройки
        self.settings = QSettings("HockeyTagger", "HockeyTagger4.0")
        # Загрузка недавних проектов из настроек при запуске
        self.load_recent_projects_from_settings()
        # Модель данных
        self.project: Project = Project() # Теперь это Project 4.0
        # Путь к видео
        self.current_video_path: str = ""
        # UI компоненты
        self.video_player_widget = VideoPlayerWidget()
        # --- Новые компоненты ---
        # self.universal_label_editor_widget = UniversalLabelEditor()
        self.universal_label_editor_widget = UniversalLabelEditor(video_player_widget=self.video_player_widget) # Новая строка
        # R1 и R2
        #self.R1_widget = QWidget()
        #self.R1_widget.setStyleSheet("background-color: lightgreen;") # Пример стиля для R1
        # Создаём стек для R1
        self.stacked_r1 = QStackedWidget()

        # Виджет валидации протокола
        self.protocol_validation_widget = ProtocolValidationWidget(parent=self)
        self.stacked_r1.addWidget(self.protocol_validation_widget)  # index 0

        # # Заглушка для модуля "Смена" (пока пустой)
        # self.lineup_module_stub = QWidget()
        # self.lineup_module_stub.setStyleSheet("background-color: lightblue;")  # для видимости
        # self.stacked_r1.addWidget(self.lineup_module_stub)  # index 1
        # --- Создание LineupModuleWidget ---
        self.lineup_module_widget = LineupModuleWidget()
        self.lineup_module_widget.set_main_window(self)
        self.lineup_module_widget._save_project_callback = self._save_project_callback

        self.stacked_r1.addWidget(self.lineup_module_widget)
        # --- Конец создания LineupModuleWidget ---

        # Устанавливаем R1
        self.R1_widget = self.stacked_r1


        self.R2_widget = QWidget()
        self.R2_widget.setStyleSheet("background-color: lightyellow;") # Пример стиля для R2
        # LabelsTreeWidget
        self.labels_tree_widget = LabelsTreeWidget()
        # SMART
        self.smart_processor = SMARTProcessor()
        self.run_smart_button = QPushButton("Запустить SMART")
        self.auto_smart_checkbox = QCheckBox("Автоматический вызов SMART")
        # --- Конец новых компонентов ---
        self.init_ui()
        self.setup_connections()
        # Развертываем окно на весь экран
        self.showMaximized()
        # Запускаем таймер для установки фиксированного размера после развертывания
        QTimer.singleShot(100, self.set_fixed_size_after_maximize)
        self._active_protocol_event = None  # ← новое поле

    # --- НОВОЕ: Вспомогательный метод для обновления активного диапазона TimelineWidget ---
    def _update_timeline_active_range(self, range_name: str):
        """Обновляет активный диапазон на TimelineWidget на основе выбранного имени в range_selector."""
        if not self.project or not self.project.match:
            print("[DEBUG] _update_timeline_active_range: Нет активного проекта.")
            return

        # Найти выбранный CalculatedRange по имени
        selected_range = None
        for cr in self.project.match.calculated_ranges:
            if cr.name == range_name:
                selected_range = cr
                break

        if selected_range:
            # Обновить TimelineWidget с новым активным диапазоном
            if self.timeline_widget:
                 print(f"[DEBUG] _update_timeline_active_range: Обновление диапазона на {range_name} ({selected_range.start_time:.3f} - {selected_range.end_time:.3f})")
                 self.timeline_widget.update_active_range(selected_range.start_time, selected_range.end_time, selected_range.name)
        else:
            # Если имя не найдено в calculated_ranges (например, "Всё видео" до первого SMART),
            # можно установить глобальный диапазон (0, total_duration), если он известен.
            # Пока просто выведем сообщение.
            print(f"[DEBUG] _update_timeline_active_range: Диапазон '{range_name}' не найден в calculated_ranges.")
            # Попробуем найти диапазон с label_type "Всё видео", если имя не совпадает
            if range_name == "Всё видео":
                 all_video_range = next((cr for cr in self.project.match.calculated_ranges if cr.label_type == "Всё видео"), None)
                 if all_video_range:
                      if self.timeline_widget:
                           print(f"[DEBUG] _update_timeline_active_range: Обновление на 'Всё видео' ({all_video_range.start_time:.3f} - {all_video_range.end_time:.3f})")
                           self.timeline_widget.update_active_range(all_video_range.start_time, all_video_range.end_time, all_video_range.name)
            # Или, если точная логика неизвестна, можно установить (0, 0) или пропустить.
            # В реальном проекте, "Всё видео" всегда должен быть в calculated_ranges после run_smart_analysis.
    # --- Конец НОВОГО ---

    def load_protocol_file(self):
        """
        Загружает JSON-файл протокола матча и сохраняет ВСЕ данные в match.
        """
        if not self.project_file_path:
            QMessageBox.warning(self, "Предупреждение", "Сначала откройте или создайте проект.")
            return

        protocol_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл протокола матча", "", "JSON (*.json *.txt)"
        )
        if not protocol_path:
            return

        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                protocol_data = json.load(f)

            # --- Сохраняем ВСЁ из протокола в match ---
            self.project.match.match_id = protocol_data.get("match_id")
            self.project.match.teams = protocol_data.get("teams", {})
            self.project.match.rosters = protocol_data.get("rosters", {})
            self.project.match.events = protocol_data.get("events", [])
            # -----------------------------------------

            # --- Сохранение проекта ---
            save_project_to_file(self.project, self.project_file_path)

            # --- Обновляем таблицу событий в R1 ---
            self.protocol_validation_widget.set_events(self.project.match.events)
            self._update_lineup_widget_with_team_roster()

            self.status_label.setText(f"Протокол загружен из: {os.path.basename(protocol_path)}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить протокол:\n{str(e)}")


    def set_fixed_size_after_maximize(self):
        """Устанавливает фиксированный размер окна после его развертывания."""
        size = self.size()
        self.setFixedSize(size)
        # print(f"MainWindow size set to fixed: {size}") # Для отладки, можно удалить

        # --- Новый метод для обновления заголовка окна ---
    def update_window_title(self):
        """
        Обновляет заголовок главного окна, добавляя имя файла проекта.
        Если проект не сохранён (project_file_path пуст), отображает только базовое имя.
        """
        base_title = "Hockey Tagger 4.0"
        if self.project_file_path:
            # Извлекаем имя файла из пути
            project_name = os.path.basename(self.project_file_path)
            full_title = f"{base_title} - {project_name}"
        else:
            # Если проект не сохранён, показываем только базовое имя
            full_title = base_title
        self.setWindowTitle(full_title)
    # --- Конец нового метода ---    

    def load_recent_projects_from_settings(self):
        size = self.settings.beginReadArray("recentProjects")
        self.recent_projects = []
        for i in range(size):
            self.settings.setArrayIndex(i)
            path = self.settings.value("path", "")
            if path and os.path.exists(path):
                 self.recent_projects.append(path)
        self.settings.endArray()
        self.recent_projects = self.recent_projects[:self.max_recent_projects]

    def init_ui(self):
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # layout = QVBoxLayout(central_widget) # Убираем старый вертикальный макет
        layout = QHBoxLayout(central_widget) # Заменяем на горизонтальный макет
        # Создаём контейнер для левой части
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container) # Вертикальный макет для левой части
        # Добавляем VideoPlayerWidget в левый контейнер
        left_layout.addWidget(self.video_player_widget)

        # --- Изменение: Создаём bottom_left_widget с вертикальным макетом ---
        bottom_left_widget = QWidget()
        bottom_left_layout = QVBoxLayout(bottom_left_widget) # Вертикальный макет

    
        # --- НОВОЕ: Создаём TimelineWidget ---
        self.timeline_widget = TimelineWidget() # Заменяем timeline_placeholder

        # 1. Добавляем TimelineWidget (пока заглушка)
        # bottom_left_layout.addWidget(self.timeline_placeholder) # Старая строка
        bottom_left_layout.addWidget(self.timeline_widget) # <-- ИЗМЕНЕНО: Добавляем настоящий TimelineWidget

        # 2. Добавляем UniversalLabelEditor
        # У него теперь есть встроенный range_selector
        bottom_left_layout.addWidget(self.universal_label_editor_widget)

        # Устанавливаем минимальную высоту для bottom_left_widget
        bottom_left_widget.setMinimumHeight(200)
        bottom_left_widget.setStyleSheet("background-color: lightgray;") # Пример стиля для видимости
        # Добавляем bottom_left_widget в вертикальный макет left_container
        left_layout.addWidget(bottom_left_widget)
        # ---

        # --- Изменение: Создаём right_widget с горизонтальным макетом и делим на R1 и R2 ---
        right_widget = QWidget()
        # right_widget.setStyleSheet("background-color: lightblue;") # Убираем светло-голубой цвет
        right_widget.setStyleSheet("background-color: lightgray;") # Возвращаем серый цвет
        right_layout = QHBoxLayout(right_widget) # Горизонтальный макет для right_widget

        # Добавляем R1 и R2 в горизонтальный макет right_widget
        right_layout.addWidget(self.R1_widget) # Левая колонка (R1)
        right_layout.addWidget(self.R2_widget) # Правая колонка (R2)
        # Устанавливаем соотношение ширины R1 и R2: 1:1
        right_layout.setStretch(0, 1) # R1
        right_layout.setStretch(1, 1) # R2

        # --- Новое: Добавляем LabelsTreeWidget и элементы SMART в R2_widget ---
        # Создаём QVBoxLayout для R2_widget
        R2_layout = QVBoxLayout(self.R2_widget)
        R2_layout.addWidget(self.run_smart_button)
        R2_layout.addWidget(self.auto_smart_checkbox)
        R2_layout.addWidget(self.labels_tree_widget) # LabelsTreeWidget внизу R2
        # --- Конец нового ---
        # --- Конец изменения (right_widget) ---

        # --- Новое: Устанавливаем политику размера для right_widget ---
        # Чтобы right_widget растягивался по высоте, совпадая с высотой left_container
        right_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # ---

        # Добавляем левый и правый контейнеры в основной горизонтальный макет
        layout.addWidget(left_container)
        layout.addWidget(right_widget)
        # Устанавливаем соотношение ширины: левая часть (включая VideoPlayerWidget) - 1 часть, правая часть - 3 части
        layout.setStretch(0, 1) # Левая часть
        layout.setStretch(1, 3) # Правая часть
        # Меню
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)
        file_menu = menubar.addMenu('Файл')
        file_menu.addAction('Создать новый проект...', self.create_new_project)
        file_menu.addAction('Открыть проект...', self.open_project)
        # Подменю недавних проектов
        self.recent_projects_menu = QMenu('Недавние проекты', self)
        file_menu.addMenu(self.recent_projects_menu)
        self.update_recent_projects_menu()
        # Связываем "Сохранить как..." с методом
        file_menu.addAction('Сохранить как...', self.save_project_as, 'Ctrl+Shift+S')
        # После пункта 'Сохранить как...'
        file_menu.addAction('Загрузить протокол матча...', self.load_protocol_file)
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Готов к работе")
        self.status_bar.addWidget(self.status_label)

    def setup_connections(self):
        # Сигналы плеера
        self.video_player_widget.videoLoaded.connect(self.on_video_loaded)
        # --- Новые соединения ---
        # 1. Сигнал от VideoPlayerWidget о нажатии '1' -> обработчик в MainWindow
        self.video_player_widget.pointHotkeyPressed.connect(self.handle_point_hotkey_pressed)
           # --- НОВОЕ: Подключения для '8' и '9' ---
        # 1.1. Сигнал от VideoPlayerWidget о нажатии '8' -> обработчик в MainWindow
        self.video_player_widget.snapToPreviousRequested.connect(self.handle_snap_to_previous)
        # 1.2. Сигнал от VideoPlayerWidget о нажатии '9' -> обработчик в MainWindow
        self.video_player_widget.snapToNextRequested.connect(self.handle_snap_to_next)
        # --- КОНЕЦ НОВОГО ---
        # 2. Сигнал от UniversalLabelEditor о запросе метки -> обработчик в MainWindow
        self.universal_label_editor_widget.labelSet.connect(self.on_label_requested_from_editor)
        # 3. Изменение выбора в range_selector (теперь внутри UniversalLabelEditor) -> обработчик в MainWindow
        # Получаем QComboBox из UniversalLabelEditor
        range_selector = self.universal_label_editor_widget.get_range_selector()
        range_selector.currentTextChanged.connect(self.on_range_selection_changed)
        # 4. Сигнал от LabelsTreeWidget о выборе метки -> переход к времени в плеере
        self.labels_tree_widget.labelSelected.connect(self.go_to_time)
        # 5. Сигнал от кнопки SMART -> вызов SMART
        self.run_smart_button.clicked.connect(self.run_smart_analysis)
        # 6. Сигнал от чекбокса SMART -> обновление состояния
        self.auto_smart_checkbox.stateChanged.connect(self.on_auto_smart_toggled)
        # 7. Сигнал от LabelsTreeWidget о выборе диапазона для воспроизведения -> переключение в плеере
        self.labels_tree_widget.rangeSelectedForPlayback.connect(self._select_range_in_selector_and_playback)

        # --- НОВОЕ: Подключения для TimelineWidget ---
        # 3.1. Сигнал от TimelineWidget для навигации плеера
        self.timeline_widget.globalTimeRequested.connect(self.go_to_time)
        # 3.2. Сигнал от VideoPlayerWidget для обновления текущего времени на TimelineWidget
        self.video_player_widget.positionChanged.connect(self.timeline_widget.update_current_time)
        self.video_player_widget.positionChanged.connect(self._update_lineup_widget_state)
        # 3.3. Сигнал от range_selector для обновления активного диапазона на TimelineWidget (Вариант 3)
        range_selector.currentTextChanged.connect(self._update_timeline_active_range)

        # Подключаем сигнал изменения типа метки
        label_group = self.universal_label_editor_widget.label_type_group
        label_group.buttonToggled.connect(self.on_label_type_toggled)

    def _update_lineup_widget_state(self):
        """
        Обновляет состояние LineupModuleWidget на основе текущего времени плеера
        и calculated_ranges проекта.
        """
        # Получить текущее global_time от self.video_player_widget
        # Используем метод, который уже применяется в on_label_requested_from_editor
        global_time = self.video_player_widget.get_current_time()

        # Получить calculated_ranges от self.project.match
        calculated_ranges = self.project.match.calculated_ranges
        generic_labels = self.project.match.generic_labels # <-- Получаем generic_labels
        # Передаём generic_labels в метод LineupModuleWidget
        self.lineup_module_widget.set_current_global_time_and_calculated_ranges(global_time, calculated_ranges, generic_labels)

        # Получить our_team_key (повторно определить, как в _update_lineup_widget_with_team_roster)
        our_team_key = None
        if hasattr(self.project, 'match') and hasattr(self.project.match, 'teams'):
            for key, team_name in self.project.match.teams.items():
                if key in ["f-team", "s-team"] and team_name == "Созвездие 2014":
                    our_team_key = key
                    break

        # Обновить ключ нашей команды в LineupModuleWidget
        self.lineup_module_widget.set_our_team_key(our_team_key) # Даже если None
        #отладка gamemode НАЧАЛО
        active_game_mode = None
        for cr in self.project.match.calculated_ranges:
            if cr.label_type == "game_mode" and cr.start_time <= global_time < cr.end_time:
                active_game_mode = cr
                break
        if active_game_mode:
            print(f"[DEBUG MW] Active game_mode at {global_time}: {active_game_mode.name}, penalties: {active_game_mode.context.get('active_penalties', [])}")
        #отладка gamemode КОНЕЦ
        
        # Вызвать self.lineup_module_widget.set_current_global_time_and_calculated_ranges(global_time, calculated_ranges)
        #self.lineup_module_widget.set_current_global_time_and_calculated_ranges(global_time, calculated_ranges, generic_labels)

        #print(f"[DEBUG MW] Updating LUM at {global_time}, our team key: {our_team_key}")

    def on_label_type_toggled(self, button, checked):
        """Автоматически переключает R1 при выборе типа метки (только если чекбокс активирован)."""
        if not checked:
            return

        label_type = button.text()
        if label_type in ("Гол", "Удаление"):
            self.stacked_r1.setCurrentWidget(self.protocol_validation_widget)
        elif label_type == "Смена":
            self.stacked_r1.setCurrentWidget(self.lineup_module_widget)
        # Для "Сегмент", "Пауза" — НЕ МЕНЯЕМ R1 (остаётся как есть)


    # --- Новые методы ---
    def handle_point_hotkey_pressed(self):
        """Обработчик сигнала от VideoPlayerWidget о нажатии клавиши '1'."""
        # Передаём сигнал в UniversalLabelEditor
        self.universal_label_editor_widget.handle_hotkey_pressed()

        # --- НОВОЕ: Обработчики для '8' и '9' ---
    def handle_snap_to_previous(self):
        """Обработчик сигнала от VideoPlayerWidget о нажатии клавиши '8'."""
        print("[DEBUG MainWindow] handle_snap_to_previous вызван.")
        # Вызываем МЕТОД TimelineWidget (_find_closest_element_time) для поиска элемента слева
        # и получения времени
        # TimelineWidget использует self.current_global_time как точку отсчёта
        target_time = self.timeline_widget._find_closest_element_time("left") # Вызов напрямую
        if target_time is not None:
            print(f"[DEBUG MainWindow] handle_snap_to_previous: Переход к времени {target_time:.3f}s.")
            self.go_to_time(target_time)
        else:
            print("[DEBUG MainWindow] handle_snap_to_previous: Элемент слева не найден.")

    def handle_snap_to_next(self):
        """Обработчик сигнала от VideoPlayerWidget о нажатии клавиши '9'."""
        print("[DEBUG MainWindow] handle_snap_to_next вызван.")
        # Вызываем МЕТОД TimelineWidget (_find_closest_element_time) для поиска элемента справа
        # и получения времени
        # TimelineWidget использует self.current_global_time как точку отсчёта
        target_time = self.timeline_widget._find_closest_element_time("right") # Вызов напрямую
        if target_time is not None:
            print(f"[DEBUG MainWindow] handle_snap_to_next: Переход к времени {target_time:.3f}s.")
            self.go_to_time(target_time)
        else:
            print("[DEBUG MainWindow] handle_snap_to_next: Элемент справа не найден.")
    # --- Конец НОВОГО ---
    
    def on_label_requested_from_editor(self, label_type: str):
        """
        Обработчик сигнала от UniversalLabelEditor о запросе установки метки.
        Создаёт GenericLabel, добавляет в проект, сохраняет, обновляет UI.
        """
        from model.project import GenericLabel
        global_time = self.video_player_widget.get_current_time()

        # --- DEBUG: проверим, есть ли активное событие из ProtocolValidationWidget ---
        active_event = None
        if hasattr(self, 'protocol_validation_widget'):
            active_event = self._active_protocol_event
        print(f"[DEBUG] label_type='{label_type}', active_event exists: {active_event is not None}")

        # --- НОВОЕ: Обработка метки "Смена" ---
        if label_type == "Смена":
            # 1. Получить ID отмеченных игроков из LineupModuleWidget
            selected_player_ids = set(self.lineup_module_widget.get_selected_player_ids())

            # 2. Определить, какая команда - наша ("Созвездие 2014")
            our_team_key = None
            if hasattr(self.project, 'match') and hasattr(self.project.match, 'teams'):
                for key, team_name in self.project.match.teams.items():
                    if key in ["f-team", "s-team"] and team_name == "Созвездие 2014":
                        our_team_key = key
                        break

            # 3. Извлечь полные данные игроков из rosters нашей команды
            players_on_ice_data = []
            if our_team_key and hasattr(self.project, 'match') and hasattr(self.project.match, 'rosters'):
                our_team_roster = self.project.match.rosters.get(our_team_key, [])
                for player_data in our_team_roster:
                    # Сравниваем id_fhm игрока с отмеченными ID
                    if player_data.get("id_fhm") in selected_player_ids:
                        # Добавляем словарь с id_fhm и name
                        players_on_ice_data.append({
                            "id_fhm": player_data.get("id_fhm"),
                            "name": player_data.get("name") # Сохраняем оригинальное "Имя Фамилия"
                        })
                        # Убираем ID из множества, чтобы отследить, если какой-то ID не найден
                        selected_player_ids.discard(player_data.get("id_fhm"))

                # (Опционально) Проверить, остались ли ID, не найденные в rosters
                if selected_player_ids:
                    print(f"[WARNING] Игроки с ID {selected_player_ids} отмечены, но не найдены в rosters команды {our_team_key}.")

            # 4. Подготовить context для метки "Смена"
            context = {"players_on_ice": players_on_ice_data}

            # 5. Создать метку GenericLabel
            #from model.project import GenericLabel
            import uuid
            new_label = GenericLabel(
                id=str(uuid.uuid4()),
                label_type=label_type,
                global_time=global_time,
                context=context
            )
            self.project.match.generic_labels.append(new_label)

            print(f"[DEBUG] Создана метка 'Смена' на {new_label.global_time:.2f} с {len(players_on_ice_data)} игроками: {[p['name'] for p in players_on_ice_data]}")

            # 6. Сохранить проект
            if self.project_file_path:
                try:
                    #from utils.project_utils import save_project_to_file
                    save_project_to_file(self.project, self.project_file_path)
                    self.status_label.setText(f"Метка '{label_type}' добавлена в {global_time:.1f}s. Проект сохранён.")
                except Exception as e:
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Предупреждение", f"Не удалось сохранить проект: {str(e)}")
            else:
                self.status_label.setText(f"Метка '{label_type}' добавлена в {global_time:.1f}s. Нет пути для сохранения.")

            # 7. Обновить UI
            # Передаём все шесть аргументов в update_tree
            self.labels_tree_widget.update_tree(
                self.project.match.generic_labels,
                self.project.match.calculated_ranges,
                self.project.match.generic_labels, # generic_labels_for_timeline
                self.project.match.calculated_ranges, # calculated_ranges_for_timeline
                self.video_player_widget,
                self._save_project_callback
            )

            # 8. Вызвать SMART, если включён
            if self.auto_smart_checkbox.isChecked():
                self.run_smart_analysis()

            # 9. ВАЖНО: Завершаем метод, чтобы не выполнить оставшуюся логику
            return

        # --- КОНЕЦ НОВОГО ---

        # --- Оригинальная логика для других меток (Гол, Удаление и т.д.) ---
        context = {}
        if label_type in ("Гол", "Удаление") and active_event:
            print(f"[DEBUG] Filling context from event: {active_event.get('player_name', 'N/A')}")
            if label_type == "Гол":
                context = {
                    "team": active_event.get("team"),
                    "player_name": active_event.get("player_name"),
                    "player_id_fhm": active_event.get("player_id_fhm"),
                    "f-pass": active_event.get("f-pass"),
                    "f-pass_id_fhm": active_event.get("f-pass_id_fhm"),
                    "s-pass": active_event.get("s-pass"),
                    "s-pass_id_fhm": active_event.get("s-pass_id_fhm"),
                    "event_time_sec": active_event.get("time_sec")
                }
            elif label_type == "Удаление":
                context = {
                    "team": active_event.get("team"),
                    "player_name": active_event.get("player_name"),
                    "player_id_fhm": active_event.get("player_id_fhm"),
                    "violation_type": active_event.get("violation_type"),
                    "start_time_sec": active_event.get("start_time_sec"),
                    "end_time_sec": active_event.get("end_time_sec"),
                    "event_time_sec": active_event.get("start_time_sec")
                }
            # Очищаем после использования
            self.protocol_validation_widget._active_protocol_event = None
        else:
            print("[DEBUG] No active event or wrong label type — context remains empty.")

        # Создание метки для всех остальных типов
        new_label = GenericLabel(label_type=label_type, global_time=global_time, context=context)
        self.project.match.generic_labels.append(new_label)

        # Сохранение
        if self.project_file_path:
            try:
                #from utils.project_utils import save_project_to_file
                save_project_to_file(self.project, self.project_file_path)
                self.status_label.setText(f"Метка '{label_type}' добавлена в {global_time:.1f}s. Проект сохранён.")
            except Exception as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Предупреждение", f"Не удалось сохранить проект: {str(e)}")
        else:
            self.status_label.setText(f"Метка '{label_type}' добавлена в {global_time:.1f}s. Нет пути для сохранения.")

        # Обновление UI (для остальных типов)
        self.labels_tree_widget.update_tree(
            self.project.match.generic_labels,
            self.project.match.calculated_ranges,
            self.project.match.generic_labels, # generic_labels_for_timeline
            self.project.match.calculated_ranges, # calculated_ranges_for_timeline
            self.video_player_widget,
            self._save_project_callback
        )

        # Вызов SMART (для остальных типов)
        if self.auto_smart_checkbox.isChecked():
            self.run_smart_analysis()


    def on_range_selection_changed(self, text: str):
        """Обработчик изменения выбора в range_selector."""
        # Найти соответствующий calculated_range в self.project.match.calculated_ranges
        for calc_range in self.project.match.calculated_ranges:
            if calc_range.name == text:
                # Установить границы "схлопывания"
                self.video_player_widget.set_navigation_bounds(calc_range.start_time, calc_range.end_time)
                self.status_label.setText(f"Режим: {text}")
                break # Нашли и применили, выходим из цикла
        # Если диапазон не найден (например, "Всё видео" не был в calculated_ranges до SMART),
        # цикл завершится, и режим не изменится. Это маловероятно, так как SMART всегда добавляет "Всё видео".

    # --- Конец новых методов ---

    def update_recent_projects_menu(self):
        self.recent_projects_menu.clear()
        for path in self.recent_projects:
            action = self.recent_projects_menu.addAction(path)
            action.triggered.connect(lambda checked=False, p=path: self.open_project_from_path(p))
        # Сохранение в настройки
        self.settings.beginWriteArray("recentProjects")
        for i, path in enumerate(self.recent_projects):
            self.settings.setArrayIndex(i)
            self.settings.setValue("path", path)
        self.settings.endArray()

    def open_project_from_path(self, path: str):
        if os.path.exists(path):
            self.load_project_from_path(path)
        else:
            QMessageBox.warning(self, "Предупреждение", f"Файл проекта не найден:\n{path}")
            if path in self.recent_projects:
                self.recent_projects.remove(path)
                self.update_recent_projects_menu()
        #добавил с целью загрузить диапазон Все видео в timeline_widget при открытии нового проекта
        all_video_range = next((cr for cr in self.project.match.calculated_ranges if cr.label_type == "Всё видео"), None)
        if all_video_range:
            if self.timeline_widget:
                 print(f"[DEBUG] MainWindow.open_project: Установка активного диапазона 'Всё видео' ({all_video_range.start_time:.3f} - {all_video_range.end_time:.3f}) для TimelineWidget.")
                 # Это вызовет redraw и установит правильный масштаб
                 self.timeline_widget.update_active_range(all_video_range.start_time, all_video_range.end_time, all_video_range.name)

    def create_new_project(self):
        video_path, _ = QFileDialog.getOpenFileName(self, "Выберите видеофайл", "", "Видео (*.mp4 *.avi *.mov)")
        if not video_path:
            return # Пользователь отменил выбор видео
        # Запрос имени файла проекта через "Сохранить как..."
        project_path, _ = QFileDialog.getSaveFileName(self, "Сохранить проект как", "", "Проект (*.hkt)")
        if not project_path:
            return # Пользователь отменил выбор файла проекта
        # Инициализация нового проекта
        self.project = Project() # Создаём проект версии 4.0
        self.project.video_path = video_path
        self.current_video_path = video_path
        # Сохраняем путь проекта
        self.project_file_path = project_path
        # --- Новое: Обновление заголовка окна ---
        self.update_window_title()
        # --- Конец нового ---
        # Загрузка видео в плеер
        self.video_player_widget.load_video(video_path)
        self.status_label.setText(f"Новый проект, видео: {os.path.basename(video_path)}")
        # --- Новое: Запуск SMART после загрузки видео ---
        # Это создаст CalculatedRange "Всё видео" и, возможно, другие диапазоны на основе пустого списка меток (или базовых правил)
        self.run_smart_analysis()
        # --- Конец нового ---
        
        # Добавление в недавние
        self.add_to_recent_projects(project_path)
        # Сохранение проекта в указанный файл
        try:
            save_project_to_file(self.project, self.project_file_path)
            self.status_label.setText(f"Проект сохранён: {os.path.basename(self.project_file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект:\n{str(e)}")
            # Если не удалось сохранить, путь проекта нужно сбросить
            self.project_file_path = ""
            # Видео останется загруженным, но проект не будет привязан к файлу

    def open_project(self):
        project_path, _ = QFileDialog.getOpenFileName(self, "Откройте проект", "", "Проект (*.hkt)")
        if project_path:
            self.load_project_from_path(project_path)

    def load_project_from_path(self, project_path: str):
        try:
            self.project = load_project_from_file(project_path)       
            self.project_file_path = project_path
            # --- Новое: Обновление заголовка окна ---
            self.update_window_title()
            # --- Конец нового ---
            self.current_video_path = self.project.video_path
            if self.current_video_path and os.path.exists(self.current_video_path):
                self.video_player_widget.load_video(self.current_video_path)
                self.status_label.setText(f"Открыт проект: {os.path.basename(project_path)}")
                self.add_to_recent_projects(project_path)
                # --- Новое: Запуск SMART после загрузки видео ---
                # Это обновит calculated_ranges, включая "Всё видео", независимо от того, был ли он в старом проекте
                self.run_smart_analysis()
                # --- Конец нового ---
                self._update_lineup_widget_with_team_roster()
                # --- Новое: инициализация ProtocolValidationWidget ---
                self._init_protocol_validation_widget()
                # --- Конец нового ---
            else:
                QMessageBox.critical(self, "Ошибка", f"Видеофайл не найден: {self.current_video_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить проект:\n{str(e)}")

    def _update_lineup_widget_with_team_roster(self):
        """
        Извлекает состав нашей команды ("Созвездие 2014") из self.project.match.rosters
        и передаёт его в self.lineup_module_widget.
        """
        # Проверяем, существуют ли необходимые данные
        if not hasattr(self.project, 'match') or not hasattr(self.project.match, 'rosters') or not hasattr(self.project.match, 'teams'):
            print("[DEBUG] _update_lineup_widget_with_team_roster: rosters или teams отсутствуют в project.match.")
            self.lineup_module_widget.set_team_roster([]) # Очищаем виджет, если данных нет
            return

        # Определяем, какая команда - наша ("Созвездие 2014")
        our_team_key = None
        for key, team_name in self.project.match.teams.items():
            # Проверяем только ключи, похожие на "f-team", "s-team"
            if key in ["f-team", "s-team"] and team_name == "Созвездие 2014":
                our_team_key = key
                break

        if our_team_key is None:
            print(f"[DEBUG] _update_lineup_widget_with_team_roster: Команда 'Созвездие 2014' не найдена в teams: {self.project.match.teams}")
            self.lineup_module_widget.set_team_roster([]) # Очищаем виджет, если команда не найдена
            # --- НОВОЕ: Убедимся, что виджет знает, что наша команда неопределена ---
            self.lineup_module_widget.set_our_team_key(None)
            # --- КОНЕЦ НОВОГО ---
            return

        # Извлекаем состав нашей команды
        our_team_roster = self.project.match.rosters.get(our_team_key, [])
        
        # Передаём состав в LineupModuleWidget
        self.lineup_module_widget.set_team_roster(our_team_roster)
        # --- НОВОЕ: Передаём ключ нашей команды в LineupModuleWidget ---
        self.lineup_module_widget.set_our_team_key(our_team_key)
        print(f"[DEBUG MW] Our team key determined: {our_team_key}")
        # --- КОНЕЦ НОВОГО ---

        print(f"[DEBUG] _update_lineup_widget_with_team_roster: Установлен состав для {our_team_key}, {len(our_team_roster)} игроков.")


    def add_to_recent_projects(self, path: str):
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:self.max_recent_projects]
        self.update_recent_projects_menu() # Вызовет сохранение3.0 (autosave 21-11-2025-11-06).zip

    # --- Новый метод для переключения авто-SMART ---
    def on_auto_smart_toggled(self, state):
        """Обработчик изменения состояния auto_smart_checkbox."""
        if state == Qt.Checked:
            self.status_label.setText("Автоматический вызов SMART включён.")
            # Запускаем SMART при включении, чтобы обновить интерфейс на случай, если метки уже были
            self.run_smart_analysis()
        else:
            self.status_label.setText("Автоматический вызов SMART отключён.")
    # --- Конец нового метода ---

    # --- Новый вспомогательный метод ---
    def _update_range_selector(self):
        """Обновляет QComboBox range_selector на основе calculated_ranges в проекте."""
        # Получаем QComboBox из UniversalLabelEditor
        range_selector = self.universal_label_editor_widget.get_range_selector()
        # Блокируем сигнал, чтобы не срабатывал обработчик при программном изменении
        range_selector.blockSignals(True)
        # Очищаем и добавляем имена calculated_ranges
        range_selector.clear()
        # --- Новое: Фильтрация calculated_ranges перед добавлением в QComboBox ---
        # Определяем label_type, которые НЕ нужно отображать в range_selector
        # (например, служебные диапазоны, используемые только для внутренней логики SMART)
        excluded_label_types = {"Пауза", "ЧИИ_СУММА", "Удаление", "game_mode", "Счёт"} # Добавьте сюда другие типы, если нужно
        # Добавляем имена calculated_ranges, НЕ входящих в исключения
        for calc_range in self.project.match.calculated_ranges:
            if calc_range.label_type not in excluded_label_types:
                range_selector.addItem(calc_range.name)
        # --- Конец нового ---
        # Разблокируем сигнал
        range_selector.blockSignals(False)
    # --- Конец нового вспомогательного метода ---

    # Метод для "Сохранить как..." (всегда диалог)
    def save_project_as(self):
        """Сохраняет проект, открывая диалог 'Сохранить как...', независимо от текущего пути."""
        # Диалог всегда открывается, начальный путь - текущий project_file_path
        initial_path = self.project_file_path or ""
        project_path, _ = QFileDialog.getSaveFileName(self, "Сохранить проект как", initial_path, "Проект (*.hkt)")
        if not project_path:
            return # Пользователь отменил, выходим
        # Обновляем путь проекта на выбранный
        self.project_file_path = project_path
         # --- Новое: Обновление заголовка окна ---
        self.update_window_title()
        # --- Конец нового ---
        try:
            save_project_to_file(self.project, self.project_file_path)
            self.status_label.setText(f"Проект сохранён: {os.path.basename(self.project_file_path)}")
            # При сохранении по новому пути, добавляем его в недавние
            self.add_to_recent_projects(self.project_file_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект:\n{str(e)}")

    # --- Новый метод для навигации по времени ---
    def go_to_time(self, global_time_sec: float):
        """
        Переходит к указанному *глобальному* времени в плеере.
        """
        self.video_player_widget.go_to_time(global_time_sec)
        # - Новое: устанавливаем фокус на VideoPlayerWidget после перехода к времени -
        self.video_player_widget.setFocus()
        # - Конец нового -
    # --- Конец нового метода ---

    # --- Новый метод для вызова SMART ---
# ui/main_window.py
# ... (внутри класса MainWindow) ...

# ui/main_window.py
# ... (внутри класса MainWindow) ...

    def run_smart_analysis(self):
        """Вызывает SMARTProcessor и обновляет calculated_ranges, player_shifts, player_shifts_official_timer и интерфейс."""
        # 1. Вызвать основной процессор для calculated_ranges
        try:
            # Передаём total_duration_sec из VideoPlayerWidget
            total_duration = self.video_player_widget.get_total_duration()
            new_calculated_ranges = self.smart_processor.process(self.project.match.generic_labels, total_duration)
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Ошибка при выполнении анализа SMART (calculated_ranges): {str(e)}")
            return # Не обновляем, если ошибка

        # 2. Вызвать процессор для player_shifts
        try:
            # Передаём generic_labels, только что вычисленные calculated_ranges и total_duration
            new_player_shifts = self.smart_processor._process_player_shifts(
                generic_labels=self.project.match.generic_labels,
                calculated_ranges=new_calculated_ranges, # Используем свежие calculated_ranges
                total_duration_sec=total_duration
            )
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Ошибка при выполнении анализа SMART (player_shifts): {str(e)}")
            return # Не обновляем, если ошибка

        # 3. Вызвать процессор для player_shifts_official_timer
        try:
            # Передаём уже вычисленные player_shifts и calculated_ranges
            new_player_shifts_ot = self.smart_processor._process_player_shifts_official_timer(
                player_shifts_data=new_player_shifts, # Используем свежие player_shifts
                calculated_ranges=new_calculated_ranges # Используем свежие calculated_ranges
            )
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Ошибка при выполнении анализа SMART (player_shifts_official_timer): {str(e)}")
            return # Не обновляем, если ошибка

        # 4. Обновить calculated_ranges в проекте
        self.project.match.calculated_ranges = new_calculated_ranges

        # 5. Обновить player_shifts в проекте
        self.project.match.player_shifts = new_player_shifts

        # 6. Обновить player_shifts_official_timer в проекте
        self.project.match.player_shifts_official_timer = new_player_shifts_ot # <-- Новое поле

        # 7. Вызвать автосохранение
        if self.project_file_path:
            try:
                save_project_to_file(self.project, self.project_file_path)
                self.status_label.setText("Проект сохранён (после работы SMART).")
            except Exception as e:
                QMessageBox.warning(self, "Предупреждение", f"Не удалось сохранить проект после SMART: {str(e)}")

        # 8. Обновить range_selector
        self._update_range_selector()

        # 9. Обновить labels_tree_widget (опционально, так как метки не изменились, но обновим для консистентности)
        # Передаём все шесть аргументов (player_shifts_ot пока не передаём)
        self.labels_tree_widget.update_tree(
            self.project.match.generic_labels,          # generic_labels
            self.project.match.calculated_ranges,       # calculated_ranges
            self.project.match.generic_labels,          # generic_labels_ref
            self.project.match.calculated_ranges,       # calculated_ranges_ref
            self.video_player_widget,                 # video_player_widget
            self._save_project_callback               # save_callback
        )
        # --- НОВОЕ: Обновляем TimelineWidget ---
        if self.timeline_widget:
            self.timeline_widget.update_data(
                self.project.match.generic_labels,
                self.project.match.calculated_ranges
            )
        # --- Конец НОВОГО ---

    # --- Конец нового метода ---

# ... (остальной код MainWindow) ...

# ... (остальной код MainWindow) ...

    # --- Новый метод для callback сохранения ---
    def _save_project_callback(self):
        """Callback для вызова из LabelsTreeWidget."""
        if self.project_file_path:
            try:
                save_project_to_file(self.project, self.project_file_path)
                self.status_label.setText("Проект сохранён (из LabelsTreeWidget).")
            except Exception as e:
                QMessageBox.warning(self, "Предупреждение", f"Не удалось сохранить проект из LabelsTreeWidget: {str(e)}")
        else:
            # Если нет пути, вызвать save_project_as?
            # Пока просто покажем предупреждение.
            self.status_label.setText("Нет пути для сохранения из LabelsTreeWidget.")
    # --- Конец нового метода ---

    # --- Новый метод для выбора диапазона в selector и переключения плеера ---
    def _select_range_in_selector_and_playback(self, range_name: str):
        """
        Выбирает указанный диапазон в range_selector и переключает плеер.
        """
        range_selector = self.universal_label_editor_widget.get_range_selector()
        
        index = range_selector.findText(range_name)
        if index >= 0:
            # --- Ключевое исправление: временно блокируем сигналы ТОЛЬКО на время setCurrentIndex ---
            range_selector.blockSignals(True)
            range_selector.setCurrentIndex(index)
            range_selector.blockSignals(False)  # ← Сразу разблокируем!
            
            # Теперь вызываем обработчик вручную (он не сработает автоматически, так как сигнал был временно отключен)
            self.on_range_selection_changed(range_name)
            
            # --- Обновляем TimelineWidget ---
            self._update_timeline_active_range(range_name)
        else:
            self.status_label.setText(f"Диапазон '{range_name}' не найден в списке.")
        # - Новое: устанавливаем фокус на VideoPlayerWidget после выбора диапазона -
        self.video_player_widget.setFocus()
        # - Конец нового -
    # --- Конец нового метода ---

    def on_video_loaded(self, path: str, duration: float, fps: float):
        """Обработчик сигнала от плеера о загрузке видео."""
        self.status_label.setText(f"Видео загружено: {os.path.basename(path)} ({duration:.1f}s, {fps:.1f}fps)")

    def set_active_protocol_event(self, event_dict: Dict[str, Any]):
        """Устанавливает активное событие из протокола для последующего заполнения context."""
        self._active_protocol_event = event_dict  # event_dict уже должна быть копией

    def _init_protocol_validation_widget(self):
        """Инициализирует ProtocolValidationWidget данными из match.events, если они есть."""
        if hasattr(self, 'protocol_validation_widget') and self.project.match.events:
            self.protocol_validation_widget.set_events(self.project.match.events)
        
# Конец содержимого файла: ui/main_window.py