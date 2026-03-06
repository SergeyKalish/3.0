#!/usr/bin/env python3
"""
Обёртка для запуска auto_draft_marker из корня проекта.
Запуск: python run_marker.py
"""

import os
import sys
import subprocess

# === АВТОПОИСК ПУТИ К QT ПЛАГИНАМ ===
def find_qt_plugins():
    """Ищет папку с Qt плагинами."""
    venv_scripts = os.path.dirname(sys.executable)
    venv_base = os.path.dirname(venv_scripts)
    site_packages = os.path.join(venv_base, 'Lib', 'site-packages')
    
    plugins_path = os.path.join(site_packages, 'PyQt5', 'Qt5', 'plugins')
    qwindows = os.path.join(plugins_path, 'platforms', 'qwindows.dll')
    if os.path.exists(qwindows):
        return plugins_path
    return None

# Устанавливаем переменную окружения для Qt
qt_plugins = find_qt_plugins()
if qt_plugins:
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugins

# === НАСТРОЙКА TESSERACT ===
# Укажите правильный путь если Tesseract не в PATH
tesseract_path = r"C:\Program Files\Tesseract-OCR"
if os.path.exists(tesseract_path):
    os.environ['PATH'] = tesseract_path + os.pathsep + os.environ.get('PATH', '')
    os.environ['TESSDATA_PREFIX'] = os.path.join(tesseract_path, 'tessdata')
    print(f"[run_marker] Добавлен Tesseract: {tesseract_path}")

# === ЗАПУСК МОДУЛЯ ===
def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    
    print(f"[run_marker] Рабочая директория: {project_root}")
    print(f"[run_marker] Запуск: python -m modules.auto_draft_marker")
    print("-" * 50)
    
    result = subprocess.run(
        [sys.executable, "-m", "modules.auto_draft_marker"],
        cwd=project_root,
        env=os.environ
    )
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()