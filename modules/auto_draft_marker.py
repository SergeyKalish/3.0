# modules/auto_draft_marker.py
"""
Модуль для автоматического создания черновых меток ("Черн.OSD", "Черн.FOOTAGE")
в проекте Hockey Tagger на основе анализа видео в пределах размеченных Сегментов.
"""

import os
import sys
import uuid
import time
from typing import List, Tuple, Optional, Dict, Any
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtCore import Qt
# Импорты из основного проекта
try:
    from model.project import Project
    from utils.helpers import load_project_from_file, save_project_to_file
    # Импорты модулей анализа
    from modules.on_screen_graphics_detection import detect_osg_events
    from modules.footage_detection import find_video_template
except ImportError as e:
    print(f"[auto_draft_marker] Ошибка импорта: {e}")
    print("Убедитесь, что структура проекта позволяет импортировать model.project, utils.helpers, и модули анализа.")
    sys.exit(1)

# --- В начале файла auto_draft_marker.py, добавим глобальную переменную ---
_last_printed_percent = -1 # Значение процента, которое последний раз было выведено


def simple_progress_callback(current: int, total: int):
    """
    Простейший прогрессбар в консоли.
    Обновляет строку только если целое число процента изменилось.
    """
    global _last_printed_percent # <-- Объявляем _last_printed_percent как глобальную ПЕРЕД использованием
    if total == 0:
        percent = 100
    else:
        percent = min(100, int(100 * current / total))

    # Если процент не изменился с прошлого раза, не выводим ничего
    if percent == _last_printed_percent:
        return

    # Обновляем последний выведенный процент
    _last_printed_percent = percent

    bar_length = 40
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    # Используем print с end='', чтобы обновлять строку
    print(f'\r[auto_draft_marker] Прогресс: |{bar}| {percent}% ({current}/{total})', end='', flush=True)
    if current == total:
        print()  # Новая строка по завершении
        _last_printed_percent = -1 # Сбросим счётчик при завершении


def load_project(hkt_file_path: str) -> Optional[Project]:
    """
    Загружает проект из .hkt файла.

    Args:
        hkt_file_path: Путь к .hkt файлу.

    Returns:
        Объект Project или None в случае ошибки.
    """
    try:
        project = load_project_from_file(hkt_file_path)
        print(f"[auto_draft_marker] Проект загружен: {os.path.basename(hkt_file_path)}")
        return project
    except Exception as e:
        print(f"[auto_draft_marker] Ошибка загрузки проекта {hkt_file_path}: {e}")
        return None


def save_project(project: Project, hkt_file_path: str) -> bool:
    """
    Сохраняет проект в .hkt файл.

    Args:
        project: Объект Project для сохранения.
        hkt_file_path: Путь к .hkt файлу для записи.

    Returns:
        True, если сохранение прошло успешно, иначе False.
    """
    try:
        save_project_to_file(project, hkt_file_path)
        print(f"[auto_draft_marker] Проект сохранён: {os.path.basename(hkt_file_path)}")
        return True
    except Exception as e:
        print(f"[auto_draft_marker] Ошибка сохранения проекта {hkt_file_path}: {e}")
        return False


def find_segment_ranges(project: Project) -> List[Tuple[float, float]]:
    """
    Находит временные диапазоны (start_time, end_time) для Сегментов (Периоды, Овертайм).

    Args:
        project: Объект Project.

    Returns:
        Список кортежей (start_time, end_time) для найденных Сегментов.
        Возвращает пустой список, если Сегменты не найдены.
    """
    segment_ranges = []
    for range_obj in project.match.calculated_ranges:
        # Проверяем label_type и name
        if range_obj.label_type == "Сегмент":
            name_lower = range_obj.name.lower()
            if "период" in name_lower or "овертайм" in name_lower:
                segment_ranges.append((range_obj.start_time, range_obj.end_time))
                print(f"[auto_draft_marker] Найден Сегмент: {range_obj.name} ({range_obj.start_time:.2f} - {range_obj.end_time:.2f})")

    if not segment_ranges:
        print("[auto_draft_marker] Предупреждение: Не найдено Сегментов (Период, Овертайм). Анализ не будет запущен.")
    else:
        print(f"[auto_draft_marker] Найдено {len(segment_ranges)} Сегментов для анализа.")

    return segment_ranges


def remove_existing_draft_labels(project: Project) -> int:
    """
    Удаляет все GenericLabel, у которых label_type начинается с "Черн.".

    Args:
        project: Объект Project.

    Returns:
        Количество удалённых меток.
    """
    initial_count = len(project.match.generic_labels)
    # Фильтруем список, оставляя только метки, не начинающиеся на "Черн."
    filtered_labels = [label for label in project.match.generic_labels if not label.label_type.startswith("Черн.")]
    removed_count = initial_count - len(filtered_labels)

    project.match.generic_labels = filtered_labels
    print(f"[auto_draft_marker] Удалено {removed_count} старых черновых меток (label_type.startswith('Черн.')).")
    return removed_count


