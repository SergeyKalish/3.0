#!/usr/bin/env python3
"""
Скрипт для добавления смен вратарей в HKT файл напрямую.

Вратарь №1 Новиков П. играл с начала матча до 53:20 по официальному таймеру
Вратарь №20 Никонов В. играл с 53:20 до конца матча
"""

import json

# ID вратарей (из команды s-team - Созвездие)
GOALIE_1_ID = "6976"   # №1 Новиков Павел
GOALIE_20_ID = "9507"  # №20 Никонов Владислав

# Время смены вратаря (официальное время)
SHIFT_TIME_OFFICIAL = 53 * 60 + 20  # 53:20 = 3200 секунд

def find_global_time_for_official(calculated_ranges, target_official_time):
    """
    Находит глобальное время для заданного официального времени.
    Использует линейную интерполяцию внутри периода.
    """
    # Находим все сегменты (периоды)
    segments = [cr for cr in calculated_ranges if cr.get('label_type') == 'Сегмент']
    segments.sort(key=lambda x: x.get('start_time', 0))
    
    if not segments:
        return None
    
    # Определяем, в какой период попадает target_official_time
    # Периоды обычно идут по 20 минут (1200 сек)
    period_duration = 1200  # 20 минут
    
    period_idx = int(target_official_time // period_duration)
    period_offset = target_official_time % period_duration
    
    if period_idx >= len(segments):
        # Если время за пределами периодов, берём последний период
        period_idx = len(segments) - 1
        period_offset = period_duration
    
    segment = segments[period_idx]
    seg_start = segment.get('start_time', 0)
    seg_end = segment.get('end_time', 0)
    seg_duration = seg_end - seg_start
    
    # Коэффициент периода (фактическая длительность / 20 минут)
    coefficient = seg_duration / period_duration if period_duration > 0 else 1.0
    
    # Глобальное время = начало периода + смещение * коэффициент
    global_time = seg_start + period_offset * coefficient
    
    return global_time

def main():
    hkt_file = "TEST_REPORT_HKT_19_тур_10.01.2026_Русь 2014_vs_Созвездие 2014.hkt"
    
    # Загружаем HKT файл
    with open(hkt_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    match = data.get('match', {})
    calculated_ranges = match.get('calculated_ranges', [])
    total_duration = match.get('total_duration_sec', 0)
    
    print(f"Загружен файл: {hkt_file}")
    print(f"Общая длительность видео: {total_duration:.2f} сек")
    
    # Находим глобальное время для 53:20
    shift_time_global = find_global_time_for_official(calculated_ranges, SHIFT_TIME_OFFICIAL)
    
    if shift_time_global is None:
        print(f"Ошибка: не найдено глобальное время для {SHIFT_TIME_OFFICIAL} сек (53:20)")
        return
    
    print(f"Время смены: 53:20 официального = {shift_time_global:.2f} глобального")
    
    # Находим глобальное время для начала и конца матча
    segments = [cr for cr in calculated_ranges if cr.get('label_type') == 'Сегмент']
    segments.sort(key=lambda x: x.get('start_time', 0))
    
    if not segments:
        print("Ошибка: не найдены сегменты")
        return
    
    first_global = segments[0]['start_time']
    last_global = segments[-1]['end_time']
    
    print(f"Начало матча (глобальное): {first_global:.2f}")
    print(f"Конец матча (глобальное): {last_global:.2f}")
    
    # Получаем player_shifts
    player_shifts = match.get('player_shifts', {})
    
    # Добавляем смену для Новикова №1 (с начала до 53:20)
    if GOALIE_1_ID not in player_shifts:
        player_shifts[GOALIE_1_ID] = {
            "id_fhm": GOALIE_1_ID,
            "name": "Новиков Павел",
            "shifts": []
        }
    
    player_shifts[GOALIE_1_ID]["shifts"] = [{
        "number": 1,
        "start_time": first_global,
        "end_time": shift_time_global
    }]
    
    print(f"\nДобавлена смена для №1 Новиков П.:")
    print(f"  Start: {first_global:.2f}, End: {shift_time_global:.2f}")
    
    # Добавляем смену для Никонова №20 (с 53:20 до конца)
    if GOALIE_20_ID not in player_shifts:
        player_shifts[GOALIE_20_ID] = {
            "id_fhm": GOALIE_20_ID,
            "name": "Никонов Владислав",
            "shifts": []
        }
    
    player_shifts[GOALIE_20_ID]["shifts"] = [{
        "number": 1,
        "start_time": shift_time_global,
        "end_time": last_global
    }]
    
    print(f"\nДобавлена смена для №20 Никонов В.:")
    print(f"  Start: {shift_time_global:.2f}, End: {last_global:.2f}")
    
    # Также обновляем player_shifts_official_timer
    official_shifts = match.get('player_shifts_official_timer', {})
    
    official_shifts[GOALIE_1_ID] = {
        "id_fhm": GOALIE_1_ID,
        "name": "Новиков Павел",
        "shifts": [{
            "number": 1,
            "start_time": 0.0,
            "end_time": float(SHIFT_TIME_OFFICIAL)
        }]
    }
    
    # Конец официального времени = начало + длительность последнего периода (обычно 60:00 = 3600 сек)
    official_end = 60 * 60  # 60 минут
    official_shifts[GOALIE_20_ID] = {
        "id_fhm": GOALIE_20_ID,
        "name": "Никонов Владислав",
        "shifts": [{
            "number": 1,
            "start_time": float(SHIFT_TIME_OFFICIAL),
            "end_time": float(official_end)
        }]
    }
    
    # Сохраняем обновлённый файл
    output_file = hkt_file.replace('.hkt', '_with_goalies.hkt')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nФайл сохранён: {output_file}")
    print("Теперь можно открыть его в HockeyTagger или сгенерировать отчёт.")

if __name__ == "__main__":
    main()
