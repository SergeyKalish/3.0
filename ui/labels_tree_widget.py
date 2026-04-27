# ui/labels_tree_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QHeaderView, QMenu, QAction, QMessageBox
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence, QColor, QBrush # Импортируем QKeySequence для горячей клавиши, QColor/QBrush для подсветки
from model.project import GenericLabel, CalculatedRange # Импортируем модель метки и диапазона
from typing import List, Set # Импортируем List и Set

# --- Новая функция для форматирования чисел ---
def format_number_with_space_separator(value: float) -> str:
    """
    Форматирует float как целое число с пробелом-разделителем разрядов,
    используя "человеческое" округление.

    Args:
        value: Число с плавающей точкой (например, 1234.5, 56789.0).

    Returns:
        Строка с целым числом и пробелом-разделителем (например, "1 235", "56 789").
    """
    # Округляем float до ближайшего целого числа
    rounded_integer = round(value)
    # Используем f-string с форматом 'd' и спецификатором '_', который вставляет '_'.
    # Затем заменяем '_' на пробел ' '.
    formatted_string = f"{rounded_integer:_}".replace('_', ' ')
    return formatted_string

def format_seconds_to_min_sec(total_seconds: int) -> str:
    """
    Форматирует длительность/время в секундах в строку "X мин Y сек".

    Args:
        total_seconds: Длительность или время в секундах (целое число).

    Returns:
        Строка в формате "X мин Y сек".
    """
    if total_seconds < 0:
        total_seconds = 0 # Обработка отрицательных значений, если нужно
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes} м {seconds} с"


def format_player_name(player_name: str) -> str:
    """
    Преобразует полное имя "Фамилия Имя" в формат "Фамилия И.".
    
    Args:
        player_name: Полное имя игрока (например, "Иванов Иван").
        
    Returns:
        Строка в формате "Фамилия И." или исходное имя, если формат не распознан.
    """
    if not player_name or player_name == "N/A":
        return ""
    
    parts = player_name.split()
    if len(parts) >= 2:
        # Фамилия Имя → Фамилия И.
        return f"{parts[0]} {parts[1][0]}."
    elif len(parts) == 1:
        # Только фамилия
        return parts[0]
    return player_name
# --- Конец новых функций ---

