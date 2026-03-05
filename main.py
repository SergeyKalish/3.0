# main.py

import os
import sys

# === НАСТРОЙКА QT ПЛАГИНОВ (должна быть ДО импорта PyQt5) ===
def setup_qt_plugins():
    """Автоматически находит и настраивает путь к Qt плагинам в venv"""
    # Проверяем, что мы в виртуальном окружении
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        venv_path = sys.prefix
        qt_plugin_path = os.path.join(venv_path, 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins')
        
        if os.path.exists(qt_plugin_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugin_path
            return True
    
    # Если не в venv, проверим стандартный путь (на всякий случай)
    alt_paths = [
        r'C:\Python314\Lib\site-packages\PyQt5\Qt5\plugins',
        r'C:\Python\Lib\site-packages\PyQt5\Qt5\plugins',
    ]
    for alt_path in alt_paths:
        if os.path.exists(alt_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = alt_path
            return True
    
    return False

# Вызываем настройку ДО импорта PyQt5
setup_qt_plugins()
# === КОНЕЦ НАСТРОЙКИ QT ===

import traceback
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def exception_hook(exc_type, exc_value, exc_traceback):
    print("Uncaught exception:", exc_type, exc_value)
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    sys.exit(1)


sys.excepthook = exception_hook


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()