# modules/combined_detection.py
"""
Модуль для объединённого прохода OSD + Footage по видео.
Читает видео один раз, параллельно выполняя OCR (OSG) и поиск футажей.
"""

import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional, Callable, Any

from modules.on_screen_graphics_detection import _preprocess_image


def _extract_template_array(png_path: str, resize: Tuple[int, int]) -> np.ndarray:
    """Загружает PNG-шаблон и возвращает его как numpy-массив int16 для быстрого сравнения."""
    image = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Не удалось загрузить PNG-шаблон: {png_path}")
    small = cv2.resize(image, resize, interpolation=cv2.INTER_AREA)
    return small.astype(np.int16)


def _calc_similarity(frame_gray: np.ndarray, template: np.ndarray, resize: Tuple[int, int]) -> float:
    """Вычисляет схожесть кадра с шаблоном."""
    small = cv2.resize(frame_gray, resize, interpolation=cv2.INTER_AREA)
    mean_abs_diff = np.mean(np.abs(small.astype(np.int16) - template))
    return 1.0 - (mean_abs_diff / 255.0)


def run_combined_detection(
    video_path: str,
    search_ranges: List[Tuple[float, float]],
    template_png_path: str,
    roi: Dict[str, int],
    event_type_map: Dict[str, str],
    analysis_params: Dict[str, Any],
    progress_callback: Optional[Callable[[int, int], None]] = None,
    base_resolution: Tuple[int, int] = (1920, 1080)
) -> Tuple[List[Dict[str, Any]], List[float]]:
    """
    Объединённый проход OSD + Footage по видео.

    Returns:
        (osg_results, footage_results) в тех же форматах, что и отдельные модули.
    """
    # === Параметры OSG ===
    osg_skip = analysis_params.get("osg_skip_every_n", 5)
    osg_debounce = analysis_params.get("osg_debounce_seconds", 5.0)
    osg_corr_thresh = analysis_params.get("osg_correlation_threshold", 0.8)
    osg_preprocess = analysis_params.get("osg_preprocess_method", 0)
    osg_find_first_only = analysis_params.get("osg_find_first_only", False)

    # === Параметры Footage ===
    footage_skip = analysis_params.get("footage_skip_every_n", 10)
    footage_threshold = analysis_params.get("footage_threshold", 0.9)
    footage_resize = analysis_params.get("footage_resize", (16, 16))
    footage_debounce = analysis_params.get("footage_debounce_seconds", 5.0)

    if osg_skip < 1:
        osg_skip = 1
    if footage_skip < 1:
        footage_skip = 1

    # === Инициализация tesserocr ===
    tesserocr_api = None
    use_tesserocr = False
    try:
        from tesserocr import PyTessBaseAPI
        tesserocr_api = PyTessBaseAPI(lang='rus', psm=6, oem=3)
        use_tesserocr = True
        print("[COMBINED] Используется tesserocr для ускорения OCR.")
    except Exception as e:
        print(f"[COMBINED] tesserocr недоступен ({e}), используется pytesseract.")

    # === Загрузка шаблона футажа ===
    template_arr = _extract_template_array(template_png_path, footage_resize)

    # === Открытие видео ===
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть видео: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0:
        fps = 25.0

    # === Масштабирование ROI ===
    base_width, base_height = base_resolution
    scale_x = frame_width / base_width
    scale_y = frame_height / base_height
    x = int(roi["x"] * scale_x)
    y = int(roi["y"] * scale_y)
    w = int(roi["width"] * scale_x)
    h = int(roi["height"] * scale_y)

    print(f"[COMBINED] Разрешение: {frame_width}x{frame_height}, FPS: {fps:.2f}")
    print(f"[COMBINED] ROI: x={x}, y={y}, w={w}, h={h}")

    # === Диапазоны поиска в кадрах ===
    frame_ranges = []
    for start_sec, end_sec in search_ranges:
        start_frame = max(0, int(start_sec * fps))
        end_frame = min(total_frames, int(end_sec * fps))
        if start_frame < end_frame:
            frame_ranges.append((start_frame, end_frame))

    total_to_process = sum(end_f - start_f for start_f, end_f in frame_ranges)
    processed_count = 0

    # === Результаты ===
    osg_results: List[Dict[str, Any]] = []
    footage_results: List[float] = []
    next_allowed_osg_time = -float('inf')
    next_allowed_footage_time = -float('inf')

    # === Цикл по диапазонам ===
    # Если skip > 1, используем прыжки cap.set для чтения только нужных кадров
    use_jumps = (footage_skip > 1 or osg_skip > 1)

    for start_frame, end_frame in frame_ranges:
        if use_jumps:
            # Собираем только те кадры, которые нужны для Footage или OSD
            frames_to_process = []
            for frame_index in range(start_frame, end_frame):
                rel = frame_index - start_frame
                if rel % footage_skip == 0 or rel % osg_skip == 0:
                    frames_to_process.append(frame_index)
            total_to_process = len(frames_to_process)
            processed_count = 0

            for frame_index in frames_to_process:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = cap.read()
                if not ret:
                    continue
                current_time_sec = frame_index / fps
                processed_count += 1

                if progress_callback and (processed_count % 50 == 0 or processed_count == total_to_process):
                    progress_callback(processed_count, total_to_process)

                # --- Footage ---
                if (frame_index - start_frame) % footage_skip == 0 and current_time_sec >= next_allowed_footage_time:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    similarity = _calc_similarity(gray, template_arr, footage_resize)
                    if similarity >= footage_threshold:
                        footage_results.append(current_time_sec)
                        next_allowed_footage_time = current_time_sec + footage_debounce

                # --- OSD ---
                if (frame_index - start_frame) % osg_skip == 0 and current_time_sec >= next_allowed_osg_time:
                    roi_img = frame[y:y+h, x:x+w]
                    if roi_img.size == 0:
                        continue
                    processed_img = _preprocess_image(roi_img, osg_preprocess)
                    pil_img_roi = Image.fromarray(processed_img)
                    try:
                        if use_tesserocr and tesserocr_api is not None:
                            tesserocr_api.SetImage(pil_img_roi)
                            text = tesserocr_api.GetUTF8Text().strip()
                            confidences = tesserocr_api.AllWordConfidences()
                            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                        else:
                            import pytesseract
                            config = '--psm 6 --oem 3 -l rus'
                            data = pytesseract.image_to_data(
                                pil_img_roi, output_type=pytesseract.Output.DICT, config=config
                            )
                            words = [word.strip() for word in data['text'] if word.strip()]
                            text = ' '.join(words)
                            confidences = [conf for conf, word in zip(data['conf'], data['text']) if word.strip()]
                            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                    except Exception as e:
                        print(f"[COMBINED] Ошибка OCR на кадре {frame_index}: {e}")
                        continue

                    if text:
                        found_keyword = None
                        for kw in event_type_map:
                            if kw.upper() in text.upper():
                                found_keyword = kw
                                break

                        if found_keyword is not None:
                            event_type = event_type_map[found_keyword]
                            if avg_conf >= osg_corr_thresh:
                                osg_results.append({
                                    "global_time_sec": current_time_sec,
                                    "detected_text": text,
                                    "event_type": event_type,
                                    "confidence": avg_conf
                                })
                                next_allowed_osg_time = current_time_sec + osg_debounce
                                if osg_find_first_only:
                                    break

            if osg_find_first_only and osg_results:
                break
        else:
            # Последовательное чтение всех кадров (fallback если skip=1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            frame_index = start_frame

            while frame_index < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_index += 1
                current_time_sec = frame_index / fps
                processed_count += 1

                if progress_callback and (processed_count % 100 == 0 or processed_count == total_to_process):
                    progress_callback(processed_count, total_to_process)

                # --- Footage ---
                if (frame_index - start_frame) % footage_skip == 0 and current_time_sec >= next_allowed_footage_time:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    similarity = _calc_similarity(gray, template_arr, footage_resize)
                    if similarity >= footage_threshold:
                        footage_results.append(current_time_sec)
                        next_allowed_footage_time = current_time_sec + footage_debounce

                # --- OSD ---
                if (frame_index - start_frame) % osg_skip == 0 and current_time_sec >= next_allowed_osg_time:
                    roi_img = frame[y:y+h, x:x+w]
                    if roi_img.size == 0:
                        continue
                    processed_img = _preprocess_image(roi_img, osg_preprocess)
                    pil_img_roi = Image.fromarray(processed_img)
                    try:
                        if use_tesserocr and tesserocr_api is not None:
                            tesserocr_api.SetImage(pil_img_roi)
                            text = tesserocr_api.GetUTF8Text().strip()
                            confidences = tesserocr_api.AllWordConfidences()
                            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                        else:
                            import pytesseract
                            config = '--psm 6 --oem 3 -l rus'
                            data = pytesseract.image_to_data(
                                pil_img_roi, output_type=pytesseract.Output.DICT, config=config
                            )
                            words = [word.strip() for word in data['text'] if word.strip()]
                            text = ' '.join(words)
                            confidences = [conf for conf, word in zip(data['conf'], data['text']) if word.strip()]
                            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                    except Exception as e:
                        print(f"[COMBINED] Ошибка OCR на кадре {frame_index}: {e}")
                        continue

                    if text:
                        found_keyword = None
                        for kw in event_type_map:
                            if kw.upper() in text.upper():
                                found_keyword = kw
                                break

                        if found_keyword is not None:
                            event_type = event_type_map[found_keyword]
                            if avg_conf >= osg_corr_thresh:
                                osg_results.append({
                                    "global_time_sec": current_time_sec,
                                    "detected_text": text,
                                    "event_type": event_type,
                                    "confidence": avg_conf
                                })
                                next_allowed_osg_time = current_time_sec + osg_debounce
                                if osg_find_first_only:
                                    break

            if osg_find_first_only and osg_results:
                break

    cap.release()
    if tesserocr_api is not None:
        tesserocr_api.End()

    print(f"[COMBINED] Найдено OSD событий: {len(osg_results)}, футажей: {len(footage_results)}")
    return osg_results, footage_results
