import sys
import os

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
from modules.reports import PlayerShiftMapReport, ReportData, SORT_BY_EXIT_TIME, SORT_BY_POSITION_BLOCKS
from modules.reports.ui.report_generation_dialog import ReportGenerationDialog


def main():
    app = QApplication(sys.argv)

    # === ДИАЛОГ ВЫБОРА ФАЙЛА HKT ===
    hkt_file_path, _ = QFileDialog.getOpenFileName(
        None, "Выберите файл проекта (.hkt)", "", "Файлы проектов (*.hkt);;Все файлы (*)"
    )

    if not hkt_file_path:
        print("Файл .hkt не выбран. Выход.")
        return

    print(f"Выбран файл: {hkt_file_path}")

    try:
        # Загрузка проекта
        project = load_project_from_file(hkt_file_path)
        print(f"Проект загружен: {project.video_path}")

        # === ДИАЛОГ ВЫБОРА ПАРАМЕТРОВ ОТЧЁТА ===
        dialog = ReportGenerationDialog()
        if dialog.exec_() != ReportGenerationDialog.Accepted:
            print("Генерация отчёта отменена пользователем.")
            return
        selected_page_size, selected_sort_order = dialog.get_selected_params()
        print(f"Выбран размер листа: {selected_page_size}")
        print(f"Выбран порядок заполнения: {selected_sort_order}")

        # Создание отчёта с новой архитектурой и выбранной сортировкой
        report_data = ReportData(original_project=project, sort_order=selected_sort_order)
        report_generator = PlayerShiftMapReport(page_size=selected_page_size)
        
        # Генерация ВСЕХ листов (новый метод generate_all)
        report_output = report_generator.generate_all(report_data)
        
        # Сохранение результатов
        # Определяем имена листов
        sheet_names = ["Матч"]
        for i in range(len(report_data.segments_info)):
            sheet_names.append(f"Период_{i+1}" if i < 3 else "Овертайм")
        
        # === ОДИН ДИАЛОГ ДЛЯ ВЫБОРА БАЗОВОГО ИМЕНИ ФАЙЛА ===
        base_name = os.path.splitext(os.path.basename(hkt_file_path))[0]
        default_filename = f"{base_name}_shift_map.png"
        
        base_output_path, _ = QFileDialog.getSaveFileName(
            None,
            "Выберите имя для отчёта (будут созданы файлы для всех листов)",
            default_filename,
            "PNG Files (*.png);;All Files (*)"
        )
        
        if not base_output_path:
            print("Сохранение отменено пользователем.")
            return
        
        # Получаем директорию и базовое имя без расширения
        output_dir = os.path.dirname(base_output_path)
        base_name_without_ext = os.path.splitext(os.path.basename(base_output_path))[0]
        
        saved_paths = []
        
        for idx, (img, name) in enumerate(zip(report_output, sheet_names)):
            # Формируем имя файла: базовое имя + название листа
            output_filename = f"{base_name_without_ext}_{name}.png"
            output_file_path = os.path.join(output_dir, output_filename)
            
            img.save(output_file_path)
            print(f"Лист '{name}' сохранён: {output_file_path}")
            saved_paths.append(output_file_path)
        
        # Уведомление об успехе
        if saved_paths:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText("Отчёты успешно сгенерированы и сохранены.")
            msg_box.setInformativeText(f"Сохранено {len(saved_paths)} файлов:\n" + "\n".join(saved_paths))
            msg_box.setWindowTitle("Успех")
            msg_box.exec_()

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
