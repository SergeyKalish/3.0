#!/usr/bin/env python3
"""
Модуль для извлечения времен начала ЧИИ (вбрасываний) из HKT-файлов в CSV.

Формат CSV:
video_filename,faceoff_time_sec
match1.mp4,284.5
match1.mp4,312.0
match2.mp4,145.2

Использование:
    python extract_faceoffs.py <path_to_hkt_or_directory> [output.csv]

Примеры:
    python extract_faceoffs.py match.hkt faceoffs.csv
    python extract_faceoffs.py "C:/Matches/" all_faceoffs.csv
"""

import json
import csv
import sys
import os
from pathlib import Path
from typing import List, Dict, Any


def extract_faceoffs_from_hkt(hkt_path: str) -> List[Dict[str, Any]]:
    """
    Извлекает времена начала ЧИИ из HKT-файла.
    
    Returns:
        Список словарей с ключами 'video_filename' и 'faceoff_time_sec'
    """
    results = []
    
    with open(hkt_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Получаем имя видео-файла
    video_path = data.get('video_path', '')
    if video_path:
        video_filename = Path(video_path).name
        # Проверяем, что имя читаемое (нет кракозябр)
        try:
            # Если есть пробелы и цифры, и имя не пустое - используем его
            if not video_filename or len(video_filename) < 5:
                video_filename = Path(hkt_path).stem + '.mp4'
        except:
            video_filename = Path(hkt_path).stem + '.mp4'
    else:
        video_filename = Path(hkt_path).stem + '.mp4'
    
    # Ищем calculated_ranges типа "ЧИИ"
    match_data = data.get('match', {})
    calculated_ranges = match_data.get('calculated_ranges', [])
    
    for range_item in calculated_ranges:
        if range_item.get('label_type') == 'ЧИИ':
            # Берем начало диапазона ЧИИ - это время вбрасывания
            start_time = range_item.get('start_time')
            if start_time is not None:
                results.append({
                    'video_filename': video_filename,
                    'faceoff_time_sec': float(start_time)
                })
    
    # Сортируем по времени
    results.sort(key=lambda x: x['faceoff_time_sec'])
    
    return results


def process_path(input_path: str) -> List[Dict[str, Any]]:
    """
    Обрабатывает путь (файл или директорию) и извлекает данные из всех HKT.
    """
    all_results = []
    path = Path(input_path)
    
    if path.is_file() and path.suffix.lower() == '.hkt':
        # Один файл
        results = extract_faceoffs_from_hkt(str(path))
        all_results.extend(results)
        print(f"Обработан: {path.name} - найдено {len(results)} вбрасываний")
        
    elif path.is_dir():
        # Директория - ищем все HKT-файлы
        hkt_files = list(path.glob('*.hkt')) + list(path.glob('*.HKT'))
        
        if not hkt_files:
            print(f"HKT-файлы не найдены в директории: {path}")
            return []
        
        for hkt_file in sorted(hkt_files):
            results = extract_faceoffs_from_hkt(str(hkt_file))
            all_results.extend(results)
            print(f"Обработан: {hkt_file.name} - найдено {len(results)} вбрасываний")
    else:
        print(f"Указан неверный путь: {input_path}")
        return []
    
    return all_results


def save_to_csv(results: List[Dict[str, Any]], output_path: str):
    """Сохраняет результаты в CSV-файл."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['video_filename', 'faceoff_time_sec'])
        
        for item in results:
            writer.writerow([item['video_filename'], item['faceoff_time_sec']])
    
    print(f"\nСохранено {len(results)} записей в: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Использование: python extract_faceoffs.py <path_to_hkt_or_directory> [output.csv]")
        print("\nПримеры:")
        print('  python extract_faceoffs.py match.hkt')
        print('  python extract_faceoffs.py match.hkt faceoffs.csv')
        print('  python extract_faceoffs.py "C:/Matches/" all_faceoffs.csv')
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    # Определяем выходной файл
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        # Автоматическое имя по умолчанию
        if Path(input_path).is_dir():
            output_path = 'faceoffs.csv'
        else:
            output_path = Path(input_path).stem + '_faceoffs.csv'
    
    # Обрабатываем
    results = process_path(input_path)
    
    if results:
        save_to_csv(results, output_path)
    else:
        print("Нет данных для сохранения.")
        sys.exit(1)


if __name__ == "__main__":
    main()
