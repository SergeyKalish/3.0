# modules/smart.py

# ... (остальные импорты) ...
import uuid
from typing import List, Dict, Tuple, Set, Optional # <-- Добавлен Optional # <-- Убедитесь, что Dict, List, Set, Tuple импортированы
from model.project import GenericLabel, CalculatedRange, PlayerShift, PlayerShiftInfo # <-- Убедитесь, что PlayerShift, PlayerShiftInfo импортированы
from utils.helpers import create_official_time_map, map_global_time_to_official # <-- Импортируем новые функции
# ... (остальные импорты) ...

class SMARTProcessor:
    """
    Модуль для анализа накопленных generic_labels и формирования calculated_ranges.
    """
    def __init__(self):
        # Здесь можно хранить параметры анализа, если они понадобятся в будущем
        pass

    def process(self, generic_labels: List[GenericLabel], total_duration_sec: float) -> List[CalculatedRange]:
        """
        Основной метод анализа.
        Принимает список актуальных GenericLabel из проекта и общую длительность видео.
        Удаляет все существующие calculated_ranges и формирует новые на основе анализа текущих меток.
        Всегда формирует CalculatedRange "Всё видео" первым.
        Возвращает список новых CalculatedRange.
        """
        # --- Логика SMART ---
        calculated_ranges = []

        # 0. Всегда создаём "Всё видео" первым
        all_video_range_id = str(uuid.uuid4())
        all_video_range = CalculatedRange(
            id=all_video_range_id,
            name="Всё видео",
            label_type="Всё видео", # Возможно, стоит использовать специальный тип или оставить как есть
            start_time=0.0,
            end_time=total_duration_sec,
            source_label_ids=[] # Нет исходных меток для "всего видео"
        )
        calculated_ranges.append(all_video_range)
        # ---

        # --- Новое: Обработка парных меток "Удаление" ---
        # Словарь: frozenset(context_items) -> список global_time меток
        penalty_context_to_times = {}
        for label in generic_labels:
            if label.label_type == "Удаление" and label.context:
                # Используем frozenset(items()) для создания неизменяемого хэшируемого ключа из словаря context
                context_key = frozenset(label.context.items())
                if context_key not in penalty_context_to_times:
                    penalty_context_to_times[context_key] = []
                penalty_context_to_times[context_key].append(label.global_time)

        # Проходим по собранному словарю
        for context_key, times_list in penalty_context_to_times.items():
            # Сортируем времена для данной группы меток
            sorted_times = sorted(times_list)
            # Обрабатываем пары (чётный индекс - start, нечётный - end)
            for i in range(0, len(sorted_times) - 1, 2):
                start_time = sorted_times[i]
                end_time = sorted_times[i + 1]

                # Создаём CalculatedRange для пары
                penalty_range_id = str(uuid.uuid4())
                # Восстанавливаем оригинальный словарь context из frozenset
                original_context = dict(context_key)
                penalty_range_name = f"Удаление {original_context.get('player_name', 'Unknown')} ({original_context.get('violation_type', 'Unknown')})"
                penalty_range = CalculatedRange(
                    id=penalty_range_id,
                    name=penalty_range_name,
                    label_type="Удаление",
                    start_time=start_time,
                    end_time=end_time,
                    source_label_ids=[], # Источник - пара меток, можно не заполнять или заполнять IDs пары
                    context=original_context # Сохраняем оригинальный context
                )
                calculated_ranges.append(penalty_range)
        # --- Конец нового ---

        # 1. Обработка "Сегментов":
        #    - Найти пары меток "Сегмент" (нечётный индекс - начало, чётный - конец, сортировка по времени).
        #    - Создать CalculatedRange с типом "Сегмент", именем "Период X" (по порядку времени начала).
        #      (X - номер периода по порядку времени начала).
        #    - Сохранить временные диапазоны сегментов для последующего использования.
        segment_labels = [label for label in generic_labels if label.label_type == "Сегмент"]
        segment_labels.sort(key=lambda x: x.global_time) # Сортировка по времени

        segment_ranges = []
        for i in range(0, len(segment_labels) - 1, 2): # Начало (i), Конец (i+1)
            start_label = segment_labels[i]
            end_label = segment_labels[i + 1] if i + 1 < len(segment_labels) else None

            if end_label and end_label.global_time > start_label.global_time:
                range_id = str(uuid.uuid4())
                period_num = len(segment_ranges) + 1 # Номер периода после "Всё видео"
                name = f"Период {period_num}"
                new_range = CalculatedRange(
                    id=range_id,
                    name=name,
                    label_type="Сегмент",
                    start_time=start_label.global_time,
                    end_time=end_label.global_time,
                    source_label_ids=[start_label.id, end_label.id]
                )
                calculated_ranges.append(new_range) # Добавляем в общий список после "Всё видео"
                segment_ranges.append(new_range) # Сохраняем для обработки пауз и ЧИИ
            # Если метка начала есть, но конца нет, она игнорируется для формирования диапазона
            
        # --- Новое: Присвоение period_name меткам "Пауза" и "Смена" ---
        # Сначала определим, к какому периоду принадлежит каждая метка "Пауза" и "Смена"
        SPECIAL_LABEL_TYPES = {"Пауза", "Смена"} # Определим типы, для которых нужно присваивать период
        for label in generic_labels:
            if label.label_type in SPECIAL_LABEL_TYPES:
                # Сбросим period_name на случай, если метка была в старом проекте
                if label.context is None:
                    label.context = {}
                # Удалим старый ключ, если он был
                label.context.pop("period_name", None)

                # Найдём сегмент, которому принадлежит метка
                for seg_range in segment_ranges:
                    if seg_range.start_time <= label.global_time <= seg_range.end_time:
                        # Присвоим имя сегмента как period_name
                        label.context["period_name"] = seg_range.name
                        break # Нашли сегмент, выходим из цикла по сегментам для этой метки
                # Если цикл завершился без break, period_name останется None или не будет установлен
        # --- Конец нового ---

        # 2. Обработка "Пауз" (только если есть хотя бы один "Сегмент"):
        #    - Найти метки "Пауза", сортировка по времени.
        #    - Проверить, находятся ли метки "Пауза" внутри диапазонов "Сегментов".
        #    - Сформировать пары "Пауза" (нечётный индекс - начало, чётный - конец для пауз *внутри сегмента*).
        #    - Создать внутреннюю структуру (например, PauseCalculatedRange) для хранения временных диапазонов пауз.
        #      (Эти диапазоны не входят в итоговый список CalculatedRange).
        pause_labels = [label for label in generic_labels if label.label_type == "Пауза"]
        pause_labels.sort(key=lambda x: x.global_time) # Сортировка по времени

        pause_ranges_by_segment: Dict[str, List[CalculatedRange]] = {} # Словарь: id сегмента -> [PauseCalculatedRange]

        if segment_ranges:
            for i in range(0, len(pause_labels) - 1, 2): # Начало (i), Конец (i+1)
                start_label = pause_labels[i]
                end_label = pause_labels[i + 1] if i + 1 < len(pause_labels) else None

                if end_label and end_label.global_time > start_label.global_time:
                    # Проверяем, в каком сегменте находится эта пауза
                    for seg_range in segment_ranges:
                        if seg_range.start_time <= start_label.global_time <= seg_range.end_time and \
                           seg_range.start_time <= end_label.global_time <= seg_range.end_time:
                            # Пауза полностью внутри сегмента
                            pause_range_id = str(uuid.uuid4())
                            pause_range_obj = CalculatedRange(
                                id=pause_range_id,
                                name=f"Пауза в {seg_range.name}", # Имя для внутреннего использования
                                label_type="Пауза",
                                start_time=start_label.global_time,
                                end_time=end_label.global_time,
                                source_label_ids=[start_label.id, end_label.id]
                            )
                            if seg_range.id not in pause_ranges_by_segment:
                                pause_ranges_by_segment[seg_range.id] = []
                            pause_ranges_by_segment[seg_range.id].append(pause_range_obj)
                            break # Нашли сегмент, выходим из цикла по сегментам для этой паузы

        # 3. Обработка "ЧИИ" (на основе "Сегментов" и "Пауз"):
        #    - Для каждого CalculatedRange "Сегмент":
        #        - Получить его start_time и end_time.
        #        - Найти все PauseCalculatedRange, которые пересекаются с этим "Сегментом".
        #        - Вычесть временные диапазоны пауз из диапазона "Сегмента".
        #        - Полученные оставшиеся интервалы - это ЧИИ.
        #    - Для каждого найденного интервала ЧИИ:
        #        - Создать CalculatedRange с типом "ЧИИ", именем "Период X. ЧИИ №Y" (Y - номер ЧИИ в сегменте X).
        #        - Добавить в итоговый список.
        chi_ranges_by_segment: Dict[str, List[CalculatedRange]] = {} # Словарь: id сегмента -> [CalculatedRange ЧИИ]
        for seg_range in segment_ranges:
            seg_start = seg_range.start_time
            seg_end = seg_range.end_time

            # Получаем паузы для этого сегмента
            pauses_in_seg = pause_ranges_by_segment.get(seg_range.id, [])
            pauses_in_seg.sort(key=lambda x: x.start_time) # Сортировка пауз в сегменте по времени

            # Найдём интервалы "ЧИИ" внутри сегмента, вычитая паузы
            chi_intervals = []
            current_start = seg_start
            for pause_range in pauses_in_seg:
                if pause_range.start_time > current_start:
                    # Есть интервал до паузы - это ЧИИ
                    chi_intervals.append((current_start, pause_range.start_time))
                current_start = max(current_start, pause_range.end_time) # Следующий интервал начинается после паузы

            # Проверяем остаток после последней паузы до конца сегмента
            if current_start < seg_end:
                chi_intervals.append((current_start, seg_end))

            # Создаём CalculatedRange для каждого интервала ЧИИ
            chi_ranges_for_this_segment = []
            for i, (chi_start, chi_end) in enumerate(chi_intervals):
                if chi_end > chi_start: # Убедимся, что интервал не пустой
                    chi_range_id = str(uuid.uuid4())
                    chi_num = i + 1
                    name = f"{seg_range.name}. ЧИИ №{chi_num}"
                    chi_range = CalculatedRange(
                        id=chi_range_id,
                        name=name,
                        label_type="ЧИИ",
                        start_time=chi_start,
                        end_time=chi_end,
                        source_label_ids=seg_range.source_label_ids # Пока что связываем с метками сегмента
                    )
                    calculated_ranges.append(chi_range) # Добавляем в общий список
                    chi_ranges_for_this_segment.append(chi_range) # Сохраняем для создания суммы ЧИИ

            chi_ranges_by_segment[seg_range.id] = chi_ranges_for_this_segment


        # --- НОВЫЙ БЛОК: Обработка "Счёта игры" ---
        # Извлекаем все метки "Гол" с валидным context
        goal_labels = []
        for label in generic_labels:
             if label.label_type == "Гол" and label.context and isinstance(label.context, dict):
                 # Проверим наличие необходимых ключей в context
                 if "team" in label.context:
                     goal_labels.append(label)
                 else:
                     # Логируем или игнорируем метку без необходимых данных в context
                     print(f"Предупреждение: Метка 'Гол' (id: {label.id}) имеет context, но не содержит 'team'. Игнорируется.")
        # Сортируем метки "Гол" по времени
        goal_labels.sort(key=lambda x: x.global_time)

        # Для каждого сегмента вычисляем счёт
        current_home_score = 0
        current_away_score = 0
        for seg_range in segment_ranges:
            seg_start = seg_range.start_time
            seg_end = seg_range.end_time

            # Находим голы, принадлежащие этому сегменту
            goals_in_segment = [gl for gl in goal_labels if seg_start <= gl.global_time <= seg_end]

            previous_time = seg_start
            # Счёт в начале сегмента равен итоговому счёту предыдущего сегмента (или 0:0 для первого)
            # current_home_score и current_away_score уже содержат счёт на начало этого сегмента

            for goal_label in goals_in_segment:
                # 1. Создаём диапазон с предыдущим счётом от previous_time до времени гола
                if goal_label.global_time > previous_time:
                    score_range_id = str(uuid.uuid4())
                    score_name = f"{current_home_score}:{current_away_score}"
                    score_range = CalculatedRange(
                        id=score_range_id,
                        name=score_name,
                        label_type="Счёт",
                        start_time=previous_time,
                        end_time=goal_label.global_time,
                        source_label_ids=[] # Можно добавить id метки гола, если нужно
                    )
                    calculated_ranges.append(score_range)

                # 2. Обновляем счёт
                goal_team = goal_label.context.get("team", "") # team извлекается из context метки "Гол"
                if goal_team == "f-team": # Предполагаем, что f-team - Home
                    current_home_score += 1
                elif goal_team == "s-team": # s-team - Away
                    current_away_score += 1
                # Игнорируем гол, если команда не определена или неизвестна

                # 3. Обновляем previous_time
                previous_time = goal_label.global_time

            # 4. Создаём финальный диапазон счёта для оставшегося времени в сегменте (от последнего гола до конца сегмента)
            if seg_end > previous_time:
                final_score_range_id = str(uuid.uuid4())
                final_score_name = f"{current_home_score}:{current_away_score}"
                final_score_range = CalculatedRange(
                    id=final_score_range_id,
                    name=final_score_name,
                    label_type="Счёт",
                    start_time=previous_time,
                    end_time=seg_end,
                    source_label_ids=[] # Можно добавить id метки последнего гола в сегменте, если нужно
                )
                calculated_ranges.append(final_score_range)

        # После обработки всех сегментов, current_home_score и current_away_score содержат итоговый счёт матча
        # (хотя этот итоговый счёт не создаёт отдельного CalculatedRange за пределами сегментов)

        # --- КОНЕЦ НОВОГО БЛОКА ---



        # === НОВЫЙ БЛОК: РАСЧЁТ "РЕЖИМ ИГРЫ" (game_mode) ===
        game_mode_ranges: List[CalculatedRange] = []

        # Получаем из уже сформированного списка все "Сегменты" и "Удаления"
        segment_calc_ranges = [cr for cr in calculated_ranges if cr.label_type == "Сегмент"]
        penalty_calc_ranges = [cr for cr in calculated_ranges if cr.label_type == "Удаление"] # <-- Берутся "Удаления", созданные ранее

        for seg in segment_calc_ranges:
            seg_start = seg.start_time
            seg_end = seg.end_time

            # Список событий: (время, тип_события, команда, player_name, penalty_range_id, player_id_fhm, violation_type)
            events: List[Tuple[float, str, str, str, str, str, str]] = []

            # Собираем все события "Удаления", пересекающиеся с этим сегментом
            for penalty in penalty_calc_ranges: # <-- penalty - это CalculatedRange("Удаление")
                if penalty.end_time <= seg_start or penalty.start_time >= seg_end:
                    continue # Штраф не пересекается с сегментом

                team = penalty.context.get("team", "unknown")
                player_name = penalty.context.get("player_name", "Unknown Player")
                player_id_fhm = penalty.context.get("player_id_fhm", "unknown_id")
                violation_type = penalty.context.get("violation_type", "Unknown Violation") # <-- Получаем violation_type из context CalculatedRange("Удаление")
                penalty_id = penalty.id

                # Добавляем события начала и конца штрафа, включая violation_type
                events.append((max(penalty.start_time, seg_start), "start", team, player_name, penalty_id, player_id_fhm, violation_type)) # <-- Добавлен violation_type
                events.append((min(penalty.end_time, seg_end), "end", team, player_name, penalty_id, player_id_fhm, violation_type)) # <-- Добавлен violation_type

            # Добавляем граничные события сегмента (фиктивные значения для последних четырёх полей)
            events.append((seg_start, "boundary", "none", "none", "none", "none", "none")) # <-- 7 элементов
            events.append((seg_end, "boundary", "none", "none", "none", "none", "none")) # <-- 7 элементов

            # Сортируем события по времени
            events.sort(key=lambda x: x[0])

            # Состояние: словарь penalty_id -> информация о штрафе (теперь с violation_type)
            # !!! Исправлен тип для хранения violation_type !!!
            active_penalties: Dict[str, Dict[str, str]] = {}
            current_time = seg_start

            # Проходим по всем событиям и формируем интервалы
            # !!! Исправлено количество переменных в распаковке кортежа !!!
            for i, (event_time, event_type, team, player_name, penalty_id, player_id_fhm_from_event, violation_type_from_event) in enumerate(events):
                # Если между текущим временем и временем события есть интервал, фиксируем его
                if event_time > current_time:
                    # Собираем информацию о всех активных штрафах для context
                    active_penalties_info = []
                    for pid, info in active_penalties.items():
                        active_penalties_info.append({
                            "team": info["team"],
                            "player_name": info["player_name"],
                            "player_id_fhm": info["player_id_fhm"],
                            "violation_type": info["violation_type"] # <-- Добавляем violation_type в active_penalties_info
                        })

                    # Определяем числовой состав
                    f_team_players = 5 - sum(1 for p in active_penalties.values() if p["team"] == "f-team")
                    s_team_players = 5 - sum(1 for p in active_penalties.values() if p["team"] == "s-team")

                    game_mode_name = f"{f_team_players} на {s_team_players}"
                    game_mode_range_id = str(uuid.uuid4())
                    # Создаём CalculatedRange с context
                    new_range = CalculatedRange(
                        id=game_mode_range_id,
                        name=game_mode_name,
                        label_type="game_mode",
                        start_time=current_time,
                        end_time=event_time,
                        source_label_ids=[], # Можно оставить пустым или заполнить при необходимости
                        context={"active_penalties": active_penalties_info} # <-- Записываем контекст с violation_type
                    )
                    game_mode_ranges.append(new_range)

                # Обновляем состояние активных штрафов
                if event_type == "start":
                    # Сохраняем team, player_name, player_id_fhm и violation_type
                    active_penalties[penalty_id] = { # <-- Обновляем структуру словаря
                        "team": team,
                        "player_name": player_name,
                        "player_id_fhm": player_id_fhm_from_event,
                        "violation_type": violation_type_from_event # <-- Сохраняем violation_type
                    }
                elif event_type == "end":
                    active_penalties.pop(penalty_id, None) # Удаляем, если существует

                current_time = event_time

        # Добавляем все новые game_mode ranges в итоговый список
        calculated_ranges.extend(game_mode_ranges)
        # === КОНЕЦ НОВОГО БЛОКА ===

        # 5. Возврат:
        #    - Вернуть итоговый список всех созданных CalculatedRange ("Всё видео", "Сегменты", "ЧИИ", "ЧИИ_СУММА").
        return calculated_ranges
    # modules/smart.py
