# utils/helpers.py
import json
from typing import Dict, Any, List, Tuple, Optional
from model.project import Project, CalculatedRange

def load_project_from_file(file_path: str) -> Project:
    """Загружает проект из JSON-файла."""
    return Project.load_from_file(file_path)

def save_project_to_file(project: Project, file_path: str):
    """Сохраняет проект в JSON-файл."""
    project.save_to_file(file_path)

def serialize_for_json(obj: Any) -> Any:
    """Вспомогательная функция для сериализации сложных объектов в JSON."""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    else:
        return obj

# --- НОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С ОФИЦИАЛЬНЫМ ВРЕМЕНЕМ ---

# utils/helpers.py
# ... (до функций create_official_time_map и т.д.) ...

def create_official_time_map(calculated_ranges: List[CalculatedRange]) -> Tuple[List[Dict[str, float]], Dict[str, Dict[str, float]]]:
    """
    Создаёт "карту" соответствия между глобальным временем и официальным игровому времени,
    с учётом коэффициентов для каждого периода (кроме овертайма).
    Также создаёт карту с информацией о каждом периоде.

    Args:
        calculated_ranges: Список CalculatedRange из проекта.

    Returns:
        Кортеж (full_timeline_map, period_info), где:
        - full_timeline_map: список [{'global_start': float, 'global_end': float, 'official_start': float, 'duration': float, 'coefficient': float}],
          представляющий отрезки ЧИИ *с учётом коэффициента* и их позиции на шкале официального времени.
          'official_start' - это накопленная *скорректированная* длительность до начала *данного* ЧИИ.
          'duration' - это *скорректированная* длительность *данного* ЧИИ.
          'coefficient' - коэффициент *периода*, к которому принадлежит ЧИИ.
        - period_info: словарь {"Период 1": {"start_sec": float, "end_sec": float, "total_chi_duration": float, "target_duration": float, "coefficient": float}, ...}.
    """
    # Извлекаем Сегменты и ЧИИ
    segment_ranges = [cr for cr in calculated_ranges if cr.label_type == "Сегмент"]
    chi_ranges = [cr for cr in calculated_ranges if cr.label_type == "ЧИИ"]

    # Словарь для хранения информации о периодах
    period_info = {}
    # Словарь: id сегмента -> список его ЧИИ
    chi_by_segment = {}
    for chi in chi_ranges:
        # Найдём, к какому сегменту принадлежит ЧИИ
        for seg in segment_ranges:
            if seg.start_time <= chi.start_time <= seg.end_time and seg.start_time <= chi.end_time <= seg.end_time:
                seg_id = seg.id
                if seg_id not in chi_by_segment:
                    chi_by_segment[seg_id] = []
                chi_by_segment[seg_id].append(chi)
                break # Нашли сегмент для ЧИИ

    # Вычислим коэффициенты для каждого сегмента
    for seg in segment_ranges:
        period_name = seg.name # e.g., "Период 1"
        seg_chi_list = chi_by_segment.get(seg.id, [])
        total_chi_duration = sum((chi.end_time - chi.start_time) for chi in seg_chi_list)

        # Целевая длительность: 20 минут (1200 сек) для обычных периодов
        target_duration = 1200.0 if "Овертайм" not in period_name else total_chi_duration # Для овертайма коэф = 1
        coefficient = total_chi_duration / target_duration if target_duration > 0 else 1.0

        period_info[period_name] = {
            "start_sec": seg.start_time,
            "end_sec": seg.end_time,
            "total_chi_duration": total_chi_duration,
            "target_duration": target_duration,
            "coefficient": coefficient
        }

    # Теперь строим full_timeline_map, применяя коэффициенты
    sorted_chi = sorted(chi_ranges, key=lambda x: x.start_time)
    full_timeline_map = []
    accumulated_official_time = 0.0

    for chi in sorted_chi:
        # Найдём период, к которому принадлежит этот ЧИИ
        period_name_for_chi = None
        for period_name, info in period_info.items():
            if info["start_sec"] <= chi.start_time <= info["end_sec"]:
                period_name_for_chi = period_name
                break

        if period_name_for_chi is None:
            # ЧИИ вне сегментов? Пропустим или логируем.
            print(f"Предупреждение: ЧИИ [{chi.start_time}, {chi.end_time}] не найден в сегментах. Пропущен.")
            continue

        coefficient_for_this_chi = period_info[period_name_for_chi]["coefficient"]
        chi_duration_raw = chi.end_time - chi.start_time
        chi_duration_scaled = chi_duration_raw / coefficient_for_this_chi

        full_timeline_map.append({
            'global_start': chi.start_time,
            'global_end': chi.end_time,
            'official_start': accumulated_official_time,
            'duration': chi_duration_scaled, # Длительность в официальном времени
            'coefficient': coefficient_for_this_chi # Коэффициент периода
        })
        accumulated_official_time += chi_duration_scaled

    return full_timeline_map, period_info

def map_global_time_to_official(global_time: float, official_timeline_map: List[Dict[str, float]], period_info: Dict[str, Dict[str, float]]) -> Optional[float]:
    """
    Преобразует глобальное время в официальное игровое время с учётом коэффициентов периода.

    Args:
        global_time: Время в глобальной шкале.
        official_timeline_map: Карта, созданная create_official_time_map.
        period_info: Информация о периодах, созданная create_official_time_map.

    Returns:
        Официальное время или None, если глобальное время не попадает в ЧИИ.
    """
    for segment in official_timeline_map:
        if segment['global_start'] <= global_time <= segment['global_end']:
            # 1. Найдём период, к которому принадлежит этот сегмент
            period_name_for_segment = None
            for period_name, info in period_info.items():
                if info["start_sec"] <= segment['global_start'] <= info["end_sec"]:
                    period_name_for_segment = period_name
                    break

            if period_name_for_segment is None:
                # Теоретически не должно happen, если official_timeline_map корректна
                return None

            coefficient = segment['coefficient']
            # 2. Вычисляем смещение внутри сегмента ЧИИ (в глобальном времени)
            offset_in_segment_raw = global_time - segment['global_start']
            # 3. Переводим смещение в официальное время (делением на коэффициент)
            offset_in_segment_official = offset_in_segment_raw / coefficient
            # 4. Добавляем смещение к началу сегмента на официальной шкале
            official_time_raw = segment['official_start'] + offset_in_segment_official
            # 5. Округляем до 1 знака после запятой
            official_time = round(official_time_raw, 1)
            return official_time
    # Время не попадает в ЧИИ
    return None

def convert_global_to_official_time(global_time: float, calculated_ranges: List[CalculatedRange]) -> Optional[float]:
    """
    Удобная функция для перевода глобального времени в официальное.

    Args:
        global_time: Время в глобальной шкале.
        calculated_ranges: Список CalculatedRange из проекта.

    Returns:
        Официальное время на шкале "чистого игрового времени".
        Возвращает None, если время не попадает в ЧИИ.
    """
    official_timeline_map, period_info = create_official_time_map(calculated_ranges)
    return map_global_time_to_official(global_time, official_timeline_map, period_info)

# --- КОНЕЦ НОВЫХ ФУНКЦИЙ ---

# ... (остальной код файла) ...