def run_osg_detection(video_path: str, search_ranges: List[Tuple[float, float]], roi: Dict[str, int], event_type_map: Dict[str, str], params: Dict[str, Any], progress_callback=None) -> List[Dict[str, Any]]:
    """
    Вызывает on_screen_graphics_detection.detect_osg_events с параметрами из словаря params.
    """
    debounce_seconds = params.get("osg_debounce_seconds", 5.0)
    correlation_threshold = params.get("osg_correlation_threshold", 0.8)
    preprocess_method = params.get("osg_preprocess_method", 0)
    skip_every_n = params.get("osg_skip_every_n", 5)
    find_first_only = params.get("osg_find_first_only", False)

    print(f"[auto_draft_marker] Параметры OSG: skip_every_n={skip_every_n}, debounce={debounce_seconds}, correlation_threshold={correlation_threshold}")
    start_time = time.time()
    results = detect_osg_events(
        video_path=video_path,
        roi=roi,
        event_type_map=event_type_map,
        search_ranges=search_ranges,
        debounce_seconds=debounce_seconds,
        correlation_threshold=correlation_threshold,
        preprocess_method=preprocess_method,
        skip_every_n=skip_every_n,
        find_first_only=find_first_only,
        progress_callback=progress_callback
    )
    elapsed = time.time() - start_time
    print(f"\n[auto_draft_marker] OSG-анализ занял {elapsed:.2f} сек.")
    print(f"[auto_draft_marker] OSG-анализ завершён. Найдено {len(results)} событий.")
    return results


def convert_osg_results_to_labels(osg_results: List[Dict[str, Any]]) -> List[object]:
    """
    Преобразует результаты OSG в список GenericLabel.
    """
    from model.project import GenericLabel # Импорт внутри функции, чтобы избежать проблем при загрузке модуля
    labels = []
    for item in osg_results:
        label = GenericLabel(
            id=str(uuid.uuid4()),
            label_type="Черн.OSD",
            global_time=item['global_time_sec'],
            context={"detected_text": item['detected_text'], "confidence": item['confidence']}
        )
        labels.append(label)
    return labels


def run_footage_detection(video_path: str, template_png_path: str, search_ranges: List[Tuple[float, float]], params: Dict[str, Any], progress_callback=None) -> List[float]:
    """
    Вызывает footage_detection.find_video_template с параметрами из словаря params.
    """
    threshold = params.get("footage_threshold", 0.9)
    resize = params.get("footage_resize", (16, 16))
    skip_every_n = params.get("footage_skip_every_n", 10)
    debounce_seconds = params.get("footage_debounce_seconds", 5.0) # <-- Новый параметр, передаётся в find_video_template

    print(f"[auto_draft_marker] Параметры Footage: skip_every_n={skip_every_n}, threshold={threshold}, resize={resize}, debounce={debounce_seconds}")
    start_time = time.time()
    results = find_video_template(
        main_video_path=video_path,
        template_png_path=template_png_path,
        threshold=threshold,
        resize=resize,
        skip_every_n=skip_every_n,
        search_ranges=search_ranges,
        debounce_seconds=debounce_seconds, # <-- Передаём debounce_seconds внутрь
        progress_callback=progress_callback
    )
    elapsed = time.time() - start_time
    print(f"\n[auto_draft_marker] Footage-анализ занял {elapsed:.2f} сек.")
    print(f"[auto_draft_marker] Footage-анализ завершён. Найдено {len(results)} футажей.")
    return results


def convert_footage_results_to_labels(footage_results: List[float]) -> List[object]:
    """
    Преобразует результаты Footage в список GenericLabel.
    """
    from model.project import GenericLabel
    labels = []
    for time_val in footage_results:
        label = GenericLabel(
            id=str(uuid.uuid4()),
            label_type="Черн.FOOTAGE",
            global_time=time_val,
            context={} # Можно добавить путь к шаблону, если нужно
        )
        labels.append(label)
    return labels


