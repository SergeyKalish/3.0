"""
Модель данных для отчёта.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from utils.helpers import convert_global_to_official_time # Импортируем функцию для перевода времени

# Константа для имени нашей команды
OUR_TEAM_NAME = "Созвездие 2014"

@dataclass
class PlayerShift:
    """
    Вспомогательный класс для хранения информации о смене (копия из models.py).
    """
    number: int
    start_time: float
    end_time: float

@dataclass
class PlayerShiftInfo:
    """
    Вспомогательный класс для хранения информации об игроке и его сменах (копия из models.py).
    """
    id_fhm: str
    name: str
    shifts: List[PlayerShift]

class PlayerInfo:
    """
    Вспомогательный класс для хранения информации об игроке (для отчёта).
    """
    def __init__(self, player_id: str, number: str, full_name: str, role: str, lineup_group: str = "", lineup_position: str = ""):
        self.player_id = str(player_id)
        self.number = str(number)
        self.full_name = str(full_name)
        self.role = str(role)
        self.lineup_group = str(lineup_group)  # <-- Новое поле
        self.lineup_position = str(lineup_position)  # <-- Новое поле

class ShiftInfo:
    """
    Вспомогательный класс для хранения информации о смене (для отчёта).
    """
    def __init__(self, official_start: float, official_end: float, number: int): # <-- Добавлен number
        self.official_start = official_start
        self.official_end = official_end
        self.number = number # <-- Сохраняем номер
        # Длительность в официальном времени
        self.duration = self.official_end - self.official_start

class GoalInfo:
    """
    Вспомогательный класс для хранения информации о голе.
    """
    def __init__(self, official_time: float, context: Dict[str, Any]):
        self.event_type = "Goal"
        self.official_time = official_time
        self.context = context # Содержит, например, 'player_name', 'assist_1', 'assist_2', 'team', 'score'

class PenaltyInfo:
    """
    Вспомогательный класс для хранения информации об удалении.
    """
    def __init__(self, official_start: float, official_end: float, player_name: str, violation_type: str, player_id_fhm: str):
        self.event_type = "Penalty"
        self.official_start = official_start
        self.official_end = official_end
        self.player_name = player_name
        self.violation_type = violation_type
        self.player_id_fhm = player_id_fhm

class SegmentInfo:
    """
    Вспомогательный класс для хранения информации о сегменте (периоде).
    """
    def __init__(self, name: str, official_start: float, official_end: float):
        self.name = name
        self.official_start = official_start
        self.official_end = official_end

class ReportData:
    """
    Класс для извлечения и хранения данных из project.match,
    необходимых для генерации отчёта.
    """

    def __init__(self, original_project):
        """
        :param original_project: объект project, загруженный из .hkt
        """
        self.original_project = original_project
        self.our_team_key: Optional[str] = None
        self.players_list: List[PlayerInfo] = []
        self.shifts_by_player_id: Dict[str, List[ShiftInfo]] = {}
        self.segments_info: List[SegmentInfo] = [] # Заменено chii_periods
        self.goals: List[GoalInfo] = []
        self.penalties: List[PenaltyInfo] = []
        # self.events: List[EventInfo] = [] # Больше не используется, заменено на goals и penalties
        self.game_modes: List[Any] = [] # Пока сырые данные
        self.active_penalties: List[Any] = [] # Пока сырые данные

        self._extract_and_validate_data()

    def _extract_and_validate_data(self):
        """
        Извлекает и валидирует данные из original_project.
        """
        match_obj = self.original_project.match

        # 1. Определение our_team_key
        teams = getattr(match_obj, 'teams', {})
        if OUR_TEAM_NAME not in teams.values():
            raise ValueError(f"Команда '{OUR_TEAM_NAME}' не найдена в проекте.")

        # Находим ключ (f-team или s-team), соответствующий OUR_TEAM_NAME
        self.our_team_key = None
        for key, name in teams.items():
            if name == OUR_TEAM_NAME:
                self.our_team_key = key
                break

        if not self.our_team_key:
             # Это маловероятно, если проверка выше прошла, но на всякий случай
            raise ValueError(f"Не удалось определить ключ для команды '{OUR_TEAM_NAME}'.")

        print(f"Ключ нашей команды: {self.our_team_key} ({teams.get(self.our_team_key)})")

        # 2. Извлечение rosters для нашей команды
        rosters = getattr(match_obj, 'rosters', {})
        our_team_roster_raw = rosters.get(self.our_team_key, [])
        if not our_team_roster_raw:
            raise ValueError(f"Состав игроков для нашей команды ({self.our_team_key}) отсутствует в rosters.")

        # Преобразование в список PlayerInfo
        self.players_list = []
        for player_data in our_team_roster_raw:
            # Пример структуры из файла: {'id_fhm': '8962', 'number': '77', 'name': 'Арнаут Иван', 'role': 'Нападающий', ...}
            p_id = player_data.get('id_fhm') # <-- Правильный ключ!
            p_num = str(player_data.get('number', '')) # <-- Правильная версия
            # В ТЗ указано Ф.И.О. в формате "Фамилия И." или "Фамилия Имя".
            # Поле 'name' в файле: "Арнаут Иван" -> "Арнаут И." -> "Иван Арнаут" ?
            full_name_raw = player_data.get('name', 'Игрок Безымянный')
            # Пробуем преобразовать "Фамилия Имя" в "Фамилия И."
            name_parts = full_name_raw.split(' ', 1) # Разделяем максимум на 2 части
            if len(name_parts) >= 2:
                # name_parts[0] теперь "Фамилия", name_parts[1] теперь "Имя Остальное..."
                surname = name_parts[0]
                first_name_part = name_parts[1] # "Имя Остальное..."
                # Берём первую букву из "Имя Остальное..." и добавляем точку
                first_initial = first_name_part[0] + "." if first_name_part else ""
                # Формируем "Фамилия И."
                formatted_name = f"{surname} {first_initial}"
            else:
                # Если формат не "Фамилия Имя", оставляем как есть
                formatted_name = full_name_raw

            p_name = str(formatted_name) # <-- ИСПРАВЛЕНО: гарантируем строку
            p_role = str(player_data.get('role', '')) # <-- ИСПРАВЛЕНО: гарантируем строку

            # --- НОВОЕ: Извлекаем lineup_group и lineup_position из rosters ---
            p_lineup_group = str(player_data.get('lineup_group', ''))
            p_lineup_position = str(player_data.get('lineup_position', ''))
            # --- КОНЕЦ НОВОГО ---

            # Теперь p_id может быть не None
            if p_id:
                # --- ИСПРАВЛЕНО: Добавлены p_lineup_group, p_lineup_position в PlayerInfo ---
                self.players_list.append(PlayerInfo(p_id, p_num, p_name, p_role, p_lineup_group, p_lineup_position))
                # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
            else:
                # Логируем, если игрок без id_fhm, хотя по структуре он должен быть
                print(f"Предупреждение: Игрок в rosters команды {self.our_team_key} не имеет id_fhm: {player_data}")


        if not self.players_list:
            raise ValueError(f"Не удалось извлечь действительных игроков для нашей команды из rosters.")

        # --- НОВОЕ: Извлечение player_shifts_official_timer для нашей команды ---
        # Попробуем получить сначала с уровня match
        match_obj = self.original_project.match
        player_shifts_ot_full = getattr(match_obj, 'player_shifts_official_timer', None)

        if player_shifts_ot_full is None or not player_shifts_ot_full:
            raise ValueError("Данные player_shifts_official_timer отсутствуют в проекте. Невозможно сгенерировать отчёт.")

        # Извлекаем смены ТОЛЬКО для наших игроков
        self.shifts_by_player_id = {}
        players_with_shifts_count = 0
        for player_info_obj in self.players_list:
            player_id = player_info_obj.player_id
            # player_shifts_ot_full хранит объекты PlayerShiftInfo
            player_shift_info_obj = player_shifts_ot_full.get(player_id)
            # --- ИСПРАВЛЕНО: Инициализируем player_shifts_list снаружи if ---
            player_shifts_list = []
            if player_shift_info_obj:
                # player_shift_info_obj - это гарантированно объект PlayerShiftInfo (из файла)
                # Извлекаем смены из объекта PlayerShiftInfo
                # !! СОРТИРУЕМ СМЕНЫ ПО ВРЕМЕНИ ПЕРЕД ОБРАБОТКОЙ !!
                shifts_to_process = sorted(player_shift_info_obj.shifts, key=lambda s: s.start_time) # start_time здесь - это official_start
                for shift_obj in shifts_to_process: # <-- Теперь проходим по отсортированным сменам
                     # shift_obj - это объект PlayerShift
                     # start_time и end_time в shift_obj уже являются official_start и official_end
                     o_start = shift_obj.start_time
                     o_end = shift_obj.end_time
                     # --- ИСПРАВЛЕНО: Передаём shift_obj.number в ShiftInfo ---
                     shift_info_obj = ShiftInfo(o_start, o_end, shift_obj.number) # <-- Передаём number
                     # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
                     player_shifts_list.append(shift_info_obj) # <-- Добавляем в список, определённый выше

                if player_shifts_list: # Если у игрока есть хотя бы одна смена
                    players_with_shifts_count += 1
            # else: # Не нужен, player_shifts_list уже пустой
            #     player_shifts_list = [] # Уже инициализирован как пустой выше

            # Теперь строка может использовать player_shifts_list
            self.shifts_by_player_id[player_id] = player_shifts_list
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---


        # --- ИСПРАВЛЕНА ВАЛИДАЦИЯ ---
        # Валидация: хотя бы у одного игрока из списка должны быть смены
        if players_with_shifts_count == 0:
             raise ValueError("У всех игроков нашей команды отсутствуют смены (player_shifts_official_timer).")
        else:
            print(f"Найдены смены для {players_with_shifts_count} игроков из {len(self.players_list)}.")
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Сортировка self.players_list по сложной логике (ПОСЛЕ извлечения self.shifts_by_player_id) ---
        # 1. Извлекаем время первой смены для каждого игрока
        first_shift_times = {}
        for player_info in self.players_list:
            player_id = player_info.player_id
            player_shifts = self.shifts_by_player_id.get(player_id, [])
            if player_shifts:
                # Берём official_start первой смены (уже отсортированной)
                first_shift_time = player_shifts[0].official_start
            else:
                # Если у игрока нет смен, ставим бесконечность, чтобы он был в конце
                first_shift_time = float('inf')
            first_shift_times[player_id] = first_shift_time

        # 2. Определяем приоритет для сортировки внутри группы с одинаковым временем
        def get_position_priority(role_str, group_str, position_str):
            """
            Определяет приоритет позиции для сортировки внутри группы с одинаковым временем первой смены.
            """
            # Приводим к нижнему регистру для гибкости
            # role_lower = role_str.lower() # Не используется напрямую для приоритета, полагаемся на group_str
            group_lower = group_str.lower()
            pos_lower = position_str.lower()

            # Проверяем тип группы (пара/тройка)
            is_defender_line = "пар" in group_lower  # "пара", "пары", "парой" и т.д.
            is_forward_line = "тро" in group_lower   # "тройка", "тройки", "тройкой" и т.д.

            # Проверяем позицию
            is_center = 'центр' in pos_lower or 'ц' == pos_lower
            is_left = 'лев' in pos_lower
            is_right = 'прав' in pos_lower

            # Правила сортировки внутри "одинакового времени":
            # 1. Центр (для нападающих)
            # 2. Левый (нападающий или защитник)
            # 3. Правый (нападающий или защитник)
            # 4. Левый защитник (если нужно отличать от нападающего)
            # 5. Правый защитник (если нужно отличать от нападающего)

            # Если это тройка (нападающие)
            if is_forward_line:
                if is_center:
                    return 0  # Центр первый
                elif is_left:
                    return 1  # Левый нападающий второй
                elif is_right:
                    return 2  # Правый нападающий третий
                else:
                    return 999 # Fallback для неузнанной позиции в тройке

            # Если это пара (защитники)
            elif is_defender_line:
                if is_left:
                    return 3  # Левый защитник четвёртый
                elif is_right:
                    return 4  # Правый защитник пятый
                else:
                    return 999 # Fallback для неузнанной позиции в паре

            # Если группа не "пара" и не "тройка", или позиция не распознана
            return 999


        def get_sort_key(player_info):
            # 1. Приоритет роли: Вратари (0), остальные (1)
            is_goalie = 0 if player_info.role.lower().startswith('вратарь') else 1

            # 2. Время первой смены (главный приоритет для не-вратарей)
            fst = first_shift_times[player_info.player_id]

            # 3. Приоритет позиции (Центр, Левый, Правый) - используется ТОЛЬКО если fst совпадает
            pos_prio = 999 # Fallback
            if not player_info.role.lower().startswith('вратарь'):
                # Используем lineup_group и lineup_position для приоритета
                pos_prio = get_position_priority(player_info.role, player_info.lineup_group, player_info.lineup_position)

            # Кортеж для сортировки: (вратарь?, время_первой_смены, приоритет_позиции, номер_игрока)
            # lineup_group НЕ используется как отдельное поле в сортировке, только для определения типа линии.
            return (is_goalie, fst, pos_prio, int(player_info.number) if player_info.number.isdigit() else float('inf'))

        # --- ДОБАВЛЕННЫЙ ОТЛАДОЧНЫЙ ВЫВОД ---
        print("--- DEBUG: Players BEFORE sorting (after shifts loaded) ---")
        for idx, p in enumerate(self.players_list):
             sort_key = get_sort_key(p)
             print(f"{idx+1:2d}. #{p.number:>3} {p.full_name:<15} (Role: {p.role}, Pos: {p.lineup_position}) | Key: {sort_key}")
        print("------------------------------------")
        # --- КОНЕЦ ДОБАВЛЕННОГО ОТЛАДОЧНОГО ВЫВОДА ---

        # 3. Сортируем список игроков
        # Используем новую функцию get_sort_key
        self.players_list.sort(key=get_sort_key)

        # --- ДОБАВЛЕННЫЙ ОТЛАДОЧНЫЙ ВЫВОД ---
        print("--- DEBUG: Players AFTER sorting ---")
        for idx, p in enumerate(self.players_list):
             sort_key = get_sort_key(p)
             print(f"{idx+1:2d}. #{p.number:>3} {p.full_name:<15} (Role: {p.role}, Pos: {p.lineup_position}) | Key: {sort_key}")
        print("-----------------------------------")
        # --- КОНЕЦ ДОБАВЛЕННОГО ОТЛАДОЧНОГО ВЫВОДА ---

        print(f"Извлечено и отсортировано {len(self.players_list)} игроков для отчёта.")


        # (остальной код метода без изменений: извлечение сегментов, голов, удалений и т.д.)

        # 4. Извлечение calculated_ranges для "Сегментов" (периодов)
        calculated_ranges = getattr(match_obj, 'calculated_ranges', [])
        segment_ranges_raw = [cr for cr in calculated_ranges if getattr(cr, 'label_type', '') == 'Сегмент']
        if not segment_ranges_raw:
            print("Предупреждение: Не найдены calculated_ranges с label_type 'Сегмент'.")
            # Логично будет предположить, что если нет сегментов, то и period_on_sheet не имеет смысла.
            # Но для базовой функциональности можно оставить пустой список.
            self.segments_info = []
        else:
            # Сортировка по времени начала
            segment_ranges_raw.sort(key=lambda x: x.start_time)

            # Преобразование в список SegmentInfo с официальным временем
            self.segments_info = []
            for cr in segment_ranges_raw:
                seg_name = cr.name # Используем имя сегмента
                # Преобразуем start_time и end_time сегмента в официальное время
                official_start = convert_global_to_official_time(cr.start_time, calculated_ranges)
                official_end = convert_global_to_official_time(cr.end_time, calculated_ranges)
                if official_start is not None and official_end is not None:
                    self.segments_info.append(SegmentInfo(seg_name, official_start, official_end))
                else:
                    # Если границы сегмента не попали в ЧИИ, это может быть артефакт или ошибка в данных.
                    # Логируем и пропускаем.
                    print(f"Предупреждение: Сегмент '{seg_name}' ({cr.start_time}, {cr.end_time}) не попал полностью в ЧИИ. Пропущен.")

        print(f"Найдено {len(self.segments_info)} сегментов (периодов).")


        # 5. Извлечение generic_labels (только голы) -> преобразование в GoalInfo
        generic_labels = getattr(match_obj, 'generic_labels', [])
        goals_raw = [label for label in generic_labels if getattr(label, 'label_type', '') == 'Гол']

        goals_processed = []
        for label in goals_raw:
            global_time = getattr(label, 'global_time', None)
            context = getattr(label, 'context', {})

            if global_time is not None:
                # Преобразуем global_time в official_time
                # Используем готовую функцию из utils.helpers
                try:
                    official_time = convert_global_to_official_time(global_time, calculated_ranges)
                except Exception as e:
                    print(f"Предупреждение: Не удалось преобразовать global_time {global_time} гола в official_time: {e}")
                    continue # Пропускаем событие, если не удалось преобразовать

                if official_time is not None: # Убедимся, что перевод прошёл успешно
                    goals_processed.append(GoalInfo(official_time, context))
                else:
                    # convert_global_to_official_time мог вернуть None
                    print(f"Предупреждение: global_time {global_time} гола не попало в ЧИИ, событие пропущено.")

        # Сортировка голов по времени
        goals_processed.sort(key=lambda x: x.official_time)
        self.goals = goals_processed

        print(f"Извлечено {len(self.goals)} голов.")


        # 6. Извлечение calculated_ranges (удаления из game_mode) -> преобразование в PenaltyInfo
        game_mode_ranges_raw = [cr for cr in calculated_ranges if getattr(cr, 'label_type', '') == 'game_mode']

        penalties_processed = []
        for cr in game_mode_ranges_raw:
            # Проверяем, есть ли активные штрафы в context
            active_penalties_ctx = cr.context.get('active_penalties', [])
            for penalty_data in active_penalties_ctx:
                # Проверяем, принадлежит ли игрок нашему ключу команды
                penalty_team_key = penalty_data.get('team')
                if penalty_team_key == self.our_team_key:
                    # Извлекаем данные
                    player_name = penalty_data.get('player_name', 'Unknown Player')
                    player_id_fhm = penalty_data.get('player_id_fhm')
                    violation_type = penalty_data.get('violation_type', 'Unknown Violation')

                    # Преобразуем start_time и end_time интервала game_mode (удаления) в официальное время
                    try:
                        official_start = convert_global_to_official_time(cr.start_time, calculated_ranges)
                        official_end = convert_global_to_official_time(cr.end_time, calculated_ranges)
                    except Exception as e:
                        print(f"Предупреждение: Не удалось преобразовать время удаления игрока {player_name} ({player_id_fhm}) в official_time: {e}")
                        continue

                    if official_start is not None and official_end is not None:
                         penalties_processed.append(PenaltyInfo(official_start, official_end, player_name, violation_type, player_id_fhm))
                    else:
                        print(f"Предупреждение: Время удаления игрока {player_name} ({player_id_fhm}) не попало в ЧИИ, событие пропущено.")

        # Сортировка удалений по времени начала
        penalties_processed.sort(key=lambda x: x.official_start)
        self.penalties = penalties_processed

        print(f"Извлечено {len(self.penalties)} удалений нашей команды.")


        # 7. Извлечение game_modes и active_penalties (пока для справки, может понадобиться позже)
        # Эти данные могут быть в формате, отличном от calculated_ranges или generic_labels
        # Пока просто сохраняем, если они есть
        self.game_modes = getattr(match_obj, 'game_modes', [])
        self.active_penalties = getattr(match_obj, 'active_penalties', [])


        # --- Валидация завершена ---
        print("Данные успешно извлечены и прошли валидацию для отчёта.")