class LabelsTreeWidget(QWidget):
    """
    Виджет для отображения списка GenericLabel и CalculatedRange в виде дерева.
    Позволяет двойным кликом перейти к времени метки или выбрать диапазон в плеере.
    Позволяет через контекстное меню редактировать или удалять метки.
    """
    # Сигнал, эмитируемый при двойном клике на элементе списка метки
    labelSelected = pyqtSignal(float) # Передаёт global_time метки
    # --- Новый сигнал для выбора диапазона ---
    rangeSelectedForPlayback = pyqtSignal(str) # Передаёт name диапазона
    # --- Новый сигнал для двойного клика по метке "Смена" ---
    shiftLabelDoubleClicked = pyqtSignal(dict, float) # Передаёт context и global_time метки "Смена"
    # --- Новый сигнал для изменения состояния развёрнутости ---
    expansionStateChanged = pyqtSignal(dict)
    # ---

    def __init__(self):
        super().__init__()

        # --- Новое: Константы для специальных меток ---
        self.SPECIAL_LABEL_TYPES = {"Пауза", "Смена"}
        self.NUM_PERIODS = 3
        # --- Конец нового ---

        layout = QVBoxLayout(self)

        self.labels_tree = QTreeWidget()
        # Добавляем колонку "Длительность", оставляем "Тип", "№", "Время (с)"
        self.labels_tree.setHeaderLabels(["Тип", "№", "Время (с)", "Длительность"])
        # Сделаем столбцы растягиваемыми, № и Длительность - меньше
        header = self.labels_tree.header()
        # Столбец "Тип" - фиксированной ширины, ограниченной
        header.setSectionResizeMode(0, QHeaderView.Fixed) # Изменено на Fixed
        self.labels_tree.header().resizeSection(0, 230) # Установите желаемую ширину в пикселях (например, 150)
        # Столбец "№" - фиксированной ширины, уменьшенной
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Изменяем на ResizeToContents
        # Столбец "Время (с)" - растягивается
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        # Столбец "Длительность" - фиксированной ширины, уменьшенной
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Изменяем на ResizeToContents

        # Подключаем сигнал двойного клика
        self.labels_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        # Подключаем сигнал вызова контекстного меню
        self.labels_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labels_tree.customContextMenuRequested.connect(self._show_context_menu)

        # --- Новое: Добавляем горячую клавишу Delete ---
        self.delete_action_shortcut = QAction(self)
        self.delete_action_shortcut.setShortcut(QKeySequence.Delete)
        self.delete_action_shortcut.setShortcutContext(Qt.WidgetWithChildrenShortcut) # Работает, когда виджет или его потомки в фокусе
        self.delete_action_shortcut.triggered.connect(self._on_delete_requested_shortcut)
        self.addAction(self.delete_action_shortcut)
        # ---

        layout.addWidget(self.labels_tree)

        # --- Хранилище данных и методов ---
        self._generic_labels_ref = None # Ссылка на список generic_labels из MainWindow
        self._calculated_ranges_ref = None # Ссылка на список calculated_ranges из MainWindow
        self._video_player_ref = None # Ссылка на VideoPlayerWidget
        self._save_callback = None # Ссылка на метод сохранения из MainWindow
        self._rosters_ref = None # Ссылка на rosters из MainWindow
        # ---

        # --- Действия контекстного меню ---
        self.edit_action = QAction("Установить текущее время плеера", self) # Обновленный текст
        self.edit_action.triggered.connect(self._on_edit_requested)
        self.delete_action = QAction("Удалить", self)
        self.delete_action.triggered.connect(self._on_delete_requested)
        # Добавим действие для диапазонов
        self.jump_to_range_action = QAction("Перейти к диапазону", self)
        self.jump_to_range_action.triggered.connect(self._on_jump_to_range_requested)
        # Действие для тоггла буллита
        self.toggle_penalty_shot_action = QAction("Это буллит", self)
        self.toggle_penalty_shot_action.setCheckable(True)
        self.toggle_penalty_shot_action.triggered.connect(self._on_toggle_penalty_shot)
        # ---

        # --- Новое: Атрибуты для хранения состояния развёрнутости ---
        self._expanded_parent_items: Set[str] = set()
        self._expanded_periodic_items: Set[str] = set()
        # --- Конец нового ---

        # --- Новое: Сохранённые состояния развёрнутости из проекта ---
        self._saved_expansion_states: Optional[dict] = None
        # --- Конец нового ---

        # --- Новое: Атрибут для хранения ссылок на статические узлы ---
        self._periodic_parent_items = {}
        # --- Конец нового ---

        # --- Новое: Подключение сигналов развёрнутости ---
        self.labels_tree.itemExpanded.connect(self._on_expansion_changed)
        self.labels_tree.itemCollapsed.connect(self._on_expansion_changed)
        # --- Конец нового ---


    def update_tree(self, generic_labels: List[GenericLabel], calculated_ranges: List[CalculatedRange], generic_labels_ref: List[GenericLabel], calculated_ranges_ref: List[CalculatedRange], video_player_widget, save_callback, rosters_ref=None):
        """
        Обновляет содержимое QTreeWidget на основе списков GenericLabel и CalculatedRange.
        Группирует метки по label_type.
        Принимает ссылки на списки из MainWindow для модификации,
        ссылку на VideoPlayerWidget для получения времени,
        и callback для сохранения проекта.
        """
        # Сохраняем ссылки
        self._generic_labels_ref = generic_labels_ref
        self._calculated_ranges_ref = calculated_ranges_ref
        self._video_player_ref = video_player_widget
        self._save_callback = save_callback
        self._rosters_ref = rosters_ref

        # --- Подсветка меток с одинаковым временем в одной категории ---
        from collections import defaultdict
        time_counts = defaultdict(int)
        for label in generic_labels:
            time_counts[(label.label_type, label.global_time)] += 1
        # --- Конец подсветки ---

        # --- Новое: Сохранить состояние развёрнутости перед очисткой ---
        self._save_expansion_state()
        # --- Конец нового ---

        self.labels_tree.clear()

        # --- Новое: Создаём узел "О проекте" (в самом верху) ---
        project_info_parent_item = QTreeWidgetItem(self.labels_tree, ["О проекте", "", "", ""])
        # Восстанавливаем состояние
        project_info_parent_item.setExpanded("О проекте" in self._expanded_parent_items)

        # --- НОВОЕ: Расчёт суммы ЧИИ по периодам "на лету" ---
        # Находим периоды (Сегменты с именами "Период 1", "Период 2", "Период 3")
        periods = {}
        for cr in calculated_ranges:
            if cr.label_type == "Сегмент":
                if cr.name == "Период 1":
                    periods[1] = (cr.start_time, cr.end_time)
                elif cr.name == "Период 2":
                    periods[2] = (cr.start_time, cr.end_time)
                elif cr.name == "Период 3":
                    periods[3] = (cr.start_time, cr.end_time)
        
        # Находим все ЧИИ (Чистое игровое время)
        chii_ranges = [cr for cr in calculated_ranges if cr.label_type == "ЧИИ"]
        
        # Считаем сумму ЧИИ для каждого периода
        period_chii_sum = {1: 0.0, 2: 0.0, 3: 0.0}
        for chii in chii_ranges:
            chii_start = chii.start_time
            chii_duration = chii.end_time - chii.start_time
            
            # Определяем, к какому периоду относится это ЧИИ (по времени начала)
            for period_num, (period_start, period_end) in periods.items():
                if period_start <= chii_start < period_end:
                    period_chii_sum[period_num] += chii_duration
                    break
        
        # Создаём дочерние элементы для П1.ЧИИ, П2.ЧИИ, П3.ЧИИ
        for period_num in [1, 2, 3]:
            sum_duration = period_chii_sum[period_num]
            # Форматирование длительности с пробелом-разделителем и в "мин:сек"
            formatted_duration = format_number_with_space_separator(sum_duration)
            formatted_duration_min_sec = format_seconds_to_min_sec(int(sum_duration))
            
            child_item = QTreeWidgetItem(project_info_parent_item, [
                f"П{period_num}.ЧИИ",  # Тип
                "-",  # №
                "-",  # Время (с)
                f"{formatted_duration} ({formatted_duration_min_sec})"  # Длительность
            ])
            # Установка выравнивания по правому краю для колонки "Длительность"
            child_item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
        # ---

        # --- Новое: Создаём статические узлы "ПX.Тип" ---
        self._periodic_parent_items.clear() # Очищаем словарь перед заполнением
        for p_num in range(1, self.NUM_PERIODS + 1):
            for label_type in self.SPECIAL_LABEL_TYPES:
                periodic_name = f"П{p_num}.{label_type}"
                periodic_item = QTreeWidgetItem(self.labels_tree, [periodic_name, "", "", ""])
                # Восстанавливаем состояние
                periodic_item.setExpanded(periodic_name in self._expanded_parent_items)
                # Сохраняем ссылку в словаре
                self._periodic_parent_items[periodic_name] = periodic_item
        # ---

        # --- Новое: Создаём узел "Удаления" (между "П3.Смена" и "Диапазоны") ---
        deletions_parent_item = QTreeWidgetItem(self.labels_tree, ["Удаления", "", "", ""])
        # Восстанавливаем состояние
        deletions_parent_item.setExpanded("Удаления" in self._expanded_parent_items)

        # Находим calculated_ranges с label_type == "Удаление"
        deletion_ranges = [cr for cr in calculated_ranges if cr.label_type == "Удаление"]

        # Заполняем узел "Удаления" дочерними элементами
        for i, deletion_range in enumerate(deletion_ranges):
            duration = deletion_range.end_time - deletion_range.start_time
            # Форматирование времени и длительности с пробелом-разделителем, округлением и "мин:сек"
            formatted_start_time = format_number_with_space_separator(deletion_range.start_time)
            formatted_end_time = format_number_with_space_separator(deletion_range.end_time)
            formatted_duration = format_number_with_space_separator(duration)
            formatted_duration_min_sec = format_seconds_to_min_sec(int(duration))

            # --- Новое: Формирование отображаемого имени для колонки "Тип" ---
            # Если имя диапазона начинается с "Удаление ", отображаем только оставшуюся часть после "Удаление ".
            # Обрабатываем случаи "УдалениеX..." и "Удаление X..."
            # print(f"DEBUG: Processing CalculatedRange for 'Deletions' node. Full name: '{deletion_range.name}'") # <-- Новый отладочный принт
            display_name = deletion_range.name
            if deletion_range.name.startswith("Удаление"): # <-- Проверяем на "Удаление" (без пробела)
                # print(f"DEBUG: Name starts with 'Удаление'. Full name: '{deletion_range.name}'") # <-- Новый отладочный принт
                # Извлекаем оставшуюся часть после "Удаление "
                # Используем split(' ', 1) для разделения по первому пробелу
                parts = deletion_range.name.split(' ', 1)
                if len(parts) > 1:
                    # Есть текст после первого пробела
                    display_name = parts[1].strip() # Берём часть после "Удаление " и убираем лишние пробелы
                    # print(f"DEBUG: Extracted suffix after 'Удаление ': '{display_name}'") # <-- Новый отладочный принт
                else:
                    # Нет пробела после "Удаление", значит, имя состоит только из "Удаление" или "УдалениеX..."
                    # В этом случае, можно оставить display_name как есть или обработать особым образом.
                    # Просто уберём "Удаление" из начала, если больше ничего нет.
                    # display_name = deletion_range.name[len("Удаление"):] # Удалить только "Удаление", оставить X...
                    # Но это не универсально. Лучше оставить как есть, если нет пробела.
                    # Однако, в вашем примере всегда есть пробел и текст после.
                    print(f"DEBUG: No space found after 'Удаление' in name: '{deletion_range.name}'. Keeping original name for display.") # <-- Новый отладочный принт
                    # display_name = deletion_range.name # <-- Это строка не выполнится для ваших данных
                    pass # <-- Это выполнится, display_name останется полным именем, если не было пробела (что не так для ваших данных)
            elif deletion_range.name == "Удаление":
                # Если имя точно "Удаление", можно отобразить пустую строку или добавить номер на основе индекса i
                # display_name = "" # Пример: пустая строка
                display_name = f"Удаление ({i+1})" # Пример: Удаление (1), Удаление (2)...
                print(f"DEBUG: Exact name 'Удаление'. Setting display_name to: '{display_name}'") # <-- Новый отладочный принт
            # (Можно добавить другие правила при необходимости)
            # --- Конец нового ---


            child_item = QTreeWidgetItem(deletions_parent_item, [
                display_name, # Имя диапазона "Удаление" в колонку "Тип"
                str(i + 1), # Порядковый номер (начинаем с 1)
                f"{formatted_start_time} - {formatted_end_time}", # Время начала - конец с округлением, разделителем и в "мин:сек"
                f"{formatted_duration} ({formatted_duration_min_sec})" # Длительность с округлением, разделителем и в "мин:сек"
            ])
            # --- Новое: Установка выравнивания по правому краю для числовых колонок ---
            child_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter) # Время
            child_item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter) # Длительность
            # --- Конец нового ---
            # Сохраняем индекс диапазона в списке как user data в первом столбце дочернего элемента
            child_item.setData(4, 0, id(deletion_range)) # Используем id объекта как уникальный ключ
        # ---

        # --- Новое: Создаём узел "Диапазоны" ---
        # (Сюда попадут все остальные calculated_ranges, кроме "ЧИИ_СУММА" и "Удаление")
        ranges_parent_item = QTreeWidgetItem(self.labels_tree, ["Диапазоны", "", "", ""])
        # Восстанавливаем состояние
        ranges_parent_item.setExpanded("Диапазоны" in self._expanded_parent_items)

        # Сортируем диапазоны по времени начала (предполагаем, что "Всё видео" всегда первое из-за SMART)
        sorted_calculated_ranges = sorted(calculated_ranges, key=lambda x: x.start_time)

        # Заполняем узел "Диапазоны" дочерними элементами
        for i, calc_range in enumerate(sorted_calculated_ranges):
            # Пропускаем диапазоны с label_type == "ЧИИ_СУММА" (они в узле "О проекте")
            # Пропускаем диапазоны с label_type == "Удаление" (они в узле "Удаления")
            if calc_range.label_type in ["ЧИИ_СУММА", "Удаление"]:
                continue

            duration = calc_range.end_time - calc_range.start_time
            # Форматирование времени и длительности с пробелом-разделителем и округлением
            formatted_start_time = format_number_with_space_separator(calc_range.start_time)
            formatted_end_time = format_number_with_space_separator(calc_range.end_time)
            formatted_duration = format_number_with_space_separator(duration)

            # Форматирование длительности в "мин:сек"
            formatted_duration_min_sec = format_seconds_to_min_sec(int(duration))

            child_item = QTreeWidgetItem(ranges_parent_item, [
                calc_range.name, # Имя диапазона в колонку "Тип"
                str(i + 1), # Порядковый номер (начинаем с 1)
                f"{formatted_start_time} - {formatted_end_time}", # Время начала - конец с округлением и разделителем
                f"{formatted_duration} ({formatted_duration_min_sec})" # Длительность с округлением, разделителем и в "мин:сек"
            ])
            # --- Новое: Установка выравнивания по правому краю для числовых колонок ---
            child_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter) # Время
            child_item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter) # Длительность
            # --- Конец нового ---
            # Сохраняем индекс диапазона в списке как user data в первом столбце дочернего элемента
            child_item.setData(4, 0, id(calc_range)) # Используем id объекта как уникальный ключ
        # ---

        # --- Новое: Создаём узел "Метки" ---
        labels_parent_item = QTreeWidgetItem(self.labels_tree, ["Метки", "", "", ""])
        # Восстанавливаем состояние
        labels_parent_item.setExpanded("Метки" in self._expanded_parent_items)

        # Группируем метки по типу
        labels_by_type = {}
        for label in generic_labels:
            if label.label_type not in labels_by_type:
                labels_by_type[label.label_type] = []
            labels_by_type[label.label_type].append(label)

        # Сортируем метки внутри каждого типа по времени
        for label_type, labels in labels_by_type.items():
            labels.sort(key=lambda x: x.global_time)

        # Заполняем узел "Метки" группами и дочерними элементами
        for label_type, labels in labels_by_type.items():
            # --- Новое: Логика размещения для специальных типов ---
            if label_type in self.SPECIAL_LABEL_TYPES:
                # Для "Пауза" и "Смена" размещаем метки в статические узлы "ПX.Тип"
                for i, label in enumerate(labels):
                    # Проверяем, есть ли period_name в context
                    period_name = label.context.get("period_name") if label.context else None
                    if period_name:
                        # Извлекаем номер периода из строки "Период N"
                        # Простой способ - найти цифры в конце строки после последнего пробела
                        # или использовать split
                        try:
                            # Проверяем формат "Период N"
                            parts = period_name.split(" ")
                            if len(parts) == 2 and parts[0] == "Период":
                                period_num_str = parts[1]
                                period_num = int(period_num_str)
                                if 1 <= period_num <= self.NUM_PERIODS:
                                    parent_key = f"П{period_num}.{label_type}"
                                    parent_item = self._periodic_parent_items.get(parent_key)
                                    if parent_item:
                                        # Форматирование времени с пробелом-разделителем и округлением
                                        formatted_time = format_number_with_space_separator(label.global_time)
                                        # Форматирование времени в "мин:сек"
                                        formatted_time_min_sec = format_seconds_to_min_sec(int(label.global_time))

                                        # === НОВОЕ: Для меток "Смена" формируем отображение номеров игроков ===
                                        type_display = ""
                                        if label_type == "Смена" and label.context and label.context.get("players_on_ice"):
                                            players = label.context.get("players_on_ice", [])
                                            
                                            # Получаем rosters для поиска lineup данных
                                            roster_dict = {}
                                            if self._rosters_ref:
                                                for team_key, team_roster in self._rosters_ref.items():
                                                    for player in team_roster:
                                                        roster_dict[player.get('id_fhm')] = player
                                            
                                            # Сначала определяем вратаря (у него нет lineup_group/lineup_position)
                                            goalie = None
                                            skaters = []  # игроки не вратари
                                            
                                            for p in players:
                                                player_id = p.get('id_fhm')
                                                roster_info = roster_dict.get(player_id, {})
                                                role = roster_info.get('role', '').lower()
                                                # Берём номер из rosters, а не из контекста метки
                                                number = str(roster_info.get('number', 'N/A'))
                                                
                                                if 'вратарь' in role:
                                                    goalie = number
                                                else:
                                                    skaters.append((p, number))
                                            
                                            # Проверяем, есть ли у всех НЕ-вратарей заполненные lineup_group и lineup_position
                                            all_skaters_have_lineup = all(
                                                roster_dict.get(p[0].get('id_fhm'), {}).get('lineup_group') and 
                                                roster_dict.get(p[0].get('id_fhm'), {}).get('lineup_position')
                                                for p in skaters
                                            )
                                            
                                            forwards = []  # нападающие
                                            defenders = []  # защитники
                                            
                                            for p, number in skaters:
                                                player_id = p.get('id_fhm')
                                                roster_info = roster_dict.get(player_id, {})
                                                
                                                if all_skaters_have_lineup:
                                                    # Используем lineup_group и lineup_position
                                                    group = roster_info.get('lineup_group', '').lower()
                                                    position = roster_info.get('lineup_position', '').lower()
                                                    
                                                    # "тройка" = нападающие, "пара" = защитники
                                                    if 'тройка' in group:
                                                        forwards.append((position, number))
                                                    elif 'пара' in group:
                                                        defenders.append((position, number))
                                                    else:
                                                        # Если lineup_group не распознан, fallback на role
                                                        role = roster_info.get('role', '').lower()
                                                        if 'нападающий' in role:
                                                            forwards.append(('', number))
                                                        elif 'защитник' in role:
                                                            defenders.append(('', number))
                                                else:
                                                    # Fallback на role
                                                    role = roster_info.get('role', '').lower()
                                                    if 'нападающий' in role:
                                                        forwards.append(('', number))
                                                    elif 'защитник' in role:
                                                        defenders.append(('', number))
                                            
                                            # Сортируем по позиции, если есть lineup данные
                                            if all_skaters_have_lineup:
                                                # Порядок: Левый, Центр, Правый (или Левый, Правый для защитников)
                                                pos_order = {
                                                    'левый': 0, 'left': 0,
                                                    'центр': 1, 'center': 1, 'centre': 1,
                                                    'правый': 2, 'right': 2
                                                }
                                                forwards.sort(key=lambda x: pos_order.get(x[0], 99))
                                                defenders.sort(key=lambda x: pos_order.get(x[0], 99))
                                                forwards = [num for _, num in forwards]
                                                defenders = [num for _, num in defenders]
                                            else:
                                                forwards = [num for _, num in forwards]
                                                defenders = [num for _, num in defenders]
                                            
                                            # Формируем строку: вратарь | нападающие | защитники
                                            parts = []
                                            if goalie:
                                                parts.append(goalie)
                                            if forwards:
                                                parts.append(', '.join(forwards))
                                            if defenders:
                                                parts.append(', '.join(defenders))
                                            type_display = ' | '.join(parts)
                                        # === КОНЕЦ НОВОГО ===

                                        child_item = QTreeWidgetItem(parent_item, [
                                            type_display, # Для "Смена" - номера игроков, иначе пусто
                                            str(i + 1), # Порядковый номер (начинаем с 1)
                                            f"{formatted_time} ({formatted_time_min_sec})", # Время с округлением, разделителем и в "мин:сек"
                                            "" # Длительность для метки - пустая строка
                                        ])
                                        # --- Новое: Установка выравнивания по правому краю для числовых колонок ---
                                        child_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter) # Время
                                        # --- Конец нового ---
                                        # Сохраняем индекс метки в списке как user data в первом столбце дочернего элемента
                                        child_item.setData(4, 0, id(label)) # Используем id объекта как уникальный ключ
                                        # --- Подсветка дублирующегося времени ---
                                        if time_counts.get((label.label_type, label.global_time), 0) > 1:
                                            pink_brush = QBrush(QColor(255, 192, 203))
                                            for col in range(4):
                                                child_item.setBackground(col, pink_brush)
                                        # --- Конец подсветки ---
                                    else:
                                         # Логирование или игнорирование, если узел не найден (маловероятно)
                                        print(f"WARNING: Parent item {parent_key} not found for label {label.id} with period_name {period_name}")
                                else:
                                     # Логирование или игнорирование, если номер периода вне диапазона
                                    print(f"WARNING: Period number {period_num} out of range [1, {self.NUM_PERIODS}] for label {label.id}")
                            else:
                                 # Логирование или игнорирование, если формат period_name не "Период N"
                                print(f"WARNING: Unexpected period_name format '{period_name}' for label {label.id}")
                        except ValueError:
                             # Логирование или игнорирование, если не удалось распарсить номер периода
                            print(f"WARNING: Could not parse period number from '{period_name}' for label {label.id}")
                    else:
                        # Если period_name нет, размещаем в старый общий узел типа "Пауза" или "Смена"
                        # Создаём узел типа метки (если его ещё нет, хотя он должен быть)
                        type_item = QTreeWidgetItem(labels_parent_item, [label_type, "", "", ""])
                        # Восстанавливаем состояние группы меток (если нужно, можно хранить отдельно для каждого типа)
                        # type_item.setExpanded(label_type in self._expanded_periodic_items)

                        # Форматирование времени с пробелом-разделителем и округлением
                        formatted_time = format_number_with_space_separator(label.global_time)
                        # Форматирование времени в "мин:сек"
                        formatted_time_min_sec = format_seconds_to_min_sec(int(label.global_time))

                        child_item = QTreeWidgetItem(type_item, [
                            "", # Тип уже в родительском элементе
                            str(i + 1), # Порядковый номер (начинаем с 1)
                            f"{formatted_time} ({formatted_time_min_sec})", # Время с округлением, разделителем и в "мин:сек"
                            "" # Длительность для метки - пустая строка
                        ])
                        # --- Новое: Установка выравнивания по правому краю для числовых колонок ---
                        child_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter) # Время
                        # --- Конец нового ---
                        # Сохраняем индекс метки в списке как user data в первом столбце дочернего элемента
                        child_item.setData(4, 0, id(label)) # Используем id объекта как уникальный ключ
                        # --- Подсветка дублирующегося времени ---
                        if time_counts.get((label.label_type, label.global_time), 0) > 1:
                            pink_brush = QBrush(QColor(255, 192, 203))
                            for col in range(4):
                                child_item.setBackground(col, pink_brush)
                        # --- Конец подсветки ---
            else:
                # --- Старая логика для остальных типов (например, "Сегмент", "Гол", "Удаление") ---
                # Создаём узел для типа метки
                type_item = QTreeWidgetItem(labels_parent_item, [label_type, "", "", ""])
                # Восстанавливаем состояние группы меток (если нужно, можно хранить отдельно для каждого типа)
                # type_item.setExpanded(label_type in self._expanded_periodic_items)

                # Добавляем дочерние элементы для каждой метки этого типа
                for i, label in enumerate(labels):
                    # Форматирование времени с пробелом-разделителем и округлением
                    formatted_time = format_number_with_space_separator(label.global_time)

                    # Форматирование времени в "мин:сек"
                    formatted_time_min_sec = format_seconds_to_min_sec(int(label.global_time))

                    # === НОВОЕ: Для меток "Удаление" и "Гол" показываем имя игрока в колонке "Длительность" ===
                    duration_text = ""
                    if label_type in ("Удаление", "Гол") and label.context and isinstance(label.context, dict):
                        player_name = label.context.get("player_name", "")
                        if player_name:
                            duration_text = format_player_name(player_name)
                    # === КОНЕЦ НОВОГО ===

                    child_item = QTreeWidgetItem(type_item, [
                        "", # Тип уже в родительском элементе
                        str(i + 1), # Порядковый номер (начинаем с 1)
                        f"{formatted_time} ({formatted_time_min_sec})", # Время с округлением, разделителем и в "мин:сек"
                        duration_text # Длительность: имя игрока для "Удаление" и "Гол", иначе пусто
                    ])
                    # --- Новое: Установка выравнивания по правому краю для числовых колонок ---
                    child_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter) # Время
                    # --- Конец нового ---
                    # Сохраняем индекс метки в списке как user data в первом столбце дочернего элемента
                    child_item.setData(4, 0, id(label)) # Используем id объекта как уникальный ключ
                    # --- Подсветка дублирующегося времени ---
                    if time_counts.get((label.label_type, label.global_time), 0) > 1:
                        pink_brush = QBrush(QColor(255, 192, 203))
                        for col in range(4):
                            child_item.setBackground(col, pink_brush)
                    # --- Конец подсветки ---
            # --- Конец новой/старой логики ---


        # --- Новое: Восстановить состояние развёрнутости после заполнения ---
        self._restore_expansion_state()
        # --- Конец нового ---

    def get_expansion_states(self) -> dict:
        """Возвращает текущие состояния развёрнутости узлов дерева."""
        return {
            "parent_items": list(self._expanded_parent_items),
            "periodic_items": list(self._expanded_periodic_items),
        }

    def set_saved_expansion_states(self, states: Optional[dict]):
        """Устанавливает состояния развёрнутости из проекта для применения при обновлении дерева."""
        self._saved_expansion_states = states

    def _on_expansion_changed(self, item):
        """Обработчик изменения развёрнутости узла."""
        self._save_expansion_state()
        self.expansionStateChanged.emit(self.get_expansion_states())

    # --- Новые методы для сохранения и восстановления состояния развёрнутости ---
    def _save_expansion_state(self):
        """Сохраняет текущее состояние развёрнутости узлов."""
        self._expanded_parent_items.clear()
        self._expanded_periodic_items.clear()

        # Проходим по корневым элементам (уровень "О проекте", "П1.Пауза", ..., "Удаления", "Диапазоны", "Метки")
        for i in range(self.labels_tree.topLevelItemCount()):
            parent_item = self.labels_tree.topLevelItem(i)
            if parent_item and parent_item.isExpanded():
                parent_text = parent_item.text(0)
                self._expanded_parent_items.add(parent_text)

                # Проходим по дочерним элементам корневого элемента (например, "Сегмент", "Пауза", "Смена" внутри "Метки")
                # Сохраняем их состояние, если они развёрнуты.
                for j in range(parent_item.childCount()):
                    child_item = parent_item.child(j)
                    if child_item and child_item.isExpanded():
                         child_text = child_item.text(0)
                         # Для узлов типа "Сегмент", "Пауза", "Смена" под "Метки" и "ПX.Тип":
                         # Сохраняем их имя, чтобы при следующем update_tree они были развёрнуты.
                         self._expanded_periodic_items.add(child_text)

    def _restore_expansion_state(self):
        """Восстанавливает состояние развёрнутости узлов."""
        # Применяем сохранённые состояния из проекта, если они есть (приоритетнее текущих)
        if self._saved_expansion_states is not None:
            saved_parent_items = set(self._saved_expansion_states.get("parent_items", []))
            saved_periodic_items = set(self._saved_expansion_states.get("periodic_items", []))

            for i in range(self.labels_tree.topLevelItemCount()):
                parent_item = self.labels_tree.topLevelItem(i)
                if parent_item:
                    parent_text = parent_item.text(0)
                    parent_item.setExpanded(parent_text in saved_parent_items)

                    for j in range(parent_item.childCount()):
                        child_item = parent_item.child(j)
                        if child_item:
                            child_text = child_item.text(0)
                            child_item.setExpanded(child_text in saved_periodic_items)

            # Сбрасываем, чтобы не применять повторно при следующих обновлениях внутри сессии
            self._saved_expansion_states = None
            return

        # Стандартное восстановление из текущей сессии
        for i in range(self.labels_tree.topLevelItemCount()):
            parent_item = self.labels_tree.topLevelItem(i)
            if parent_item:
                parent_text = parent_item.text(0)
                parent_item.setExpanded(parent_text in self._expanded_parent_items)

                # Проходим по дочерним элементам корневого элемента и восстанавливаем их состояние
                for j in range(parent_item.childCount()):
                    child_item = parent_item.child(j)
                    if child_item:
                         child_text = child_item.text(0)
                         child_item.setExpanded(child_text in self._expanded_periodic_items)

    # --- Конец новых методов ---

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """
        Обработчик двойного клика по элементу дерева.
        Эмитирует сигнал labelSelected с global_time метки или rangeSelectedForPlayback с name диапазона.
        Для меток "Смена" дополнительно эмитирует shiftLabelDoubleClicked с context и global_time.
        """
        # Проверяем, является ли элемент дочерним (не родительским узлом "Метки" или "Диапазоны")
        if item.parent():
            # Получаем id объекта из QTreeWidgetItem (колонка 4)
            obj_id = self._get_obj_id_from_item(item)
            if obj_id is not None:
                # Проверяем, является ли это меткой или диапазоном, сравнивая с id в соответствующих списках
                # Сначала проверим списки, чтобы не искать в них каждый раз
                if self._generic_labels_ref:
                    for label in self._generic_labels_ref:
                        if id(label) == obj_id:
                            # Это метка
                            # Если это метка "Смена", эмитируем дополнительный сигнал
                            if label.label_type == "Смена" and label.context:
                                self.shiftLabelDoubleClicked.emit(label.context, label.global_time)
                            self.labelSelected.emit(label.global_time)
                            return # Выходим после обработки метки
                if self._calculated_ranges_ref:
                    for calc_range in self._calculated_ranges_ref:
                        if id(calc_range) == obj_id:
                            # Это диапазон
                            self.rangeSelectedForPlayback.emit(calc_range.name)
                            return # Выходим после обработки диапазона
        # Если элемент - родительский или id не найден, ничего не делаем

    def _get_obj_id_from_item(self, item: QTreeWidgetItem):
        """Получает id объекта из QTreeWidgetItem, хранящийся в колонке 4."""
        return item.data(4, 0) # Получаем id из колонки 4

    def _show_context_menu(self, position):
        """Показывает контекстное меню при правом клике."""
        item = self.labels_tree.itemAt(position)
        if item and item.parent(): # Проверяем, что клик был по дочернему элементу (конкретной метке или диапазону)
            # Сохраняем выбранный элемент для дальнейших действий
            self._current_context_item = item
            menu = QMenu()

            # Получаем id объекта из колонки 4
            obj_id = self._get_obj_id_from_item(item)
            if obj_id is not None:
                # Проверяем, является ли это меткой или диапазоном
                if self._generic_labels_ref:
                    for label in self._generic_labels_ref:
                        if id(label) == obj_id:
                            # Это метка - показываем действия для метки
                            menu.addAction(self.edit_action)
                            menu.addAction(self.delete_action)
                            if label.label_type == "Гол":
                                is_penalty = label.context.get("is_penalty_shot", False) if label.context else False
                                self.toggle_penalty_shot_action.setChecked(is_penalty)
                                menu.addAction(self.toggle_penalty_shot_action)
                            menu.exec_(self.labels_tree.viewport().mapToGlobal(position))
                            return # Выходим после показа меню для метки
                if self._calculated_ranges_ref:
                    for calc_range in self._calculated_ranges_ref:
                        if id(calc_range) == obj_id:
                            # Это диапазон - показываем действия для диапазона
                            menu.addAction(self.jump_to_range_action)
                            menu.exec_(self.labels_tree.viewport().mapToGlobal(position))
                            return # Выходим после показа меню для диапазона

    def _on_edit_requested(self):
        """Обработчик действия 'Установить текущее время плеера' из контекстного меню."""
        if not hasattr(self, '_current_context_item') or not self._current_context_item:
            return

        item = self._current_context_item
        # Получаем id объекта из колонки 4
        label_obj_id = self._get_obj_id_from_item(item)
        if label_obj_id is not None and self._video_player_ref:
            # Найдём метку по её id в списке self._generic_labels_ref
            for label in self._generic_labels_ref:
                if id(label) == label_obj_id:
                    # Получаем новое время из плеера (глобальное)
                    new_time = self._video_player_ref.get_current_time()
                    # Обновляем время метки
                    label.global_time = new_time
                    # Сортируем список меток по времени
                    self._generic_labels_ref.sort(key=lambda x: x.global_time)
                    # Обновляем дерево
                    self.update_tree(self._generic_labels_ref, self._calculated_ranges_ref, self._generic_labels_ref, self._calculated_ranges_ref, self._video_player_ref, self._save_callback)
                    # Вызываем сохранение
                    if self._save_callback:
                        self._save_callback()
                    break # Нашли и обновили, выходим из цикла

    def _on_delete_requested(self):
        """Обработчик действия 'Удалить' из контекстного меню."""
        if not hasattr(self, '_current_context_item') or not self._current_context_item:
            return

        item = self._current_context_item
        # Получаем id объекта из колонки 4
        label_obj_id = self._get_obj_id_from_item(item)
        if label_obj_id is not None:
            # Найдём метку по её id в списке self._generic_labels_ref
            label_to_remove = None
            for label in self._generic_labels_ref:
                if id(label) == label_obj_id:
                    label_to_remove = label
                    break

            if label_to_remove:
                # Удаляем метку из списка
                self._generic_labels_ref.remove(label_to_remove)
                # Обновляем дерево
                self.update_tree(self._generic_labels_ref, self._calculated_ranges_ref, self._generic_labels_ref, self._calculated_ranges_ref, self._video_player_ref, self._save_callback)
                # Вызываем сохранение
                if self._save_callback:
                    self._save_callback()

    # --- Новый метод для обработки Delete ---
    def _on_delete_requested_shortcut(self):
        """Обработчик нажатия клавиши Delete."""
        # Используем текущий выбранный элемент в tree widget
        current_item = self.labels_tree.currentItem()
        if current_item and current_item.parent(): # Проверяем, что выбран дочерний элемент (конкретная метка)
            # Сохраняем выбранный элемент как для контекстного меню
            self._current_context_item = current_item
            # Вызываем логику удаления
            self._on_delete_requested()
            # Убираем ссылку после использования
            self._current_context_item = None # Очищаем, чтобы избежать путаницы с контекстным меню

    # --- Новый метод для действия "Перейти к диапазону" ---
    def _on_jump_to_range_requested(self):
        """Обработчик действия 'Перейти к диапазону' из контекстного меню."""
        if not hasattr(self, '_current_context_item') or not self._current_context_item:
            return

        item = self._current_context_item
        # Получаем id объекта из колонки 4
        range_obj_id = self._get_obj_id_from_item(item)
        if range_obj_id is not None:
            # Найдём диапазон по его id в списке self._calculated_ranges_ref
            for calc_range in self._calculated_ranges_ref:
                if id(calc_range) == range_obj_id:
                    # Эмитируем сигнал для выбора диапазона в плеере
                    self.rangeSelectedForPlayback.emit(calc_range.name)
                    break # Нашли и вызвали сигнал, выходим из цикла

    def _on_toggle_penalty_shot(self):
        """Обработчик действия 'Это буллит' из контекстного меню."""
        if not hasattr(self, '_current_context_item') or not self._current_context_item:
            return

        item = self._current_context_item
        label_obj_id = self._get_obj_id_from_item(item)
        if label_obj_id is not None and self._generic_labels_ref:
            for label in self._generic_labels_ref:
                if id(label) == label_obj_id:
                    if label.label_type == "Гол":
                        if not label.context:
                            label.context = {}
                        label.context["is_penalty_shot"] = not label.context.get("is_penalty_shot", False)
                        self.update_tree(
                            self._generic_labels_ref,
                            self._calculated_ranges_ref,
                            self._generic_labels_ref,
                            self._calculated_ranges_ref,
                            self._video_player_ref,
                            self._save_callback,
                            self._rosters_ref
                        )
                        if self._save_callback:
                            self._save_callback()
                    break

    def _update_column_widths(self):
        """Вспомогательный метод для установки ширины колонок (опционально)."""
        # Если используется Fixed, можно установить ширину здесь
        # self.labels_tree.header().resizeSection(1, 40) # Пример ширины колонки "№"
        # self.labels_tree.header().resizeSection(3, 60) # Пример ширины колонки "Длительность"
        pass # Пока что используем ResizeToContents для колонки "№" и "Длительность"

# Конец содержимого файла: ui/labels_tree_widget.py