def process_project(
    hkt_file_path: str,
    template_png_path: str,
    osg_params: Dict[str, Any], # {"roi": ..., "event_type_map": ..., ...}
    analysis_params: Dict[str, Any] # {"osg_skip_every_n": ..., "footage_threshold": ..., ...}
) -> bool:
    """
    Основная функция обработки проекта.
    """
    print(f"[auto_draft_marker] Начинаю обработку проекта: {os.path.basename(hkt_file_path)}")
    # 1. Загрузка проекта
    project = load_project(hkt_file_path)
    if not project:
        return False

    # 2. Поиск Сегментов
    search_ranges = find_segment_ranges(project)
    if not search_ranges:
        print("[auto_draft_marker] Остановка: нет сегментов для анализа.")
        return False

    # 3. Удаление старых черновых меток
    remove_existing_draft_labels(project)

    # 4. Вызов анализа
    # --- OSG ---
    osg_results = run_osg_detection(
        video_path=project.video_path,
        search_ranges=search_ranges,
        roi=osg_params.get("roi", {"x": 151, "y": 92, "width": 91, "height": 34}),
        event_type_map=osg_params.get("event_type_map", {"ГОЛ": "Goal"}), # <-- Сокращённый event_type_map
        params=analysis_params,
        progress_callback=simple_progress_callback
    )
    converted_osg_labels = convert_osg_results_to_labels(osg_results)

    # --- Footage ---
    footage_results = run_footage_detection(
        video_path=project.video_path,
        template_png_path=template_png_path,
        search_ranges=search_ranges,
        params=analysis_params,
        progress_callback=simple_progress_callback
    )
    converted_footage_labels = convert_footage_results_to_labels(footage_results)

    # 5. Добавление новых меток
    project.match.generic_labels.extend(converted_osg_labels)
    project.match.generic_labels.extend(converted_footage_labels)
    print(f"[auto_draft_marker] Добавлено {len(converted_osg_labels)} меток 'Черн.OSD' и {len(converted_footage_labels)} меток 'Черн.FOOTAGE'.")

    # 6. Сохранение проекта
    success = save_project(project, hkt_file_path)
    if success:
        print(f"[auto_draft_marker] Обработка проекта {os.path.basename(hkt_file_path)} завершена успешно.")
    else:
        print(f"[auto_draft_marker] Обработка проекта {os.path.basename(hkt_file_path)} завершена с ошибкой сохранения.")
    return success