# ... (внутри класса SMARTProcessor) ...

    def _process_player_shifts(
        self,
        generic_labels: List[GenericLabel],
        calculated_ranges: List[CalculatedRange],
        total_duration_sec: float
    ) -> Dict[str, PlayerShiftInfo]:
        """
        Обрабатывает метки 'Смена' и формирует структуру player_shifts.

        Args:
            generic_labels: Список всех GenericLabel из проекта.
            calculated_ranges: Список всех CalculatedRange из проекта (для получения Сегментов).
            total_duration_sec: Общая длительность видео.

        Returns:
            Словарь player_shifts, где ключ - player_id_fhm, значение - PlayerShiftInfo.
        """
        # Извлекаем метки "Смена"
        change_labels = [
            label for label in generic_labels
            if label.label_type == "Смена"
            and label.context is not None
            and isinstance(label.context, dict)
            and "players_on_ice" in label.context
            and isinstance(label.context["players_on_ice"], list)
        ]

        # Проверяем и фильтруем содержимое players_on_ice
        filtered_change_labels = []
        for label in change_labels:
            valid_players = []
            for player_info in label.context["players_on_ice"]:
                if isinstance(player_info, dict) and "id_fhm" in player_info and "name" in player_info:
                    if isinstance(player_info["id_fhm"], str) and isinstance(player_info["name"], str):
                        valid_players.append(player_info)
                    else:
                        print(f"Предупреждение: Метка 'Смена' (id: {label.id}) содержит некорректные типы данных в players_on_ice: id_fhm='{type(player_info.get('id_fhm'))}', name='{type(player_info.get('name'))}'. Игрок проигнорирован.")
                else:
                    print(f"Предупреждение: Метка 'Смена' (id: {label.id}) содержит некорректную информацию о игроке в context.players_on_ice: {player_info}. Игрок проигнорирован.")
            if valid_players:
                # Создаём копию метки с отфильтрованным контекстом для дальнейшей обработки
                filtered_context = {**label.context, "players_on_ice": valid_players}
                # Для простоты, можно создать временную метку или модифицировать context на лету.
                # Но чтобы не менять оригинальные данные, будем использовать оригинальную метку,
                # но с осторожностью при доступе к context.
                # Просто добавляем оригинальную метку, если у неё есть хотя бы один валидный игрок.
                # В цикле обработки будем использовать label.context["players_on_ice"] и предполагать,
                # что там только валидные данные.
                filtered_change_labels.append(label)

        # Сортируем метки "Смена" по времени
        filtered_change_labels.sort(key=lambda x: x.global_time)

        # Извлекаем CalculatedRange "Сегмент" и сортируем их по start_time
        segment_ranges = [cr for cr in calculated_ranges if cr.label_type == "Сегмент"]
        segment_ranges.sort(key=lambda x: x.start_time)

        # Словарь для хранения времени "входа" игрока (global_time метки, где он впервые появился после выхода)
        player_entry_times: Dict[str, float] = {}

        # Множество игроков, находящихся на льду *до* текущей метки
        players_on_ice_before: Set[str] = set()

        # Результат: словарь player_id_fhm -> PlayerShiftInfo
        player_shifts_result: Dict[str, PlayerShiftInfo] = {}

        # Проходим по меткам "Смена" в хронологическом порядке
        for label in filtered_change_labels:
            # Получаем состав после изменения (только id_fhm)
            players_after_change_set = {player_info["id_fhm"] for player_info in label.context["players_on_ice"]}
            # NOTE: player_name берётся из метки, где игрок *вошёл* или *ушёл*.

            # Находим вышедших игроков (были до, нет после)
            left_players = players_on_ice_before - players_after_change_set

            # Находим вошедших игроков (нет до, есть после)
            entered_players = players_after_change_set - players_on_ice_before

            # --- Закрываем интервалы для вышедших игроков ---
            for player_id in left_players:
                entry_time = player_entry_times.get(player_id)
                if entry_time is not None:
                    # Найдём имя игрока из метки, где он *вошёл* (время entry_time).
                    # Это может быть сложно, если метки "Смена" не кешированы.
                    # Проще всего хранить имя вместе с entry_time.
                    # Однако, имя можно взять из *текущей* метки (где он *ушёл*), если он там есть.
                    # Лучше всего - хранить {player_id: (entry_global_time, player_name_at_entry)}
                    # Для простоты, возьмём имя из *текущей* метки, где он ушёл.
                    player_name = "Unknown Player"
                    for player_info in label.context["players_on_ice"]:
                        if player_info["id_fhm"] == player_id:
                            player_name = player_info["name"]
                            break # Нашли имя

                    # Найдём номер смены для этого игрока
                    existing_info = player_shifts_result.get(player_id)
                    if existing_info is None:
                        existing_info = PlayerShiftInfo(id_fhm=player_id, name=player_name)
                        player_shifts_result[player_id] = existing_info
                    else:
                        # Если PlayerShiftInfo уже существует, имя уже установлено. Можем проверить на совпадение.
                        if existing_info.name != player_name:
                            print(f"Предупреждение: Игрок {player_id} имеет разные имена в метках 'Смена': '{existing_info.name}' vs '{player_name}'. Используется первое.")

                    shift_number = len(existing_info.shifts) + 1
                    shift_obj = PlayerShift(number=shift_number, start_time=entry_time, end_time=label.global_time)
                    existing_info.shifts.append(shift_obj)

                    # Удаляем игрока из словаря точек входа
                    del player_entry_times[player_id]
                else:
                    # Игрок "ушёл", но не был отмечен как "вошедший". Артефакт данных.
                    print(f"Предупреждение: Игрок {player_id} ушёл с льда (метка id: {label.id}), но не был отмечен как вошедший. Пропущен.")

            # --- Открываем интервал (записываем точку входа) для вошедших игроков ---
            for player_id in entered_players:
                # Найдём имя игрока из *текущей* метки (где он *вошёл*)
                player_name = "Unknown Player"
                for player_info in label.context["players_on_ice"]:
                    if player_info["id_fhm"] == player_id:
                        player_name = player_info["name"]
                        break # Нашли имя

                # Записываем global_time текущей метки как время входа
                player_entry_times[player_id] = label.global_time

                # Создаём PlayerShiftInfo, если его ещё нет (для первого входа)
                if player_id not in player_shifts_result:
                    player_shifts_result[player_id] = PlayerShiftInfo(id_fhm=player_id, name=player_name)

            # Обновляем состояние
            players_on_ice_before = players_after_change_set

        # --- Финализация: закрываем интервалы для игроков, оставшихся на льду в конце периода ---
        # Для каждого игрока в player_entry_times нужно найти, в каком Сегменте он вошёл в последний раз
        # и закрыть его смену в end_time этого Сегмента.
        for player_id, entry_time in player_entry_times.items():
            # Найдём Сегмент, в котором находилась метка "Смена", установившая entry_time
            # Это требует поиска метки, которая установила entry_time.
            # Сопоставим entry_time с global_time меток из filtered_change_labels.
            # Найдём метку с минимальной разницей global_time - entry_time, где global_time >= entry_time.
            # Или, проще: пройти по отсортированным меткам и найти первую, где global_time == entry_time (если timestamps точные).
            # Если не точные, ищем ближайшую.
            corresponding_change_label = None
            for change_label in filtered_change_labels:
                if abs(change_label.global_time - entry_time) < 1e-6: # Проверим с небольшой погрешностью
                    corresponding_change_label = change_label
                    break
                elif change_label.global_time > entry_time: # Если время метки больше, то entry_time не может быть этой метки
                    # Если предыдущая метка была ближе, то нужно было её проверить раньше.
                    # Текущая метка уже за границей. entry_time не найден точно.
                    break

            if corresponding_change_label is None:
                # Не удалось найти метку, установившую entry_time. Артефакт.
                print(f"Предупреждение: Не найдена метка 'Смена', установившая точку входа {entry_time} для игрока {player_id}. Смена не будет завершена.")
                continue # Пропускаем этого игрока

            # Теперь найдём, в каком Сегменте была эта метка
            corresponding_segment = None
            for seg_range in segment_ranges:
                # Проверим, попадает ли время метки в интервал Сегмента
                if seg_range.start_time <= corresponding_change_label.global_time <= seg_range.end_time:
                    corresponding_segment = seg_range
                    break # Нашли

            if corresponding_segment is None:
                # Метка "Смена" вне любого Сегмента. Артефакт.
                print(f"Предупреждение: Метка 'Смена' (id: {corresponding_change_label.id}, time: {corresponding_change_label.global_time}) находится вне любого 'Сегмента'.")
                # В этом случае, возможно, нужно завершить смену в total_duration_sec
                # Но по ТЗ, смены должны быть внутри Сегментов.
                # Решим, что завершаем в total_duration_sec, если не нашли сегмент.
                end_time_final = total_duration_sec
            else:
                # Смена завершается в конце соответствующего Сегмента
                end_time_final = corresponding_segment.end_time

            # Найдём имя игрока из метки входа (corresponding_change_label)
            player_name = "Unknown Player"
            for player_info in corresponding_change_label.context["players_on_ice"]:
                if player_info["id_fhm"] == player_id:
                    player_name = player_info["name"]
                    break # Нашли имя

            # Найдём номер смены для этого игрока
            existing_info = player_shifts_result.get(player_id)
            if existing_info is None:
                # Теоретически, если он был в player_entry_times, он должен быть и в player_shifts_result
                # из-за логики добавления в entered_players.
                existing_info = PlayerShiftInfo(id_fhm=player_id, name=player_name)
                player_shifts_result[player_id] = existing_info
            else:
                # Проверим имя
                if existing_info.name != player_name:
                    print(f"Предупреждение: Игрок {player_id} имеет разные имена в метках 'Смена' (финализация): '{existing_info.name}' vs '{player_name}'. Используется существующее.")

            shift_number = len(existing_info.shifts) + 1
            shift_obj = PlayerShift(number=shift_number, start_time=entry_time, end_time=end_time_final)
            existing_info.shifts.append(shift_obj)

            # Удаляем из временного словаря (хотя это последняя итерация)
            # del player_entry_times[player_id] # Не обязательно, цикл закончен

        return player_shifts_result


    def _process_player_shifts_official_timer(
        self,
        player_shifts_data: Dict[str, PlayerShiftInfo],
        calculated_ranges: List[CalculatedRange]
    ) -> Dict[str, PlayerShiftInfo]:
        """
        Обрабатывает player_shifts и формирует структуру player_shifts_official_timer,
        где start_time и end_time смен выражены в официальном игровом времени.

        Args:
            player_shifts_data: Словарь player_shifts из project.match.
            calculated_ranges: Список calculated_ranges из project.match.

        Returns:
            Словарь player_shifts_official_timer.
        """
        
        # 1. Создаём "карту" официального времени и информацию о периодах
        official_timeline_map, period_info = create_official_time_map(calculated_ranges) # <-- Теперь возвращает два значения

        # 2. Результат: словарь player_id_fhm -> PlayerShiftInfo
        player_shifts_ot_result: Dict[str, PlayerShiftInfo] = {}

        # 3. Проходим по каждому игроку в player_shifts_data
        for player_id, player_info_obj in player_shifts_data.items():
            # 4. Создаём PlayerShiftInfo для официального времени
            player_name = player_info_obj.name
            new_player_info_obj = PlayerShiftInfo(id_fhm=player_id, name=player_name, shifts=[])

            # 5. Проходим по каждой смене игрока
            for shift_obj in player_info_obj.shifts:
                original_shift_number = shift_obj.number
                original_start_time = shift_obj.start_time
                original_end_time = shift_obj.end_time

              # 6. Переводим start_time и end_time в официальное время
                official_start_time = map_global_time_to_official(original_start_time, official_timeline_map, period_info) # <-- Три аргумента
                official_end_time = map_global_time_to_official(original_end_time, official_timeline_map, period_info) # <-- Три аргумента

                # 7. Проверяем, попали ли времена в ЧИИ
                if official_start_time is None or official_end_time is None:
                    # Если какое-то время не попало в ЧИИ, возможно, это артефакт данных или смена в "паузе".
                    # По умолчанию, мы не создаём смену в официальном времени, если границы не определены.
                    # Можно логировать предупреждение.
                    print(f"Предупреждение: Смена #{original_shift_number} игрока {player_name} ({player_id}) "
                        f"имеет границы ({original_start_time}, {original_end_time}), "
                        f"не попадающие полностью в ЧИИ. Смена не будет создана в официальном времени.")
                    continue

                # 8. Создаём новый объект PlayerShift с официальным временем
                new_shift_obj = PlayerShift(
                    number=original_shift_number, # Номер смены сохраняется
                    start_time=official_start_time,
                    end_time=official_end_time
                )

                # 9. Добавляем новый объект в список смен для официального времени
                new_player_info_obj.shifts.append(new_shift_obj)

            # 10. Добавляем PlayerShiftInfo для официального времени в результат
            player_shifts_ot_result[player_id] = new_player_info_obj

        return player_shifts_ot_result
    
    def convert_global_to_official_time(self, global_time: float, calculated_ranges: List[CalculatedRange]) -> Optional[float]:
        """
        Переводит глобальное время в официальное игровое время.

        Args:
            global_time: Время в глобальной шкале.
            calculated_ranges: Список calculated_ranges из проекта.

        Returns:
            Официальное время или None, если не попадает в ЧИИ.
        """
        official_timeline_map, period_info = create_official_time_map(calculated_ranges)
        return map_global_time_to_official(global_time, official_timeline_map, period_info)


        # ... (остальной код класса SMARTProcessor) ...


    # Конец содержимого файла: modules/smart.py