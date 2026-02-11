# modules/footage_detection.py
"""
Модуль для автоматического обнаружения видеовставок (футажей) в хоккейных трансляциях.
Ищет повторяющийся короткий футаж (например, логотип лиги) по его ключевому кадру (PNG).
Возвращает только времена обнаружения (в секундах), а не интервалы.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Callable


def _calculate_hash_similarity(hash1: bytes, hash2: bytes, resize: Tuple[int, int] = (32, 32)) -> float:
    """
    Вычисляет схожесть двух хешей кадров.
    """
    arr1 = np.frombuffer(hash1, dtype=np.uint8).reshape((resize[1], resize[0]))
    arr2 = np.frombuffer(hash2, dtype=np.uint8).reshape((resize[1], resize[0]))
    mean_abs_diff = np.mean(np.abs(arr1.astype(np.int16) - arr2.astype(np.int16)))
    return 1.0 - (mean_abs_diff / 255.0)


def extract_frame_hash_from_png(png_path: str, resize: Tuple[int, int] = (32, 32)) -> bytes:
    """
    Загружает PNG-изображение и возвращает его хеш (ключевой кадр шаблона).
    """
    image = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Не удалось загрузить PNG-шаблон: {png_path}")
    small = cv2.resize(image, resize, interpolation=cv2.INTER_AREA)
    return small.tobytes()


def find_video_template(
    main_video_path: str,
    template_png_path: str,
    threshold: float = 0.95,
    resize: Tuple[int, int] = (32, 32),
    skip_every_n: int = 1,
    search_ranges: Optional[List[Tuple[float, float]]] = None,
    debounce_seconds: float = 0.0, # <-- Новый параметр
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[float]:
    """
    Ищет все вхождения футажа (по ключевому кадру из PNG) в основном видео.

    Args:
        main_video_path: Путь к видео матча.
        template_png_path: Путь к PNG-файлу с ключевым кадром футажа.
        threshold: Порог схожести [0.0, 1.0]. Рекомендуется 0.92–0.95.
        resize: Размер кадра для сравнения (ширина, высота).
        skip_every_n: Обрабатывать каждый n-й кадр (1 = каждый кадр).
        search_ranges: Список (start, end) в секундах. Если None — искать во всём видео.
        debounce_seconds: Минимальная пауза (в секундах) между обнаружениями.
                         После нахождения футажа, не искать в течение debounce_seconds.
        progress_callback: Опциональный callback для отслеживания прогресса.

    Returns:
        List[float]: Список времён (в секундах) обнаружения ключевого кадра.

    Raises:
        ValueError: При ошибках работы с видео или шаблоном.
    """
    if skip_every_n < 1:
        skip_every_n = 1

    # === Загружаем FPS и общую длительность основного видео ===
    cap = cv2.VideoCapture(main_video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть основное видео: {main_video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if fps <= 0:
        fps = 25.0

    # === Загружаем ключевой кадр шаблона (из PNG) ===
    key_hash = extract_frame_hash_from_png(template_png_path, resize)

    # === Определяем диапазоны поиска ===
    if search_ranges is None:
        # Поиск по всему видео
        frame_ranges = [(0, total_frames)]
    else:
        # Преобразуем временные диапазоны в кадровые
        frame_ranges = []
        for start_sec, end_sec in search_ranges:
            start_frame = max(0, int(start_sec * fps))
            end_frame = min(total_frames, int(end_sec * fps))
            if start_frame < end_frame:
                frame_ranges.append((start_frame, end_frame))

    # === Потоковая обработка по диапазонам ===
    cap = cv2.VideoCapture(main_video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть основное видео (второй раз): {main_video_path}")

    results = []
    total_to_process = 0
    processed_count = 0

    # Подсчёт общего числа кадров для обработки (для прогресса)
    for start_f, end_f in frame_ranges:
        total_to_process += (end_f - start_f + skip_every_n - 1) // skip_every_n

    # === НОВОЕ: Переменная для отслеживания времени, после которого можно искать снова ===
    next_allowed_time_sec = -float('inf')

    # Обработка каждого диапазона
    for start_frame, end_frame in frame_ranges:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_index = start_frame

        while frame_index < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            # Пропускаем кадры, если skip_every_n > 1
            if (frame_index - start_frame) % skip_every_n != 0:
                frame_index += 1
                # --- ИСПРАВЛЕНО: увеличиваем processed_count и вызываем progress_callback ---
                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, total_to_process)
                continue

            current_time_sec = frame_index / fps

            # === НОВОЕ: Проверка дебаунсинга ===
            if current_time_sec < next_allowed_time_sec:
                frame_index += 1
                # --- ИСПРАВЛЕНО: увеличиваем processed_count и вызываем progress_callback ---
                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, total_to_process)
                continue

            # --- ИСПРАВЛЕНО: увеличиваем processed_count и вызываем progress_callback ПЕРЕД анализом ---
            processed_count += 1
            if progress_callback:
                progress_callback(processed_count, total_to_process)

            # Обрабатываем кадр
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, resize, interpolation=cv2.INTER_AREA)
            frame_hash = small.tobytes()

            similarity = _calculate_hash_similarity(frame_hash, key_hash, resize)
            if similarity >= threshold:
                results.append(current_time_sec)
                # === НОВОЕ: Устанавливаем время, после которого можно искать снова ===
                next_allowed_time_sec = current_time_sec + debounce_seconds

            frame_index += 1

        # Пропускаем оставшиеся кадры в диапазоне (если skip_every_n > 1)
        remaining = end_frame - frame_index
        if remaining > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, end_frame)
            processed_count += (remaining + skip_every_n - 1) // skip_every_n
            if progress_callback:
                progress_callback(processed_count, total_to_process)

    cap.release()
    return results