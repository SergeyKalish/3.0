# ui/lineup_module_widget.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QLabel, QFrame, QHBoxLayout, QPushButton,
    QAction, QMenu
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from typing import List, Dict, Optional
# --- НОВОЕ: Импорт GenericLabel ---
from model.project import GenericLabel
# --- КОНЕЦ НОВОГО ---

class LineupModuleWidget(QWidget):
    """
    Виджет для выбора игроков своей команды на льду.
    Отображает состав в виде таблицы с возможностью выбора (чекбоксами).
    Учитывает лимиты на количество игроков, основанные на game_modes.
    Учитывает активные персональные штрафы из game_modes.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._team_roster: List[Dict] = []
        self._calculated_ranges: List[Dict] = []
        self._current_global_time: float = 0.0
        self._our_team_key = None
        # --- НОВОЕ: Ссылка на MainWindow ---
        self.main_window = None
        # --- КОНЕЦ НОВОГО ---

        # Словарь для быстрого поиска строки по id игрока
        self._id_to_row: Dict[str, int] = {}

        # Словарь для хранения QCheckBox
        self._checkboxes: Dict[str, QCheckBox] = {}

        # --- НОВОЕ: Словарь для хранения информации об игроке по id ---
        self._id_to_player_info = {} # <-- Инициализируем здесь
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Количество строк игроков (для корректной очистки пакетов) ---
        self._num_player_rows = 0
        # --- КОНЕЦ НОВОГО ---        

        # --- НОВОЕ: Словарь для отслеживания занятых позиций в пакетах ---
        # Пример: {"1-я пара": {"Левый": "id123", "Правый": "id456"}, "2-я тройка": {"Центр": "id789", ...}}
        self._occupied_positions: Dict[str, Dict[str, str]] = {}
        # --- КОНЕЦ НОВОГО ---

        # Цвета для ролей
        self._role_colors = {
            "Вратарь": QColor(255, 200, 150),  # Светло-оранжевый
            "Защитник": QColor(255, 200, 255), # Светло-розовый
            "Нападающий": QColor(200, 255, 200), # Светло-зеленый
            "Звено": QColor(255, 255, 0)       # ярко желтый
        }

        # --- НОВОЕ: Цвет для штрафованного игрока ---
        self._penalty_color = QColor(255, 200, 200) # Светло-красный
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Флаг, указывающий, что восстановление из метки в процессе ---
        self._restore_in_progress = False
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Следим за тем, устанавливалось ли состояние вручную после восстановления ---
        self._manual_change_occurred_after_restore = False
        # --- КОНЕЦ НОВОГО ---
        
        # --- НОВОЕ: ID игроков, восстановленных последним вызовом restore_from_context ---
        self._last_restored_player_ids = set()
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Чекбокс для восстановления смены слева ---
        self.show_last_change_before_time_checkbox = None # Инициализируем как None, создадим в _setup_ui
        # --- КОНЕЦ НОВОГО ---

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        header_label = QLabel("Состав команды")
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Кнопка "Убрать всех"
        self.clear_button = QPushButton("Убрать всех (кроме вратаря)")
        self.clear_button.clicked.connect(self._on_clear_button_clicked)

        # --- НОВОЕ: Чекбокс "Показать смену слева..." ---
        self.show_last_change_before_time_checkbox = QCheckBox("Показать смену слева...")
        # Подключаем сигнал
        self.show_last_change_before_time_checkbox.stateChanged.connect(self._on_show_last_change_checkbox_toggled)
        # --- КОНЕЦ НОВОГО ---

        # Таблица
        self.table = QTableWidget()
        # 0: #, 1: чекбокс, 2: номер, 3: ФИО, 4: Роль (Амплуа)
        self.table.setColumnCount(6) # Было 5, стало 6 (добавлена колонка "Пакет")
        self.table.setHorizontalHeaderLabels(["#", "", "№", "ФИО", "Амплуа", "Пакет"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # Только для чтения
        self.table.setSelectionBehavior(QTableWidget.SelectRows)  # Выделение строк
        self.table.setSelectionMode(QTableWidget.NoSelection)     # Без выделения строк

        # Настройка ширины колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Чекбокс
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Номер
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # ФИО
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Амплуа
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Пакет

        # Подключение сигнала двойного клика
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # Подключение сигнала правого клика (контекстного меню)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_cell_right_clicked)

        layout.addWidget(header_label)
        layout.addWidget(self.clear_button)
        # --- НОВОЕ: Добавляем чекбокс под кнопку ---
        layout.addWidget(self.show_last_change_before_time_checkbox)
        # --- КОНЕЦ НОВОГО ---
        layout.addWidget(self.table)


    def _on_show_last_change_checkbox_toggled(self, state: int):
            """
            Обработчик изменения состояния чекбокса "Показать смену слева...".
            state: Qt.Checked (2) или Qt.Unchecked (0)
            """
            self.main_window.video_player_widget.setFocus()
            if state == Qt.Checked:
                # Чекбокс включён, пытаемся восстановить смену
                if self.main_window and hasattr(self.main_window, 'get_current_global_time'):
                    current_time = self.main_window.get_current_global_time()
                    # print(f"[DEBUG] Checkbox toggled ON at time {current_time}") # Для отладки
                    restored_player_ids = self.find_last_change_label_before_time(current_time)
                    if restored_player_ids is not None:
                        # print(f"[DEBUG] Found label at time <= {current_time}, restoring players: {restored_player_ids}") # Для отладки
                        # Сохраняем ID перед восстановлением
                        self._last_restored_player_ids = set(restored_player_ids)
                        # Сбрасываем флаг ручного изменения
                        self._manual_change_occurred_after_restore = False
                        # Вызываем восстановление
                        self.restore_from_context({"players_on_ice": restored_player_ids})
                        # _update_checkbox_states вызывается внутри restore_from_context или нужно вызвать отдельно?
                        # Лучше вызвать, чтобы точно обновить состояние после восстановления
                        # NOTE: restore_from_context уже вызывает _update_checkbox_states
                    else:
                        # print(f"[DEBUG] No 'Смена' label found before time {current_time}.") # Для отладки
                        # Ничего не делаем, оставляем текущее состояние
                        pass
                else:
                    print("[WARNING] Cannot restore from label: main_window or get_current_global_time not available.")
            elif state == Qt.Unchecked:
                # Чекбокс выключен, сбрасываем флаг
                # print(f"[DEBUG] Checkbox toggled OFF") # Для отладки
                self._last_restored_player_ids = set()
                self._manual_change_occurred_after_restore = False

    def find_last_change_label_before_time(self, time: float) -> Optional[List[str]]:
        """
        Находит последнюю метку 'Смена' с global_time <= time.
        Возвращает список id_fhm игроков из context.players_on_ice или None.
        """
        if not self.main_window or not hasattr(self.main_window.project, 'match'):
            print("[WARNING] Cannot find labels: main_window or project.match not available.")
            return None

        labels = self.main_window.project.match.generic_labels
        relevant_labels = []

        for label in labels:
            # --- ИСПРАВЛЕНО: обращение к атрибутам объекта GenericLabel ---
            if (label.label_type == "Смена" and
                label.global_time <= time and
                True
               ):
                relevant_labels.append(label)
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Сортируем по global_time по убыванию
        relevant_labels.sort(key=lambda x: x.global_time, reverse=True) # <-- ИСПРАВЛЕНО: x.global_time

        # Берём первую (последнюю по времени слева)
        if relevant_labels:
            latest_label = relevant_labels[0]
            # print(f"[DEBUG] Found 'Смена' label at time {latest_label.global_time}") # Для отладки
            # --- ИСПРАВЛЕНО: обращение к атрибуту context объекта GenericLabel ---
            players_on_ice_raw = latest_label.context.get("players_on_ice") if latest_label.context else None
            # print(f"[DEBUG] Raw players on ice from label: {players_on_ice_raw}") # Для отладки
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            # --- НОВОЕ: Нормализация players_on_ice к списку строк id_fhm ---
            normalized_players_on_ice = []
            if isinstance(players_on_ice_raw, list):
                for item in players_on_ice_raw:
                    if isinstance(item, str):
                        # Если элемент - строка (старый формат), добавляем как есть
                        normalized_players_on_ice.append(item)
                    elif isinstance(item, dict):
                        # Если элемент - словарь (новый формат), извлекаем id_fhm
                        player_id = item.get("id_fhm")
                        if player_id:
                            normalized_players_on_ice.append(player_id)
                        else:
                            # Логируем, если id_fhm нет в словаре
                            print(f"[WARNING] 'id_fhm' not found in player dict: {item}")
                    else:
                        # Логируем, если элемент не строка и не словарь
                        print(f"[WARNING] Unexpected item type in players_on_ice: {type(item)}, value: {item}")
            # --- КОНЕЦ НОВОГО ---

            if normalized_players_on_ice: # Проверяем, что список не пустой после нормализации
                 # print(f"[DEBUG] Normalized players on ice: {normalized_players_on_ice}") # Для отладки
                 return normalized_players_on_ice
            else:
                 print(f"[WARNING] 'players_on_ice' is empty or could not be normalized in label at time {latest_label.global_time}. Raw data: {players_on_ice_raw}")
                 return None
        else:
            # print(f"[DEBUG] No 'Смена' labels found before time {time}") # Для отладки
            return None


    def _on_package_button_clicked(self, package_name: str):
        """
        Обработчик нажатия кнопки 'Выбрать' для строки пакета.
        package_name: Имя пакета (например, "1-я пара", "2-е звено").
        """
        # print(f"[DEBUG] _on_package_button_clicked called for '{package_name}'") # Для отладки
        # Получаем список пакетов и находим нужный
        packages_data = self.get_all_packages_for_display()
        target_package = None
        for pkg in packages_data:
            if pkg['name'] == package_name:
                target_package = pkg
                break

        if not target_package:
            # Пакет с таким именем не найден (например, был удалён)
            print(f"[WARNING] Package '{package_name}' not found in current list for button click.")
            return

        # Получаем id_fhm игроков в целевом пакете
        target_player_ids = [p['id'] for p in target_package['players']]
        pkg_type = target_package['type'] # "pair", "trio", "line"

        # --- НОВОЕ: Определить, какие чекбоксы снимать ---
        ids_to_uncheck = []
        if pkg_type == "pair":
            # Снимаем у всех защитников
            for player_id, checkbox in self._checkboxes.items():
                player_info = self._id_to_player_info.get(player_id)
                if player_info and player_info.get("role") == "Защитник":
                     ids_to_uncheck.append(player_id)
        elif pkg_type == "trio":
            # Снимаем у всех нападающих
            for player_id, checkbox in self._checkboxes.items():
                player_info = self._id_to_player_info.get(player_id)
                if player_info and player_info.get("role") == "Нападающий":
                     ids_to_uncheck.append(player_id)
        elif pkg_type == "line":
            # Снимаем у всех полевых (защитников и нападающих)
            for player_id, checkbox in self._checkboxes.items():
                player_info = self._id_to_player_info.get(player_id)
                if player_info and player_info.get("role") in ["Защитник", "Нападающий"]:
                     ids_to_uncheck.append(player_id)
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Собрать id_fhm игроков, которые должны быть отмечены ---
        ids_to_check = target_player_ids # Все игроки из выбранного пакета
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Выполнить снятие галочек ---
        for pid in ids_to_uncheck:
            checkbox = self._checkboxes.get(pid)
            if checkbox and checkbox.isChecked(): # Только если был отмечен
                checkbox.setChecked(False)
                # print(f"[DEBUG] Unchecked player {pid}") # Для отладки
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Выполнить установку галочек ---
        for pid in ids_to_check:
            checkbox = self._checkboxes.get(pid)
            if checkbox and not checkbox.isChecked(): # Только если не был отмечен
                checkbox.setChecked(True)
                # print(f"[DEBUG] Checked player {pid}") # Для отладки
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: После изменения чекбоксов игроков, вызываем обновление состояний ---
        # Это применит ограничения game_mode и штрафы
        self._update_checkbox_states()
        # --- КОНЕЦ НОВОГО ---

        # print(f"[DEBUG] Finished processing button click for package '{package_name}'.") # Для отладки

    def add_package_rows_to_table(self):
        """
        Добавляет строки для 'пакетов' (пар, троек, звеньев) в конец таблицы.
        Перед пакетами добавляется пустая строка-разделитель.
        """
        # --- НОВОЕ: Очистка существующих строк пакетов ---
        # Удаляем строки, начиная с индекса, следующего за последним игроком.
        num_player_rows = self._num_player_rows
        current_row_count = self.table.rowCount()
        if current_row_count > num_player_rows:
            self.table.setRowCount(num_player_rows)
        # --- КОНЕЦ НОВОГО (Очистка) ---

        # Получаем данные о пакетах
        packages_data = self.get_all_packages_for_display()

        if not packages_data:
            # Если нет пакетов, очистка уже выполнена, выходим
            return

        # --- НОВОЕ: Добавляем строку-разделитель ---
        separator_row_index = self.table.rowCount()
        self.table.insertRow(separator_row_index)
        for col_idx in range(self.table.columnCount()):
            self.table.setItem(separator_row_index, col_idx, QTableWidgetItem(""))
        # --- КОНЕЦ НОВОГО (Разделитель) ---

        # --- НОВОЕ: Добавляем строки для каждого пакета ---
        for pkg_info in packages_data:
            pkg_row_index = self.table.rowCount()
            self.table.insertRow(pkg_row_index)

            # 0: # - оставляем пустым
            self.table.setItem(pkg_row_index, 0, QTableWidgetItem(""))

            # 1: Кнопка - привязана к пакету, текст на основе имени
            pkg_button_widget = QWidget()
            pkg_button_layout = QHBoxLayout(pkg_button_widget)
            pkg_button_layout.setContentsMargins(0, 0, 0, 0)
            pkg_button_layout.setAlignment(Qt.AlignCenter)

            # --- НОВОЕ: Формируем текст кнопки из имени пакета ---
            pkg_name_full = pkg_info['name'] # Например, "1-я пара", "2-е звено"
            # Извлекаем номер и тип
            # Для "X-я ...":
            parts = pkg_name_full.split('-я ') # ["1", "пара"], ["2", "тройка"]
            if len(parts) == 2:
                 number = parts[0]
                 type_part = parts[1].lower()
                 if "пар" in type_part:
                     pkg_button_text = f"{number} пара"
                 elif "тро" in type_part:
                     pkg_button_text = f"{number} тройка"
                 else:
                     pkg_button_text = f"{number} {type_part}" # fallback
            else:
                 # Для "X-е звено": "1-е звено" -> split by '-е '
                 parts_zveno = pkg_name_full.split('-е ') # ["1", " звено"]
                 if len(parts_zveno) == 2:
                      number = parts_zveno[0]
                      pkg_button_text = f"{number} звено"
                 else:
                      # fallback
                      pkg_button_text = pkg_name_full # Или просто "Пакет"?

            pkg_button = QPushButton(pkg_button_text)
                        # --- НОВОЕ: Устанавливаем стиль для кнопки ---
            pkg_button.setStyleSheet("""
                QPushButton {
                    font-size: 10pt; /* Размер шрифта */
                    font-weight: bold; /* Жирный шрифт */
                    /* Можно добавить padding для лучшего вида */
                    padding: 2px;
                }
            """)
            # --- КОНЕЦ НОВОГО ---
            pkg_button_widget.setLayout(pkg_button_layout)
            pkg_button_layout.addWidget(pkg_button)
            # --- КОНЕЦ НОВОГО (Формирование текста кнопки) ---

            # Привязываем сигнал нажатия кнопки пакета
            pkg_button.clicked.connect(
                lambda checked=False, pkg_name=pkg_info['name']: self._on_package_button_clicked(pkg_name) # checked не используется
            )
            # --- НОВОЕ: Устанавливаем цвет фона кнопки в зависимости от типа пакета ---
            pkg_type_lower = pkg_info['type'].lower()
            if pkg_type_lower == "line": # Звено
                # Используем цвет из _role_colors для "Нападающий" или свой желтый
                # pkg_button.setStyleSheet("background-color: rgb(255, 255, 0);") # Желтый
                # Или, чтобы использовать установленный цвет нападающего:
                pkg_button.setStyleSheet(f"background-color: {self._role_colors['Звено'].name()};") # Желтый? Нет, светло-зеленый.
            elif pkg_type_lower == "pair": # Пара
                pkg_button.setStyleSheet(f"background-color: {self._role_colors['Защитник'].name()};") # Светло-розовый
            elif pkg_type_lower == "trio": # Тройка
                pkg_button.setStyleSheet(f"background-color: {self._role_colors['Нападающий'].name()};") # Светло-зеленый
            # else: # fallback
            #     pkg_button.setStyleSheet("") # или цвет по умолчанию
            # --- КОНЕЦ НОВОГО ---

            self.table.setCellWidget(pkg_row_index, 1, pkg_button_widget)

            # 2: Номер - оставляем пустым
            self.table.setItem(pkg_row_index, 2, QTableWidgetItem(""))

            # 3: ФИО - отображаем ТОЛЬКО display_name (список игроков)
            # Было: pkg_name_item = QTableWidgetItem(pkg_info['display_name']) # Например, "1 пара (Иванов/Петров)"
            pkg_players_item = QTableWidgetItem(pkg_info['display_name']) # Теперь: "(Иванов/Петров)"
            self.table.setItem(pkg_row_index, 3, pkg_players_item)

            # 4: Амплуа - можно оставить пустым или указать "Пакет"
            self.table.setItem(pkg_row_index, 4, QTableWidgetItem("Пакет")) # Или ""

            # 5: Принадлежность к пакету - можно оставить пустым или указать тип
            self.table.setItem(pkg_row_index, 5, QTableWidgetItem(pkg_info['type'].upper())) # Или ""

        # --- КОНЕЦ НОВОГО (Добавление строк пакетов) ---

        # print(f"[DEBUG] Added {len(packages_data)} package rows to table.") # Для отладки

    def get_all_packages_for_display(self):
        """
        Формирует список словарей, описывающих 'пакеты' (пары, тройки, звенья),
        на основе данных из self._team_roster (через self._id_to_player_info).
        """
        packages = []
        # Используем _id_to_player_info для доступа к данным
        # Группируем игроков по их lineup_group
        groups_dict = {}
        for player_id, player_info in self._id_to_player_info.items():
            group_name = player_info.get("lineup_group")
            position = player_info.get("lineup_position")
            player_name = player_info.get("name", "Без имени")

            if group_name and position: # Только если игрок назначен
                if group_name not in groups_dict:
                    groups_dict[group_name] = []
                groups_dict[group_name].append({
                    "id": player_id,
                    "name": player_name,
                    "position": position
                })

        # --- НОВОЕ: Разделяем пары и тройки ---
        pairs_dict = {}
        trios_dict = {}
        for group_name, players_list in groups_dict.items():
            lower_group_name = group_name.lower()
            if "пара" in lower_group_name:
                # Извлекаем номер (например, "1" из "1-я пара")
                parts = group_name.split("-я ")
                if len(parts) == 2:
                    number = parts[0]
                    pairs_dict[number] = {
                        "name": group_name,
                        "players": players_list,
                        "type": "pair"
                    }
            elif "тройка" in lower_group_name:
                # Извлекаем номер (например, "1" из "1-я тройка")
                parts = group_name.split("-я ")
                if len(parts) == 2:
                    number = parts[0]
                    trios_dict[number] = {
                        "name": group_name,
                        "players": players_list,
                        "type": "trio"
                    }
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Формируем список пакетов (пары и тройки) и звеньев ---
        # Сначала добавим пары и тройки как есть
        for pkg_type, pkg_dict in [("pair", pairs_dict), ("trio", trios_dict)]:
            for number, details in pkg_dict.items():
                # Сортируем игроков в пакете по позиции для стабильного отображения
                # Правила сортировки:
                # - Для "pair": Левый, Правый
                # - Для "trio": Центр, Левый, Правый
                # - Для "line" (ниже): Центр, Левый, Правый, Лев.Защ, Прав.Защ
                position_order = {"Центр": 0, "Левый": 1, "Правый": 2, "Ц": 0, "Лев": 1, "Прав": 2}
                sorted_players = sorted(details['players'], key=lambda p: position_order.get(p['position'], 999))

                # --- НОВОЕ: Формируем строку имён без имен и лишних пробелов ---
                # Извлекаем только фамилию (первое слово из полного имени)
                names_parts = [p['name'].split()[0] for p in sorted_players]
                names_str_no_spaces = "/".join(names_parts)
                # --- КОНЕЦ НОВОГО ---

                # --- НОВОЕ: Формируем display_name ТОЛЬКО с игроками ---
                # Было: pkg_display_name = f"{number} {details['type'][:-1]}а ({names_str_no_spaces})" # "1 пара (Иванов/Петров)"
                pkg_display_name_only_players = f"({names_str_no_spaces})" # "(Иванов/Петров)"
                # --- КОНЕЦ НОВОГО ---

                package_info = {
                    "name": details["name"], # Полное имя группы (например, "1-я пара") - для внутреннего использования
                    "display_name": pkg_display_name_only_players, # Имя ТОЛЬКО для отображения в UI (ФИО колонка)
                    "players": sorted_players,
                    "type": details["type"],
                    "group_identifier": details["name"] # Оригинальный идентификатор
                }
                packages.append(package_info)

        # Теперь формируем звенья на основе совпадающих номеров
        for number in pairs_dict:
            if number in trios_dict:
                pair_details = pairs_dict[number]
                trio_details = trios_dict[number]

                # Объединяем игроков
                combined_players = pair_details['players'] + trio_details['players']

                # Сортируем объединённых игроков по позиции для звена
                # Правила сортировки для "line": Центр, Левый, Правый, Лев.Защ, Прав.Защ
                position_order_line = {"Центр": 0, "Левый": 1, "Правый": 2, "Ц": 0, "Лев": 1, "Прав": 2}
                sorted_combined_players = sorted(combined_players, key=lambda p: position_order_line.get(p['position'], 999))

                # --- НОВОЕ: Формируем строку имён для звена без имен и лишних пробелов ---
                names_parts_line = [p['name'].split()[0] for p in sorted_combined_players]
                names_str_line_no_spaces = "/".join(names_parts_line)
                # --- КОНЕЦ НОВОГО ---

                line_name = f"{number}-е звено"
                # --- НОВОЕ: Формируем display_name звена ТОЛЬКО с игроками ---
                # Было: line_display_name = f"{number} звено ({names_str_line_no_spaces})" # "1 звено (Сидоров/...)"
                line_display_name_only_players = f"({names_str_line_no_spaces})" # "(Сидоров/...)"
                # --- КОНЕЦ НОВОГО ---

                line_info = {
                    "name": line_name, # Имя звена (например, "1-е звено") - для внутреннего использования
                    "display_name": line_display_name_only_players, # Имя ТОЛЬКО для отображения в UI (ФИО колонка)
                    "players": sorted_combined_players, # Объединённые игроки
                    "type": "line", # Тип звена
                    "group_identifier": f"{pair_details['name']}/{trio_details['name']}" # Идентификатор из пары/тройки
                }
                packages.append(line_info)

        # --- НОВОЕ: Обновлённая сортировка: Звенья -> Тройки -> Пары -> по номеру ---
        # --- НОВОЕ: Обновлённая сортировка: Звенья -> Тройки -> Пары -> по номеру ---
        def sort_key(pkg):
            name = pkg['name']
            # Извлекаем номер и тип из полного имени пакета (например, "1-я пара", "2-е звено")
            # Для "X-я ...":
            parts = name.split('-я ') # ["1", "пара"], ["2", "тройка"]
            if len(parts) == 2:
                 number_str = parts[0]
                 type_part = parts[1].lower()
                 type_for_sorting = type_part
            else:
                 # Для "X-е звено": "1-е звено" -> split by '-е '
                 parts_zveno = name.split('-е ') # ["1", " звено"]
                 if len(parts_zveno) == 2:
                      number_str = parts_zveno[0]
                      type_for_sorting = "звено" # Нормализуем тип для сортировки
                 else:
                      # fallback
                      number_str = "999"
                      type_for_sorting = name.lower()

            try:
                number = int(number_str)
            except ValueError:
                number = 999 # fallback

            # Определим приоритет типа: звено -> тройка -> пара
            # Чем меньше число, тем выше приоритет (идёт раньше)
            type_priority = {
                "звено": 0,
                "тройка": 1,
                "пара": 2
            }
            type_sort_val = type_priority.get(type_for_sorting, 999)

            return (type_sort_val, number) # Сначала по приоритету типа, потом по номеру

        packages.sort(key=sort_key)
        # --- КОНЕЦ НОВОГО ---
        # --- КОНЕЦ НОВОГО ---

        return packages
    
    def _on_cell_right_clicked(self, pos):
        """
        Обработчик правого клика по таблице.
        Открывает контекстное меню для строки, на которой был клик.
        """
        # Получаем индекс строки, по которой был клик
        row = self.table.rowAt(pos.y())
        if row == -1 or row >= self.table.rowCount():
            # Клик вне строк или за пределами таблицы
            return

        # Проверяем, есть ли у нас информация об игроке в этой строке
        player_id = None
        for pid, r in self._id_to_row.items():
            if r == row:
                player_id = pid
                break

        if player_id:
            # Создаём и показываем контекстное меню
            menu = self._create_context_menu_for_player(row)
            if menu:
                menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _create_context_menu_for_player(self, row: int):
        """
        Создаёт контекстное меню для строки игрока.
        """
        # Получаем id игрока по строке
        player_id = None
        for pid, r in self._id_to_row.items():
            if r == row:
                player_id = pid
                break

        if not player_id:
            return None

        # Получаем информацию об игроке
        player_info = self._id_to_player_info.get(player_id)
        if not player_info:
            return None

        role = player_info.get("role", "Неизвестно")

        # Создаём меню
        menu = QMenu(self)

        # Если вратарь - только "Снять назначение"
        if role == "Вратарь":
            action_remove = QAction("Снять назначение", self)
            action_remove.triggered.connect(lambda: self.remove_player_from_group_in_roster(player_id))
            menu.addAction(action_remove)
            # Вратари не участвуют в пакетах, выходим
            return menu

        # Для защитников и нападающих
        if role == "Защитник":
            submenu_include = menu.addMenu("Включить в пару")
            for i in range(1, 5): # 1-я пара, 2-я пара, 3-я пара, 4-я пара
                group_name = f"{i}-я пара"
                submenu_group = submenu_include.addMenu(group_name)
                positions = ["Левый", "Правый"]
                for pos_name in positions:
                    full_name = f"{group_name} ({pos_name})"
                    # Проверяем, занята ли позиция
                    is_occupied = (group_name in self._occupied_positions and
                                   pos_name in self._occupied_positions[group_name])
                    if not is_occupied:
                        action = QAction(full_name, self)
                        # Используем lambda с захватом переменных
                        action.triggered.connect(lambda checked=False, pid=player_id, gn=group_name, pn=pos_name:
                                                 self.assign_player_to_group_in_roster(pid, gn, pn))
                        submenu_group.addAction(action)
                    else:
                        # Если занята, можно сделать неактивной
                        action = QAction(full_name, self)
                        action.setEnabled(False) # Делаем неактивной
                        submenu_group.addAction(action)

        elif role == "Нападающий":
            submenu_include = menu.addMenu("Включить в тройку")
            for i in range(1, 5): # 1-я тройка, 2-я тройка, 3-я тройка, 4-я тройка
                group_name = f"{i}-я тройка"
                submenu_group = submenu_include.addMenu(group_name)
                positions = ["Центр", "Левый", "Правый"]
                for pos_name in positions:
                    full_name = f"{group_name} ({pos_name})"
                    # Проверяем, занята ли позиция
                    is_occupied = (group_name in self._occupied_positions and
                                   pos_name in self._occupied_positions[group_name])
                    if not is_occupied:
                        action = QAction(full_name, self)
                        # Используем lambda с захватом переменных
                        action.triggered.connect(lambda checked=False, pid=player_id, gn=group_name, pn=pos_name:
                                                 self.assign_player_to_group_in_roster(pid, gn, pn))
                        submenu_group.addAction(action)
                    else:
                        # Если занята, можно сделать неактивной
                        action = QAction(full_name, self)
                        action.setEnabled(False) # Делаем неактивной
                        submenu_group.addAction(action)

        # Добавляем "Снять назначение"
        action_remove = QAction("Снять назначение", self)
        action_remove.triggered.connect(lambda: self.remove_player_from_group_in_roster(player_id))
        menu.addAction(action_remove)

        return menu

    
    def assign_player_to_group_in_roster(self, player_id: str, group_name: str, position: str):
        """
        Назначает игроку принадлежность к пакету и позицию.
        Обновляет self._team_roster, self.project.match.rosters, self._occupied_positions.
        """
        # Найти игрока в self._team_roster и self.project.match.rosters[our_team_key]
        target_player_in_team_roster = None
        target_player_in_project_rosters = None

        # 1. Найти в self._team_roster
        for player in self._team_roster:
            if player.get("id_fhm") == player_id:
                target_player_in_team_roster = player
                break

        # 2. Найти в self.project.match.rosters[our_team_key]
        if self.main_window and self._our_team_key:
            project_roster = self.main_window.project.match.rosters.get(self._our_team_key, [])
            for player in project_roster:
                if player.get("id_fhm") == player_id:
                    target_player_in_project_rosters = player
                    break
        else:
            print(f"[WARNING] Cannot assign group: main_window or _our_team_key not set.")
            return

        if not target_player_in_team_roster or not target_player_in_project_rosters:
            print(f"[WARNING] Player with id {player_id} not found in current roster or project roster.")
            return

        # 3. Обновить поля в обоих словарях
        target_player_in_team_roster["lineup_group"] = group_name
        target_player_in_team_roster["lineup_position"] = position
        target_player_in_project_rosters["lineup_group"] = group_name
        target_player_in_project_rosters["lineup_position"] = position

        # 4. Обновить self._occupied_positions
        #    Сначала освободить старую позицию, если она была
        old_group = target_player_in_team_roster.get("lineup_group") # Это новый group_name, но логика ниже учитывает это
        old_position = target_player_in_team_roster.get("lineup_position") # Это новый position, но логика ниже учитывает это
        # НЕТ! Нужно найти старую позицию до обновления. Пока не будем удалять старую, просто добавим новую/обновим.
        # Лучше переписать: сначала удалить из _occupied_positions, если игрок был там, затем добавить новое.
        # Найдем старую информацию в _id_to_player_info, если она была
        current_info = self._id_to_player_info.get(player_id, {})
        old_group = current_info.get("lineup_group")
        old_position = current_info.get("lineup_position")

        # Удалить из _occupied_positions, если игрок был назначен
        if old_group and old_position:
             if old_group in self._occupied_positions and old_position in self._occupied_positions[old_group]:
                 del self._occupied_positions[old_group][old_position]
                 # Если внутри группы больше нет назначенных, удалим и саму группу
                 if not self._occupied_positions[old_group]:
                     del self._occupied_positions[old_group]

        # Добавить/обновить в _occupied_positions
        if group_name not in self._occupied_positions:
            self._occupied_positions[group_name] = {}
        self._occupied_positions[group_name][position] = player_id

        # 5. Обновить отображение (колонка "Пакет", возможно, пересортировка)
        # Перезагружаем данные, чтобы обновить _id_to_player_info и таблицу
        # Используем текущий _team_roster, он уже обновлён
        self.set_team_roster(self._team_roster) # Это пересоздаст таблицу и обновит _id_to_player_info

        # 6. Вызвать callback для сохранения проекта
        if hasattr(self, '_save_project_callback') and callable(self._save_project_callback):
            self._save_project_callback()
       
        print(f"[DEBUG] Assign: Updated {player_id} -> {group_name} ({position})")
        print(f"[DEBUG] Player in _team_roster now: {target_player_in_team_roster}")
        print(f"[DEBUG] Player in project.rosters now: {target_player_in_project_rosters}")
        print(f"[DEBUG] _occupied_positions after assign: {self._occupied_positions}")

    def remove_player_from_group_in_roster(self, player_id: str):
        """
        Исключает игрока из пакета (удаляет lineup_group и lineup_position).
        Обновляет self._team_roster, self.project.match.rosters, self._occupied_positions.
        """
        # Найти игрока в self._team_roster и self.project.match.rosters[our_team_key]
        target_player_in_team_roster = None
        target_player_in_project_rosters = None

        # 1. Найти в self._team_roster
        for player in self._team_roster:
            if player.get("id_fhm") == player_id:
                target_player_in_team_roster = player
                break

        # 2. Найти в self.project.match.rosters[our_team_key]
        if self.main_window and self._our_team_key:
            project_roster = self.main_window.project.match.rosters.get(self._our_team_key, [])
            for player in project_roster:
                if player.get("id_fhm") == player_id:
                    target_player_in_project_rosters = player
                    break
        else:
            print(f"[WARNING] Cannot remove group: main_window or _our_team_key not set.")
            return

        if not target_player_in_team_roster or not target_player_in_project_rosters:
            print(f"[WARNING] Player with id {player_id} not found in current roster or project roster.")
            return

        # Проверить, был ли игрок назначен
        was_assigned = "lineup_group" in target_player_in_team_roster and "lineup_position" in target_player_in_team_roster
        if not was_assigned:
            # Игрок не был назначен, нечего удалять
            # print(f"[DEBUG] Player {player_id} was not assigned to any group, nothing to remove.") # Для отладки
            return

        # 3. Удалить поля из обоих словарей
        old_group = target_player_in_team_roster.get("lineup_group")
        old_position = target_player_in_team_roster.get("lineup_position")

        target_player_in_team_roster.pop("lineup_group", None)
        target_player_in_team_roster.pop("lineup_position", None)
        target_player_in_project_rosters.pop("lineup_group", None)
        target_player_in_project_rosters.pop("lineup_position", None)

        # 4. Обновить self._occupied_positions
        # Удалить из _occupied_positions
        if old_group and old_position:
             if old_group in self._occupied_positions and old_position in self._occupied_positions[old_group]:
                 del self._occupied_positions[old_group][old_position]
                 # Если внутри группы больше нет назначенных, удалим и саму группу
                 if not self._occupied_positions[old_group]:
                     del self._occupied_positions[old_group]

        # 5. Обновить отображение (колонка "Пакет", возможно, пересортировка)
        # Перезагружаем данные, чтобы обновить _id_to_player_info и таблицу
        # Используем текущий _team_roster, он уже обновлён
        self.set_team_roster(self._team_roster) # Это пересоздаст таблицу и обновит _id_to_player_info

        # 6. Вызвать callback для сохранения проекта
        if hasattr(self, '_save_project_callback') and callable(self._save_project_callback):
            self._save_project_callback()
        # print(f"[DEBUG] Removed player {player_id} from group. _occupied_positions: {self._occupied_positions}") # Для отладки
        # В remove_player_from_group_in_roster, после удаления
        print(f"[DEBUG] Remove: Cleared assignment for {player_id}")
        print(f"[DEBUG] Player in _team_roster now: {target_player_in_team_roster}")
        print(f"[DEBUG] Player in project.rosters now: {target_player_in_project_rosters}")
        print(f"[DEBUG] _occupied_positions after remove: {self._occupied_positions}")

    def set_our_team_key(self, team_key: str):
        """
        Устанавливает идентификатор нашей команды ("f-team" или "s-team").
        """
        self._our_team_key = team_key
        print(f"[DEBUG LUM] Our team key received: {team_key}")
        # print(f"[DEBUG] LineupModuleWidget: Our team key set to {team_key}") # Для отладки

    def _on_cell_double_clicked(self, row: int, column: int):
        """
        Обработчик двойного клика по ячейке таблицы.
        Переключает чекбокс в строке, если клик НЕ по колонке чекбокса (1).
        """
        # Проверяем, кликнули ли по колонке с чекбоксом
        if column == 1:
            # Если клик по чекбоксу, ничего не делаем, пусть стандартное поведение сработает
            return

        # Проходим по нашему словарю _id_to_row, чтобы найти player_id для строки
        for player_id, stored_row in self._id_to_row.items():
            if stored_row == row:
                checkbox = self._checkboxes.get(player_id)
                if checkbox and checkbox.isEnabled(): # Проверяем, что чекбокс активен
                    # Переключаем состояние чекбокса
                    checkbox.setChecked(not checkbox.isChecked())
                break # Нашли строку, выходим из цикла

        # --- НОВОЕ: Установка фокуса на плеер ---
        if self.main_window:
            self.main_window.video_player_widget.setFocus()
        # --- КОНЕЦ НОВОГО ---

    def _on_clear_button_clicked(self):
        """
        Снимает все галочки, кроме вратарей.
        """
        for player_id, checkbox in self._checkboxes.items():
            row = self._id_to_row.get(player_id)
            if row is not None:
                role_item = self.table.item(row, 4) # Амплуа
                if role_item and role_item.text() != "Вратарь":
                    checkbox.setChecked(False)
        # После снятия вызываем обновление состояния
        self._update_checkbox_states()

        # --- НОВОЕ: Установка фокуса на плеер ---
        if self.main_window:
            self.main_window.video_player_widget.setFocus()
        # --- КОНЕЦ НОВОГО ---

    def set_team_roster(self, roster: List[Dict]):
        """
        Устанавливает состав команды и заполняет таблицу.
        """
        self._team_roster = roster
        self._id_to_row.clear()
        self._checkboxes.clear()
        # --- НОВОЕ: Очищаем _id_to_player_info перед заполнением ---
        self._id_to_player_info.clear() # Или используем update, но clear проще
        # --- КОНЕЦ НОВОГО ---
        self.table.setRowCount(0)

        if not roster:
            return

        # Группируем по ролям
        role_order = {"Вратарь": 0, "Защитник": 1, "Нападающий": 2}
        # --- НОВОЕ: Сортировка с учётом принадлежности к пакетам ---
        def custom_sort_key(player):
            role = player.get("role", "Прочее")
            role_sort_value = role_order.get(role, 99)

            # Извлекаем информацию о пакете
            group_name = player.get("lineup_group") # e.g., "1-я пара"
            position_name = player.get("lineup_position") # e.g., "Левый"

            # Для ролей, где нужна сортировка по пакетам
            if role in ["Защитник", "Нападающий"] and group_name and position_name:
                # Извлекаем номер из group_name (например, "1-я пара" -> "1")
                parts = group_name.split("-я ")
                if len(parts) == 2:
                    number_str = parts[0]
                    type_part = parts[1].lower()
                else:
                    # fallback, если формат не стандартный
                    number_str = "999"
                    type_part = "unknown"

                # Пытаемся преобразовать номер в целое для правильной сортировки (1, 2, 10 -> 1, 2, 10, а не 1, 10, 2)
                try:
                    group_number = int(number_str)
                except ValueError:
                    group_number = 999 # fallback

                # Определяем порядок позиции внутри пакета
                position_order_map = {"центр": 0, "лев": 1, "прав": 2, "ц": 0, "л": 1, "п": 2} # Используем начало строки
                pos_order = position_order_map.get(position_name.lower()[:3], 999) # [:3] для "центр" -> "цент" -> "цен" -> не найдено, 999
                # Более точное сопоставление
                pos_order_detailed = {"центр": 0, "левый": 1, "правый": 2, "ц": 0, "л": 1, "п": 2}
                pos_order_final = pos_order_detailed.get(position_name.lower(), 999)

                # Порядок: роль, признак "есть пакет" (0), номер пакета, тип пакета (пара < тройка), позиция в пакете, номер игрока (для стабильности)
                return (role_sort_value, 0, pos_order_final, group_number, int(player.get("number", 0)))
            else:
                # Для игроков без пакета или других ролей (вратари)
                # Порядок: роль, признак "нет пакета" (1), номер игрока
                return (role_sort_value, 1, int(player.get("number", 0)))

        sorted_roster = sorted(roster, key=custom_sort_key)
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Сначала заполняем _id_to_player_info и _team_roster ---
        # self._team_roster уже присвоен в начале функции, но пересортировка важна.
        # self._team_roster теперь sorted_roster
        self._team_roster = sorted_roster

        # Заполняем _id_to_player_info до заполнения таблицы
        for player in self._team_roster:
            player_id = player.get("id_fhm") # Используем id_fhm как идентификатор
            if player_id: # Убедимся, что id_fhm существует
                self._id_to_player_info[player_id] = player
        # --- КОНЕЦ НОВОГО ---

        self.table.setRowCount(len(sorted_roster))

        # --- НОВОЕ: Обновляем количество строк игроков ---
        self._num_player_rows = len(sorted_roster)
        # --- КОНЕЦ НОВОГО ---

        for row_index, player in enumerate(sorted_roster):
            player_id = player.get("id_fhm", str(row_index))  # Используем id_fhm как идентификатор
            player_role = player.get("role", "Неизвестно")
            player_number = str(player.get("number", ""))
            player_name_full = player.get("name", "Без имени")

            # 0: #
            self.table.setItem(row_index, 0, QTableWidgetItem(str(row_index + 1)))

            # 1: Чекбокс
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)

            checkbox = QCheckBox()
            checkbox_widget.setLayout(checkbox_layout)
            checkbox_layout.addWidget(checkbox)

            # Сохраняем ссылку на QCheckBox
            self._checkboxes[player_id] = checkbox

            # Привязываем сигнал изменения состояния
            checkbox.stateChanged.connect(lambda state, p_id=player_id: self._on_checkbox_changed(p_id, state))

            self.table.setCellWidget(row_index, 1, checkbox_widget)

            # 2: Номер
            number_item = QTableWidgetItem(player_number)
            self.table.setItem(row_index, 2, number_item)

            # 3: ФИО (Изменение: Фамилия Имя) (ВЫКЛЮЧИЛ ПЕРЕСТАНОВКУ ФАМИЛИИ И ИМЕНИ, т.к. реализовал это в модуле парсинга протокола)
            name_item = QTableWidgetItem(player_name_full)
            self.table.setItem(row_index, 3, name_item)

            # 4: Амплуа (Роль) - сокращения
            short_role = player_role
            if player_role == "Вратарь":
                short_role = "Вр."
            elif player_role == "Нападающий":
                short_role = "Нап."
            elif player_role == "Защитник":
                short_role = "Защ."
            role_item = QTableWidgetItem(short_role)
            self.table.setItem(row_index, 4, role_item)

            # 5: Принадлежность к пакету
            # Получаем информацию об игроке из _id_to_player_info (теперь доступна!)
            player_info = self._id_to_player_info.get(player_id)
            if player_info is None:
                package_text = "-" # Если информация не найдена (в принципе, не должно происходить, если id_fhm уникальны)
            else:
                player_role = player_info.get("role", "Неизвестно")
                if player_role == "Вратарь":
                    package_text = "-" # Вратари не участвуют
                else:
                    group = player_info.get("lineup_group") # Например, "1-я пара"
                    position = player_info.get("lineup_position") # Например, "Левый"
                    if group and position:
                        # Формат: "<номер><тип>(<позиция>)"
                        # Пример: "1-я пара", "Левый" -> "1ПараЛ"
                        # Пример: "2-я тройка", "Центр" -> "2ТрЦ"
                        # Разбор group
                        parts = group.split("-я ") # ["1", "пара"] или ["2", "тройка"]
                        if len(parts) == 2:
                            number = parts[0]
                            type_part = parts[1].lower()
                            # Сокращение типа
                            if type_part.startswith("пар"):
                                type_short = "Пар"
                            elif type_part.startswith("тро"):
                                type_short = "Тр"
                            else:
                                type_short = type_part # fallback

                            # Сокращение позиции
                            if position.startswith("Лев"):
                                pos_short = "Л"
                            elif position.startswith("Прав"):
                                pos_short = "П"
                            elif position.startswith("Цент"):
                                pos_short = "Ц"
                            else:
                                pos_short = position[0] # fallback, берем первую букву

                            package_text = f"{number}{type_short}{pos_short}"
                        else:
                            package_text = "-" # Если формат group неожиданный
                    else:
                        package_text = "-" # Если нет group или position

            package_item = QTableWidgetItem(package_text)
            self.table.setItem(row_index, 5, package_item)

            # Сохраняем индекс строки
            self._id_to_row[player_id] = row_index

            # Устанавливаем цвет фона строки по умолчанию (роль)
            bg_color = self._role_colors.get(player_role, QColor(240, 240, 240)) # Белесый по умолчанию
            for col_idx in range(self.table.columnCount()):
                item = self.table.item(row_index, col_idx)
                if item:
                    item.setBackground(bg_color)
                    # --- НОВОЕ: Установка шрифта по умолчанию ---
                    default_font = QFont()
                    item.setFont(default_font)
                    # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Обновление _occupied_positions на основе _team_roster (и _id_to_player_info) ---
        # Очищаем словарь перед заполнением
        self._occupied_positions.clear()

        # Можно использовать self._id_to_player_info вместо self._team_roster, так как они синхронизированы
        for p_id, p_info in self._id_to_player_info.items():
            group_name = p_info.get("lineup_group")
            position_name = p_info.get("lineup_position")
            # player_id уже p_id

            # Проверяем, что все необходимые данные есть
            if group_name and position_name and p_id:
                # Если группа ещё не существует в словаре, создаём для неё вложенный словарь
                if group_name not in self._occupied_positions:
                    self._occupied_positions[group_name] = {}
                # Привязываем id игрока к конкретной позиции в группе
                # Если позиция уже занята (например, ошибка в данных), новое значение перезапишет старое
                self._occupied_positions[group_name][position_name] = p_id

        # print(f"[DEBUG] _occupied_positions updated: {self._occupied_positions}") # Для отладки
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Добавляем строки для 'пакетов' ---
        self.add_package_rows_to_table()
        # --- КОНЕЦ НОВОГО ---

        # После заполнения таблицы, обновляем ограничения
        self._update_checkbox_states()

        print(f"[DEBUG] Set_team_roster ВЫЗВАН") # Для отладки

    # --- НОВОЕ: Метод для установки ссылки на MainWindow ---
    def set_main_window(self, main_window):
        self.main_window = main_window
    # --- КОНЕЦ НОВОГО ---

    def set_current_global_time_and_calculated_ranges(self, global_time: float, calculated_ranges: List[Dict], generic_labels: List[GenericLabel]):
        """
        Обновляет внутреннее состояние времени и calculated_ranges.
        Вызывает пересчёт состояния чекбоксов.
        """
        self._current_global_time = global_time
        self._calculated_ranges = calculated_ranges

        # --- НОВОЕ: Автоматическое восстановление, если чекбокс включён и не было ручного изменения после восстановления ---
        # Проверяем, включён ли чекбокс "Показать смену слева..."
        if self.show_last_change_before_time_checkbox.isChecked():
            # Ищем последнюю метку "Смена" до текущего времени
            restored_player_ids_from_time = self.find_last_change_label_before_time(global_time)
            if restored_player_ids_from_time is not None:
                # Сравниваем с тем, что было восстановлено последним разом
                # Если ID не совпадают, это новое состояние, которое нужно восстановить
                # Если совпадают, восстанавливать не нужно, состояние уже верное
                if set(restored_player_ids_from_time) != self._last_restored_player_ids:
                    # print(f"[DEBUG] Time changed to {time}, auto-restoring players due to checked checkbox.") # Для отладки
                    # Сохраняем ID перед восстановлением
                    self._last_restored_player_ids = set(restored_player_ids_from_time)
                    # Сбрасываем флаг ручного изменения, так как это автоматическое восстановление
                    self._manual_change_occurred_after_restore = False
                    # Вызываем восстановление
                    self.restore_from_context({"players_on_ice": restored_player_ids_from_time})
                    # _update_checkbox_states вызывается внутри restore_from_context
                # else:
                #     print(f"[DEBUG] Time changed to {time}, but players match last restored. No action needed.") # Для отладки
            else:
                # print(f"[DEBUG] Time changed to {time}, no 'Смена' label found, auto-unchecking checkbox.") # Для отладки
                # Не нашли метку, возможно, стоит снять чекбокс?
                # Или оставить как есть, и ждать, когда появится метка слева?
                # Пока оставим как есть, пользователь увидит, что состояние не восстановлено.
                # Но логично снять, если метка исчезла.
                # Однако, если просто снять, то при следующем движении плеера, если метка появится,
                # она автоматически восстановится, что может быть неожиданно.
                # Лучше оставить включенным, но не восстанавливать, если метки нет.
                # Или восстановить в "пустое" состояние?
                # restore_from_context({"players_on_ice": []}) ?
                # Нет, лучше не трогать, если метки нет. Пусть пользователь сам решает.
                # Но если мы не восстанавливаем, а чекбокс включён, это может вводить в заблуждение.
                # Вариант 1: Оставить включенным, не восстанавливать, если нет метки.
                # Вариант 2: Снять чекбокс, если нет метки.
                # Выбираем Вариант 1: Оставляем включенным. Оператор увидит, что состояние не изменилось.
                pass
        # --- КОНЕЦ НОВОГО ---

        self._update_checkbox_states()
        print(f"[DEBUG LUM] Received time: {global_time}, ranges count: {len(calculated_ranges)}, our team key: {self._our_team_key}")

    def _update_checkbox_states(self):
        """
        Обновляет состояние (активен/неактивен) чекбоксов
        на основе _current_global_time, _calculated_ranges, _our_team_key и текущего выбора.
        Использует player_id_fhm для сопоставления активных штрафов.
        """
        # Найти активный game_mode
        active_game_mode = None
        for cr in self._calculated_ranges:
            if cr.label_type == "game_mode":
                if cr.start_time <= self._current_global_time < cr.end_time:
                    active_game_mode = cr
                    break

        # --- НОВОЕ: Определить ожидаемое количество полевых игроков для НАШЕЙ команды ---
        expected_field_players = 5 # Значение по умолчанию
        if active_game_mode:
            mode_str = active_game_mode.name # e.g., "5 на 4"
            try:
                # Разбиваем строку по " на "
                parts = mode_str.split(" на ")
                # Предполагаем, что формат всегда X на Y
                f_team_count = int(parts[0])
                s_team_count = int(parts[1])

                # Выбираем количество в зависимости от нашей команды
                if self._our_team_key == "f-team":
                    expected_field_players = f_team_count
                elif self._our_team_key == "s-team":
                    expected_field_players = s_team_count
                else:
                    # Если our_team_key не определён или неизвестен
                    expected_field_players = 5

            except (ValueError, IndexError):
                # Если формат строки неожиданный или не удаётся преобразовать в int,
                # используем значение по умолчанию
                expected_field_players = 5
        # --- КОНЕЦ НОВОГО ---


        # --- НОВОЕ: Подсчитываем отмеченных НЕштрафованных игроков ---
        # Это нужно для правильного применения ограничений
        selected_field_count = 0
        selected_goalie_count = 0

        # Сначала собираем ID игроков на штрафе
        penalty_player_ids = set()
        if active_game_mode:
            active_penalties = active_game_mode.context.get("active_penalties", [])
            for penalty in active_penalties:
                # Проверяем, что штраф для нашей команды и это персональный штраф (с ID)
                if penalty.get("team") == self._our_team_key and penalty.get("player_id_fhm"):
                    penalty_player_ids.add(penalty.get("player_id_fhm"))

        # Теперь подсчитываем отмеченных игроков, исключая штрафованных
        for player_id, checkbox in self._checkboxes.items():
            # Ищем информацию об игроке
            player_info = self._id_to_player_info.get(player_id)
            if player_info and checkbox.isChecked():
                # Проверяем, не находится ли игрок на штрафе
                if player_id not in penalty_player_ids:
                    role = player_info.get("role", "Неизвестно")
                    if role == "Вратарь":
                        selected_goalie_count += 1
                    else:
                        selected_field_count += 1
        # --- КОНЕЦ НОВОГО ---


        # Определяем максимальное количество полевых игроков
        # Если вратарь отмечен, то max_field = expected_field_players (например, 5)
        # Если вратарь НЕ отмечен, то max_field = expected_field_players + 1 (например, 6)
        max_field_players = expected_field_players + (1 if selected_goalie_count == 0 else 0)


        # Обновляем состояние чекбоксов и подсветку строк
        for player_id, checkbox in self._checkboxes.items():
            row = self._id_to_row.get(player_id)
            if row is not None:
                # Получаем информацию об игроке из _id_to_player_info
                player_info = self._id_to_player_info.get(player_id)
                if player_info:
                    player_role = player_info.get("role", "Неизвестно")
                    player_name_in_table = player_info.get("name", "Без имени") # Используем имя из rosters, которое отображается

                    role_item = self.table.item(row, 4) # Амплуа
                    number_item = self.table.item(row, 2) # Номер
                    name_item = self.table.item(row, 3) # ФИО
                    checkbox_widget = self.table.cellWidget(row, 1) # QWidget с чекбоксом
                    package_text = self.table.item(row, 5) # Принадлежность к пакету

                    if role_item and number_item and name_item and checkbox_widget:
                        checkbox_layout = checkbox_widget.layout()
                        actual_checkbox = checkbox_layout.itemAt(0).widget() if checkbox_layout.count() > 0 else None

                        # --- НОВОЕ: Проверка, находится ли игрок на штрафной скамейке ---
                        is_on_penalty = player_id in penalty_player_ids
                        # --- КОНЕЦ НОВОГО ---

                        # --- НОВОЕ: Установка подсветки строки ---
                        if is_on_penalty:
                            bg_color = self._penalty_color
                        else:
                            bg_color = self._role_colors.get(player_role, QColor(240, 240, 240))
                        # Устанавливаем цвет для всех ячеек строки
                        for col_idx in range(self.table.columnCount()):
                            item = self.table.item(row, col_idx)
                            if item:
                                item.setBackground(bg_color)
                        # Также для чекбокса
                        checkbox_widget.setStyleSheet(f"background-color: {bg_color.name()};")
                        # --- КОНЕЦ НОВОГО ---

                        # --- НОВОЕ: Установка жирного шрифта для отмеченных строк ---
                        # --- ПРИМЕЧАНИЕ: Место для изменения размера шрифта ---
                        font = QFont()
                        if checkbox.isChecked():
                            font.setBold(True)
                            # font.setPointSize(font.pointSize() + 2)  # Пример увеличения размера шрифта
                            font.setPointSize(12) # Или фиксированный размер, если нужно
                        else:
                            font.setBold(False)
                            # font.setPointSize(font.pointSize() - 2) # Или вернуть к дефолтному
                            font.setPointSize(10) # Или фиксированный размер по умолчанию

                        # Применяем шрифт к ячейкам
                        number_item.setFont(font)
                        name_item.setFont(font)
                        role_item.setFont(font)
                        package_text.setFont(font)
                        # --- КОНЕЦ НОВОГО ---


                        # Если чекбокс уже отмечен, проверяем его состояние
                        if checkbox.isChecked():
                            # Если игрок на штрафе, чекбокс должен быть неактивен и галочка снята
                            if is_on_penalty:
                                checkbox.setEnabled(False)
                                checkbox.setChecked(False) # Снимаем галочку, если она была
                                # Обновляем подсчёт, так как мы только что сняли галочку
                                # (Это важно, если этот игрок был последним, нарушая ограничение)
                                # NOTE: Подсчёт в начале метода уже исключил штрафованных из selected_*_count,
                                #       поэтому снятие галочки с штрафованного игрока не влияет на счетчики.
                                #       Однако, если галочка была снята вручную до обновления, счетчики могли быть неверны.
                                #       Логика подсчёта теперь корректна.
                            else:
                                checkbox.setEnabled(True)
                            continue # Переходим к следующему чекбоксу

                        # Проверяем лимиты и штрафы для НЕотмеченных чекбоксов
                        is_disabled = False
                        if player_role == "Вратарь":
                            # Нельзя отметить второго вратаря, если один уже отмечен
                            if selected_goalie_count >= 1:
                                is_disabled = True
                        else: # Полевой
                            # Нельзя отметить полевого, если лимит достигнут
                            # Используем max_field_players, вычисленное выше
                            # NOTE: selected_field_count уже не включает штрафованных игроков
                            if selected_field_count >= max_field_players:
                                is_disabled = True
                            # --- НОВОЕ: Нельзя отметить игрока на штрафе ---
                            if is_on_penalty:
                                is_disabled = True
                            # --- КОНЕЦ НОВОГО ---

                        # Обновляем состояние чекбокса
                        checkbox.setEnabled(not is_disabled)
                        # Также обновляем стиль чекбокса, чтобы отразить его состояние (серый если disabled)
                        if not checkbox.isEnabled():
                            actual_checkbox.setStyleSheet("QCheckBox { color: gray; }")
                        else:
                            actual_checkbox.setStyleSheet("") # Сброс стиля


        

    def _on_checkbox_changed(self, player_id: str, state: int):
        """
        Обработчик изменения состояния чекбокса игрока.
        """
        self.main_window.video_player_widget.setFocus()
        # --- НОВОЕ: Проверка, происходило ли сейчас автоматическое восстановление ---
        # Если изменение произошло ВНУТРИ restore_from_context, не отключаем чекбокс "Показать смену слева..."
        if not self._restore_in_progress:
            # Изменение произошло не в рамках восстановления (ручное изменение)
            if self.show_last_change_before_time_checkbox.isChecked():
                # Ручное изменение -> отключаем чекбокс и устанавливаем флаг
                # print(f"[DEBUG] Manual change detected for player {player_id}, unchecking 'Show Last Change' checkbox.") # Для отладки
                self.show_last_change_before_time_checkbox.blockSignals(True) # Блокируем сигнал, чтобы не сработал _on_show_last_change_checkbox_toggled
                self.show_last_change_before_time_checkbox.setChecked(False)
                self.show_last_change_before_time_checkbox.blockSignals(False) # Восстанавливаем сигналы
                self._manual_change_occurred_after_restore = True # Устанавливаем флаг
        # else:
        #     # Изменение произошло в рамках восстановления (например, restore_from_context отметил чекбокс)
        #     # Не отключаем главный чекбокс, не меняем флаг _manual_change_occurred_after_restore.
        #     pass
        # --- КОНЕЦ НОВОГО ---

        # --- Старая/новая логика обновления ограничений ---
        # Вызываем обновление состояний чекбоксов (ограничения game_mode, штрафы)
        # NOTE: _update_checkbox_states пересчитывает всё состояние
        # self._restore_in_progress уже сброшен к этому моменту (если был True).
        # self._manual_change_occurred_after_restore устанавливается выше, до этого вызова.
        self._update_checkbox_states()
        # --- Конец старой/новой логики ---

    def get_selected_player_ids(self) -> List[str]:
        """
        Возвращает список id_fhm отмеченных игроков.
        """
        selected_ids = []
        for player_id, checkbox in self._checkboxes.items():
            if checkbox.isChecked():
                selected_ids.append(player_id)
        return selected_ids

    def restore_from_context(self, context: dict):
        """
        Восстанавливает состояние чекбоксов игроков на основе контекста.
        context: Словарь, например {"players_on_ice": ["id1", "id2", ...]}
        """
        # --- ИСПРАВЛЕНО: Проверяем, что параметр context существует ---
        if not isinstance(context, dict):
             print(f"[ERROR] restore_from_context: context is not a dict, got {type(context)}: {context}")
             return # или raise ValueError(...)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Получаем список ID игроков, которые должны быть отмечены
        players_on_ice_ids = context.get("players_on_ice", []) # <-- context ДОЛЖЕН быть доступен здесь

        # --- НОВОЕ: Устанавливаем флаг, что восстановление началось ---
        self._restore_in_progress = True
        # --- КОНЕЦ НОВОГО ---

        # Сбрасываем ВСЕ чекбоксы
        for checkbox in self._checkboxes.values():
            if checkbox.isChecked(): # Только если был отмечен
                checkbox.setChecked(False)

        # Отмечаем чекбоксы для указанных игроков
        for player_id in players_on_ice_ids:
            checkbox = self._checkboxes.get(player_id)
            if checkbox and not checkbox.isChecked(): # Только если не был отмечен
                checkbox.setChecked(True)

        # --- НОВОЕ: Сбрасываем флаг, что восстановление завершено ---
        self._restore_in_progress = False
        # --- КОНЕЦ НОВОГО ---

        # Обновляем ограничения и состояния (включая серый цвет для недоступных)
        # Это важно, так как восстановленное состояние может нарушать текущие game_mode/штрафы
        self._update_checkbox_states()
        # print(f"[DEBUG] Restored state for players: {players_on_ice_ids}") # Для отладки

        # --- НОВОЕ: Установка фокуса на плеер ---
        if self.main_window:
            self.main_window.video_player_widget.setFocus()
        # --- КОНЕЦ НОВОГО ---