class ParamsDialog(QDialog):
    """
    Диалог для ввода параметров анализа.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры анализа")
        self.setModal(True)

        layout = QVBoxLayout()

        # --- Параметры OSG ---
        layout.addWidget(QLabel("Параметры OSG (on-screen graphics):"))
        self.osg_skip_every_n_edit = QLineEdit("20")
        layout.addWidget(QLabel("skip_every_n (OSG):"))
        layout.addWidget(self.osg_skip_every_n_edit)

        self.osg_debounce_edit = QLineEdit("30.0")
        layout.addWidget(QLabel("debounce_seconds (OSG):"))
        layout.addWidget(self.osg_debounce_edit)

        self.osg_corr_thresh_edit = QLineEdit("0.8")
        layout.addWidget(QLabel("correlation_threshold (OSG):"))
        layout.addWidget(self.osg_corr_thresh_edit)

        self.osg_preprocess_edit = QLineEdit("0")
        layout.addWidget(QLabel("preprocess_method (OSG):"))
        layout.addWidget(self.osg_preprocess_edit)

        self.osg_find_first_edit = QLineEdit("False")
        layout.addWidget(QLabel("find_first_only (OSG) (True/False):"))
        layout.addWidget(self.osg_find_first_edit)

        # --- Параметры Footage ---
        layout.addWidget(QLabel("Параметры Footage (поиск футажей):"))
        self.footage_skip_every_n_edit = QLineEdit("20")
        layout.addWidget(QLabel("skip_every_n (Footage):"))
        layout.addWidget(self.footage_skip_every_n_edit)

        self.footage_threshold_edit = QLineEdit("0.9")
        layout.addWidget(QLabel("threshold (Footage):"))
        layout.addWidget(self.footage_threshold_edit)

        self.footage_resize_edit = QLineEdit("(16, 16)")
        layout.addWidget(QLabel("resize (Footage) (например, (16, 16)):"))
        layout.addWidget(self.footage_resize_edit)

        # --- Новый параметр: Footage Debounce ---
        self.footage_debounce_edit = QLineEdit("5.0")
        layout.addWidget(QLabel("debounce_seconds (Footage):"))
        layout.addWidget(self.footage_debounce_edit)

        # --- Кнопки ---
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Отмена")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_params(self) -> Dict[str, Any]:
        """
        Возвращает словарь с параметрами, введёнными пользователем.
        """
        params = {}
        try:
            params["osg_skip_every_n"] = int(self.osg_skip_every_n_edit.text())
            params["osg_debounce_seconds"] = float(self.osg_debounce_edit.text())
            params["osg_correlation_threshold"] = float(self.osg_corr_thresh_edit.text())
            params["osg_preprocess_method"] = int(self.osg_preprocess_edit.text())
            find_first_text = self.osg_find_first_edit.text().strip().lower()
            params["osg_find_first_only"] = find_first_text in ("true", "1", "yes")
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Некорректное значение для параметра OSG. Используются значения по умолчанию.")
            # Возвращаем значения по умолчанию в случае ошибки
            params.update({
                "osg_skip_every_n": 5,
                "osg_debounce_seconds": 5.0,
                "osg_correlation_threshold": 0.8,
                "osg_preprocess_method": 0,
                "osg_find_first_only": False
            })

        try:
            params["footage_skip_every_n"] = int(self.footage_skip_every_n_edit.text())
            params["footage_threshold"] = float(self.footage_threshold_edit.text())
            # Обработка строки resize
            resize_str = self.footage_resize_edit.text().strip()
            # Убираем скобки и разбиваем по запятой
            resize_clean = resize_str.replace("(", "").replace(")", "")
            x_str, y_str = resize_clean.split(",")
            params["footage_resize"] = (int(x_str.strip()), int(y_str.strip()))
            params["footage_debounce_seconds"] = float(self.footage_debounce_edit.text()) # <-- Новый параметр
        except (ValueError, IndexError):
            QMessageBox.warning(self, "Ошибка", "Некорректное значение для параметра Footage. Используются значения по умолчанию.")
            params.update({
                "footage_skip_every_n": 10,
                "footage_threshold": 0.9,
                "footage_resize": (16, 16),
                "footage_debounce_seconds": 5.0 # <-- Новый параметр по умолчанию
            })

        return params


def main_interactive():
    """
    Интерактивная точка входа для ручного тестирования.
    """
    print("\n--- Запуск auto_draft_marker (интерактивный режим) ---")
    # Инициализируем QApplication для QFileDialog и ParamsDialog
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()

    # 1. Выбор .hkt файла
    hkt_path, _ = QFileDialog.getOpenFileName(None, "Выберите файл проекта (.hkt)", "", "Файлы проектов (*.hkt)")
    if not hkt_path:
        print("Не выбран .hkt файл. Завершение.")
        return
    print(f"Выбран проект: {os.path.basename(hkt_path)}")

    # 2. Выбор PNG шаблона футажа
    # --- ИСПОЛЬЗУЕМ ШАБЛОН ПО УМОЛЧАНИЮ ---
    default_template_path = r"c:\hockey\4.0\3.0\data\league_logo_footage.png"
    if os.path.exists(default_template_path):
        reply = QMessageBox.information(None, "Шаблон футажа", f"Найден шаблон по умолчанию:\n{default_template_path}\n\nИспользовать его?", QMessageBox.Yes | QMessageBox.No)
        use_default = reply == QMessageBox.Yes # <-- Исправлено

        if use_default:
            png_path = default_template_path
            print(f"Используется шаблон по умолчанию: {os.path.basename(png_path)}")
        else:
            png_path, _ = QFileDialog.getOpenFileName(None, "Выберите PNG-шаблон футажа", "", "PNG файлы (*.png)")
            if not png_path:
                print("Не выбран PNG-шаблон футажа. Завершение.")
                return
            print(f"Выбран шаблон футажа: {os.path.basename(png_path)}")
    else:
        # Если шаблон по умолчанию не найден, просим выбрать
        png_path, _ = QFileDialog.getOpenFileName(None, "Выберите PNG-шаблон футажа", "", "PNG файлы (*.png)")
        if not png_path:
            print("Не выбран PNG-шаблон футажа. Завершение.")
            return
        print(f"Выбран шаблон футажа: {os.path.basename(png_path)}")

    # 3. Параметры OSG (теперь только "ГОЛ")
    osg_params = {
        "roi": {"x": 151, "y": 92, "width": 91, "height": 34}, # Пример ROI
        "event_type_map": {"ГОЛ": "Goal"} # <-- Сокращённый event_type_map
    }
    print(f"Используемые параметры OSG (ROI, event_type_map): {osg_params}")

    # 4. Диалог ввода параметров анализа
    params_dialog = ParamsDialog()
    if params_dialog.exec_() != QDialog.Accepted:
        print("Оператор отменил ввод параметров. Завершение.")
        return

    analysis_params = params_dialog.get_params()
    print(f"Получены параметры анализа: {analysis_params}")

    # 5. Запуск процесса
    success = process_project(hkt_path, png_path, osg_params, analysis_params)

    # 6. Результат
    if success:
        QMessageBox.information(None, "Успех", f"Обработка проекта '{os.path.basename(hkt_path)}' завершена.\nЧерновые метки добавлены.")
    else:
        QMessageBox.critical(None, "Ошибка", f"Обработка проекта '{os.path.basename(hkt_path)}' завершена с ошибкой.")


def main():
    """
    Точка входа для запуска из командной строки (опционально).
    """
    print("[auto_draft_marker] Запуск через main(). Для интерактивного режима используйте main_interactive().")
    # Здесь можно реализовать логику запуска с аргументами командной строки, если потребуется.


if __name__ == "__main__":
    # Запускаем интерактивный режим при запуске скрипта напрямую
    main_interactive()