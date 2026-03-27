#!/usr/bin/env python3
"""
Скрипт для добавления вратарей в существующие метки "Смена".

Вратарь №1 Новиков П. играл с начала матча до смены с global_time = 7646.111441109549
Вратарь №20 Никонов В. играл с смены с global_time = 7705.946666068436 до конца матча
"""

import json

# ID и данные вратарей
GOALIE_1 = {"id_fhm": "6976", "name": "Новиков П."}   # №1
GOALIE_20 = {"id_fhm": "9507", "name": "Никонов В."}  # №20

# Времена смены вратарей (global_time)
SHIFT_TIME_GOALIE_1_END = 7646.111441109549   # Последняя смена с Новиковым
SHIFT_TIME_GOALIE_20_START = 7705.946666068436  # Первая смена с Никоновым

def main():
    hkt_file = "TEST_REPORT_HKT_19_тур_10.01.2026_Русь 2014_vs_Созвездие 2014.hkt"
    
    # Загружаем HKT файл
    with open(hkt_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    match = data.get('match', {})
    generic_labels = match.get('generic_labels', [])
    
    print(f"Загружен файл: {hkt_file}")
    print(f"Всего меток: {len(generic_labels)}")
    
    # Счётчики
    shifts_updated = 0
    goalie_1_added = 0
    goalie_20_added = 0
    
    # Обрабатываем каждую метку "Смена"
    for label in generic_labels:
        if label.get('label_type') != 'Смена':
            continue
        
        global_time = label.get('global_time', 0)
        context = label.get('context', {})
        
        # Получаем текущий список игроков на льду
        if 'players_on_ice' not in context:
            context['players_on_ice'] = []
        
        players_on_ice = context['players_on_ice']
        
        # Определяем, какой вратарь должен быть на льду
        # Если время <= конца игры Новикова → Новиков
        # Если время >= начала игры Никонова → Никонов
        # В промежутке (7646.11 - 7705.95) решаем по ближайшему
        
        if global_time <= SHIFT_TIME_GOALIE_1_END:
            # Добавляем Новикова №1
            goalie = GOALIE_1
            goalie_1_added += 1
        elif global_time >= SHIFT_TIME_GOALIE_20_START:
            # Добавляем Никонова №20
            goalie = GOALIE_20
            goalie_20_added += 1
        else:
            # Промежуточная зона - редкий случай
            # Определяем по ближайшему времени
            dist_to_1 = abs(global_time - SHIFT_TIME_GOALIE_1_END)
            dist_to_20 = abs(global_time - SHIFT_TIME_GOALIE_20_START)
            if dist_to_1 < dist_to_20:
                goalie = GOALIE_1
                goalie_1_added += 1
            else:
                goalie = GOALIE_20
                goalie_20_added += 1
        
        # Проверяем, нет ли уже этого вратаря в списке
        goalie_exists = False
        for player in players_on_ice:
            if isinstance(player, dict) and player.get('id_fhm') == goalie['id_fhm']:
                goalie_exists = True
                break
            elif isinstance(player, str) and player == goalie['id_fhm']:
                # Старый формат - просто ID
                goalie_exists = True
                break
        
        if not goalie_exists:
            # Добавляем вратаря в начало списка (или в конец)
            players_on_ice.append(goalie)
            shifts_updated += 1
            
            # Обновляем context
            label['context'] = context
    
    print(f"\nОбработано меток 'Смена': {goalie_1_added + goalie_20_added}")
    print(f"  - с Новиковым №1: {goalie_1_added}")
    print(f"  - с Никоновым №20: {goalie_20_added}")
    print(f"Обновлено меток (добавлен вратарь): {shifts_updated}")
    
    # Также обновляем player_shifts (для совместимости с отчётами)
    player_shifts = match.get('player_shifts', {})
    
    # Добавляем смены вратарей в player_shifts
    segments = [cr for cr in match.get('calculated_ranges', []) if cr.get('label_type') == 'Сегмент']
    segments.sort(key=lambda x: x.get('start_time', 0))
    
    if segments:
        first_global = segments[0]['start_time']
        last_global = segments[-1]['end_time']
        
        # Новиков: от начала до SHIFT_TIME_GOALIE_1_END
        player_shifts[GOALIE_1['id_fhm']] = {
            "id_fhm": GOALIE_1['id_fhm'],
            "name": GOALIE_1['name'],
            "shifts": [{
                "number": 1,
                "start_time": first_global,
                "end_time": SHIFT_TIME_GOALIE_1_END
            }]
        }
        
        # Никонов: от SHIFT_TIME_GOALIE_20_START до конца
        player_shifts[GOALIE_20['id_fhm']] = {
            "id_fhm": GOALIE_20['id_fhm'],
            "name": GOALIE_20['name'],
            "shifts": [{
                "number": 1,
                "start_time": SHIFT_TIME_GOALIE_20_START,
                "end_time": last_global
            }]
        }
        
        print(f"\nОбновлены player_shifts:")
        print(f"  - Новиков №1: {first_global:.2f} - {SHIFT_TIME_GOALIE_1_END:.2f}")
        print(f"  - Никонов №20: {SHIFT_TIME_GOALIE_20_START:.2f} - {last_global:.2f}")
    
    # Сохраняем обновлённый файл
    output_file = hkt_file.replace('.hkt', '_with_goalies.hkt')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nФайл сохранён: {output_file}")

if __name__ == "__main__":
    main()
