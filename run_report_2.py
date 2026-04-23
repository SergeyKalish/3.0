import sys
import os

# === FIX: Настройка путей Qt ===
def setup_qt_plugins():
    possible_paths = [
        os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
        os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
    ]
    for path in possible_paths:
        platforms_path = os.path.join(path, 'platforms')
        if os.path.exists(os.path.join(platforms_path, 'qwindows.dll')):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = platforms_path
            print(f"Qt plugins найдены: {platforms_path}")
            return True
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

sys.path.insert(0, os.path.abspath('.'))

from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from modules.reports.season_report_data import SeasonReportDataCollector
from modules.reports.season_report_generator import PlayerSeasonReportGenerator
from modules.reports.ui.season_report_dialog import SeasonReportPlayerDialog


def main():
    app = QApplication(sys.argv)

    # 1. Выбор папки с .hkt
    hkt_folder = QFileDialog.getExistingDirectory(None, "Выберите папку с файлами .hkt")
    if not hkt_folder:
        print("Папка не выбрана. Выход.")
        return

    print(f"Сканирование папки: {hkt_folder}")

    # 2. Сбор данных
    try:
        collector = SeasonReportDataCollector(hkt_folder)
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"Ошибка при сканировании папки:\n{e}")
        return

    players = collector.get_players_list()
    if not players:
        QMessageBox.information(None, "Информация",
                                "В выбранной папке не найдено оконченных матчей или игроков.")
        return

    print(f"Найдено игроков: {len(players)}")
    print(f"Сезон: {collector.season_name}")

    # 3. Диалог выбора игроков
    dialog = SeasonReportPlayerDialog(players)
    if dialog.exec_() != QDialog.Accepted:
        print("Отменено пользователем.")
        return

    selected = dialog.get_selected()
    print(f"Выбрано игроков: {len(selected)}")

    # 4. Выбор папки для сохранения
    output_folder = QFileDialog.getExistingDirectory(None, "Выберите папку для сохранения отчётов")
    if not output_folder:
        print("Папка для сохранения не выбрана. Выход.")
        return

    # 5. Генерация
    generator = PlayerSeasonReportGenerator()
    saved_files = []

    for summary in selected:
        # Имя файла: {number}_{Фамилия}__stats.png
        surname = (summary.player_full_name or summary.player_name).split()[0]
        filename = f"{summary.player_number}_{surname}__stats.png"
        filepath = os.path.join(output_folder, filename)

        try:
            img = generator.generate(summary, collector.season_name, collector.player_db)
            img.save(filepath)
            print(f"Сохранён: {filepath}")
            saved_files.append(filepath)
        except Exception as e:
            print(f"Ошибка генерации для {summary.player_name}: {e}")
            import traceback
            traceback.print_exc()

    # 6. Уведомление
    if saved_files:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Успех")
        msg.setText(f"Сгенерировано отчётов: {len(saved_files)}")
        msg.setDetailedText("\n".join(saved_files))
        msg.exec_()
    else:
        QMessageBox.warning(None, "Внимание", "Не удалось сгенерировать ни одного отчёта.")


if __name__ == "__main__":
    main()
