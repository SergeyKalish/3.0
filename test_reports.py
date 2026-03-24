import sys
import os
from datetime import datetime

# === FIX: Настройка путей Qt ===
def setup_qt_plugins():
    """Автоматическая настройка путей к плагинам Qt"""
    possible_paths = [
        # Стандартный путь в venv
        os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
        # Альтернативный путь
        os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
        # PyQt5 в system Python
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
    ]
    
    for path in possible_paths:
        platforms_path = os.path.join(path, 'platforms')
        if os.path.exists(os.path.join(platforms_path, 'qwindows.dll')):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = platforms_path
            print(f"Qt plugins найдены: {platforms_path}")
            return True
    
    # Если не нашли, попробуем через PyQt5 напрямую
    try:
        import PyQt5
        qt_path = os.path.join(os.path.dirname(PyQt5.__file__), 'Qt5', 'plugins')
        if os.path.exists(qt_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(qt_path, 'platforms')
            print(f"Qt plugins через PyQt5: {qt_path}")
            return True
    except ImportError:
        pass
    
    return False

if not setup_qt_plugins():
    print("WARNING: Не удалось найти плагины Qt!")
    print("Попробуйте установить: pip install PyQt5 --force-reinstall")

# === Остальной код без изменений ===

sys.path.insert(0, os.path.abspath('.'))

from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox
from utils.helpers import load_project_from_file
from modules.reports import PlayerShiftMapReport, ReportData
from modules.reports.ui.report_generation_dialog import ReportGenerationDialog

# Путь к тестовому файлу
TEST_FILE_PATH = r"c:\code\3.0\TEST_REPORT_HKT_19_тур_10.01.2026_Русь 2014_vs_Созвездие 2014.hkt"
TEST_OUTPUT_DIR = os.path.dirname(TEST_FILE_PATH)


def main():
    app = QApplication(sys.argv)

    # === АВТОМАТИЧЕСКИЙ РЕЖИМ (без диалогов) ===
    # Для включения диалогов обратно закомментируйте этот блок и раскомментируйте старый ниже
    
    hkt_file_path = None
    is_test_mode = False
    
    # Проверяем тестовый файл - если есть, используем автоматически
    if os.path.exists(TEST_FILE_PATH):
        hkt_file_path = TEST_FILE_PATH
        is_test_mode = True
        print(f"[AUTO] Тестовый файл найден и выбран автоматически: {hkt_file_path}")
    else:
        # Если тестового файла нет - показываем диалог выбора
        print(f"[AUTO] Тестовый файл не найден: {TEST_FILE_PATH}")
        hkt_file_path, _ = QFileDialog.getOpenFileName(
            None, "Выберите файл проекта (.hkt)", "", "Файлы проектов (*.hkt);;Все файлы (*)"
        )
        is_test_mode = False

    if not hkt_file_path:
        print("Файл .hkt не выбран. Выход.")
        return

    print(f"Выбран файл: {hkt_file_path}")

    try:
        # Загрузка проекта
        project = load_project_from_file(hkt_file_path)
        print(f"Проект загружен: {project.video_path}")

        # === РАЗМЕР ЛИСТА ВСЕГДА A4 (без диалога) ===
        # Для включения диалога выбора размера раскомментируйте:
        # dialog = ReportGenerationDialog()
        # if dialog.exec_() != ReportGenerationDialog.Accepted:
        #     print("Генерация отчёта отменена пользователем.")
        #     return
        # selected_page_size = dialog.get_selected_params()
        
        selected_page_size = "A4"  # <-- РАЗМЕР ЛИСТА ВСЕГДА A4
        print(f"[AUTO] Размер листа: {selected_page_size}")

        # Создание отчёта с новой архитектурой
        report_data = ReportData(original_project=project)
        report_generator = PlayerShiftMapReport(page_size=selected_page_size)
        
        # Генерация ВСЕХ листов (новый метод generate_all)
        report_output = report_generator.generate_all(report_data)
        
        # Сохранение результатов
        now = datetime.now()
        current_timestamp = now.strftime("%d_%m_%H_%M_%S")
        
        # Определяем имена листов
        sheet_names = ["Матч"]
        for i in range(len(report_data.segments_info)):
            sheet_names.append(f"Период_{i+1}" if i < 3 else "Овертайм")
        
        saved_paths = []
        
        for idx, (img, name) in enumerate(zip(report_output, sheet_names)):
            if is_test_mode:
                # Автоматическое имя в тестовом режиме
                existing_test_files = [
                    f for f in os.listdir(TEST_OUTPUT_DIR)
                    if f.startswith("_TEST_REPORT_") and f.endswith(".png")
                ]
                existing_numbers = []
                for f in existing_test_files:
                    try:
                        num_str = f.split('_')[0]
                        if num_str.isdigit():
                            existing_numbers.append(int(num_str))
                    except (IndexError, ValueError):
                        continue
                
                base_n = max(existing_numbers) + 1 if existing_numbers else 1
                output_filename = f"{base_n}_{idx}_{name}_TEST_REPORT_{current_timestamp}.png"
                output_file_path = os.path.join(TEST_OUTPUT_DIR, output_filename)
            else:
                # Диалог сохранения
                output_file_path, _ = QFileDialog.getSaveFileName(
                    None,
                    f"Сохранить лист '{name}'",
                    f"{os.path.splitext(os.path.basename(hkt_file_path))[0]}_{name}_shift_map.png",
                    "PNG Files (*.png);;All Files (*)"
                )
            
            if output_file_path:
                img.save(output_file_path)
                print(f"Лист '{name}' сохранён: {output_file_path}")
                saved_paths.append(output_file_path)
            else:
                print(f"Сохранение листа '{name}' отменено.")
                if not is_test_mode:
                    break
        
        # Уведомление об успехе
        if saved_paths and not is_test_mode:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText("Отчёты успешно сгенерированы и сохранены.")
            msg_box.setInformativeText(f"Сохранено {len(saved_paths)} файлов:\n" + "\n".join(saved_paths))
            msg_box.setWindowTitle("Успех")
            msg_box.exec_()
        elif saved_paths and is_test_mode:
            print(f"Тестовый режим: сохранено {len(saved_paths)} файлов.")

    except Exception as e:
        print(f"Ошибка при генерации отчёта: {e}")
        import traceback
        traceback.print_exc()
        
        error_msg_box = QMessageBox()
        error_msg_box.setIcon(QMessageBox.Critical)
        error_msg_box.setText("Произошла ошибка при генерации отчёта.")
        error_msg_box.setInformativeText(str(e))
        error_msg_box.setWindowTitle("Ошибка")
        error_msg_box.exec_()


if __name__ == "__main__":
    main()