# modules/on_screen_graphics_detection.py
"""
Модуль для автоматического обнаружения событий (например, "ГОЛ", "2 МИН") на on-screen graphics (OSG)
в видеофайле по их появлению в заданной области кадра (ROI) с помощью OCR (pytesseract).
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image
from typing import List, Dict, Tuple, Optional, Callable, Any


def _preprocess_image(img: np.ndarray, method: int) -> np.ndarray:
    """
    Применяет один из 10 методов предобработки изображения для OCR.
    В точности как в test_ocr_on_single_frame.py.
    """
    if method == 0:
        # 0: Без предобработки (исходное grayscale)
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif method == 1:
        # 1: Увеличение контраста
        return cv2.convertScaleAbs(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), alpha=1.5, beta=0)
    elif method == 2:
        # 2: Бинаризация Otsu
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    elif method == 3:
        # 3: Адаптивная бинаризация
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        return binary
    elif method == 4:
        # 4: Инверсия + бинаризация
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return binary
    elif method == 5:
        # 5: Сглаживание + контраст
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        return cv2.convertScaleAbs(blur, alpha=1.5, beta=0)
    elif method == 6:
        # 6: Морфологическое замыкание
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        return closed
    elif method == 7:
        # 7: Удаление шума + бинаризация
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    elif method == 8:
        # 8: Выделение границ + бинаризация
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        _, binary = cv2.threshold(edges, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    elif method == 9:
        # 9: Режим "только белый текст на тёмном фоне"
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        return binary
    else:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def detect_osg_events(
    video_path: str,
    roi: Dict[str, int],  # {"x": 151, "y": 92, "width": 91, "height": 34}
    event_type_map: Dict[str, str],  # {"ГОЛ": "Goal", "2 МИН": "Penalty", ...}
    search_ranges: Optional[List[Tuple[float, float]]] = None,
    debounce_seconds: float = 5.0,  # Задержка дебаунсинга: не искать повторы события в течение N секунд
    correlation_threshold: float = 0.95,  # Порог уверенности OCR (например, средняя уверенность > 95%)
    preprocess_method: int = 0,  # Метод предобработки изображения (0-9 из предыдущего скрипта)
    skip_every_n: int = 1,  # Пропускать N-1 кадров между обрабатываемыми (1 = обрабатывать все)
    find_first_only: bool = False,  # <-- Новый параметр: искать только первое вхождение
    progress_callback: Optional[Callable[[int, int], None]] = None  # Для отображения прогресса
) -> List[Dict[str, Any]]:
    """
    Выполняет OCR на заданной области кадра в видео и ищет ключевые слова из event_type_map.

    Args:
        video_path: Путь к видеофайлу.
        roi: Словарь с координатами ROI: {"x": ..., "y": ..., "width": ..., "height": ...}.
        event_type_map: Словарь {"ключевое_слово": "event_type"}.
        search_ranges: Список (start_sec, end_sec). Если None — искать по всему видео.
        debounce_seconds: Минимальная пауза между двумя событиями одного типа (в секундах).
                         После нахождения события OCR не вызывается для этого типа до (T + debounce).
        correlation_threshold: Минимальная уверенность OCR (средняя по словам).
        preprocess_method: Номер метода предобработки изображения (0-9).
        skip_every_n: Пропускать N-1 кадров между обрабатываемыми (1 = обрабатывать все).
        find_first_only: Если True, останавливается после первого найденного события.
        progress_callback: Функция callback(current, total) для отслеживания прогресса.

    Returns:
        List[Dict[str, Any]]: [
            {
                "global_time_sec": 123.45,      # Время появления события (в секундах от начала видео)
                "detected_text": "ГОЛ! ИВАНОВ", # Точный текст, распознанный OCR
                "event_type": "Goal",           # Тип события (определяется по event_type_map)
                "confidence": 87.0              # Средняя уверенность OCR (если доступна)
            },
            ...
        ]
    """
    if skip_every_n < 1:
        skip_every_n = 1

    # === Открываем видео ===
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть видео: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0:
        fps = 25.0  # fallback

    x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]

    # === Определяем диапазоны поиска в кадрах ===
    if search_ranges is None:
        frame_ranges = [(0, total_frames)]
    else:
        frame_ranges = []
        for start_sec, end_sec in search_ranges:
            start_frame = max(0, int(start_sec * fps))
            end_frame = min(total_frames, int(end_sec * fps))
            if start_frame < end_frame:
                frame_ranges.append((start_frame, end_frame))

    # === Подсчёт общего числа кадров для прогресса ===
    total_to_process = 0
    for start_f, end_f in frame_ranges:
        total_to_process += (end_f - start_f + skip_every_n - 1) // skip_every_n

    # === Переменные для дебаунсинга и результатов ===
    next_allowed_time = {}  # {event_type: float (время в секундах)}
    results = []
    processed_count = 0

    # === Цикл по диапазонам ===
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
                continue  # Не увеличиваем processed_count, т.к. кадр не обрабатывается

            current_time_sec = frame_index / fps

            # === Оптимизация: пропуск кадров по дебаунсу ===
            skip_ocr = False
            for event_type, allowed_time in next_allowed_time.items():
                if current_time_sec < allowed_time:
                    # Пропускаем OCR для этого типа, но всё равно инкрементим счётчик
                    skip_ocr = True
                    break

            # === Увеличиваем processed_count, потому что кадр "обрабатывается" (даже если OCR пропущен) ===
            processed_count += 1
            if progress_callback:
                progress_callback(processed_count, total_to_process)

            if skip_ocr:
                frame_index += 1
                continue

            # === Вырезаем ROI ===
            roi_img = frame[y:y+h, x:x+w]
            if roi_img.size == 0:
                frame_index += 1
                continue

            # === Применяем предобработку ===
            processed_img = _preprocess_image(roi_img, preprocess_method)

            # === OCR ===
            pil_img_roi = Image.fromarray(processed_img)
            try:
                config = '--psm 6 --oem 3 -l rus'
                text = pytesseract.image_to_string(pil_img_roi, config=config).strip()
                data = pytesseract.image_to_data(pil_img_roi, output_type=pytesseract.Output.DICT, config=config)
                confidences = [conf for conf, word in zip(data['conf'], data['text']) if word.strip() != '']
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            except Exception as e:
                print(f"Ошибка при выполнении OCR на кадре {frame_index}: {e}")
                frame_index += 1
                continue

            # === Проверяем наличие ключевых слов ===
            if text:
                found_keyword = None
                for kw in event_type_map:
                    if kw.upper() in text.upper():
                        found_keyword = kw
                        break

                if found_keyword is not None:
                    event_type = event_type_map[found_keyword]

                    # === Проверка порога уверенности ===
                    if avg_conf < correlation_threshold:
                        frame_index += 1
                        continue

                    # === Фиксируем событие ===
                    event = {
                        "global_time_sec": current_time_sec,
                        "detected_text": text,
                        "event_type": event_type,
                        "confidence": avg_conf
                    }
                    results.append(event)

                    # === Устанавливаем время, после которого можно снова искать этот тип ===
                    next_allowed_time[event_type] = current_time_sec + debounce_seconds

                    # === Проверка find_first_only ===
                    if find_first_only:
                        cap.release()
                        if progress_callback:
                            progress_callback(processed_count, total_to_process)  # Завершаем прогресс
                        return results

            frame_index += 1

    cap.release()
    return results