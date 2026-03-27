#!/usr/bin/env python3
"""
Модуль для подготовки команды объединения PNG-файлов в PDF.
Показывает диалог выбора файлов и выводит команду для img2pdf,
которую нужно запустить отдельно (чтобы избежать конфликта с PyQt5).

Порядок страниц в PDF задаётся в диалоге переупорядочивания.
"""

import sys
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMessageBox, 
                             QDialog, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QListWidgetItem, QPushButton,
                             QLabel, QWidget, QTextEdit, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QClipboard


class OrderDialog(QDialog):
    """Диалог для изменения порядка файлов."""
    
    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files
        self.setWindowTitle("Порядок файлов в PDF")
        self.setMinimumSize(600, 450)
        
        layout = QVBoxLayout()
        
        # Инструкция
        label = QLabel("Файлы будут добавлены в PDF в указанном порядке.\n"
                      "Используйте кнопки ▲ ▼ для изменения порядка.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        # Список файлов
        self.list_widget = QListWidget()
        for f in files:
            item = QListWidgetItem(Path(f).name)
            item.setData(Qt.UserRole, f)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        
        self.btn_up = QPushButton("▲ Вверх")
        self.btn_up.clicked.connect(self.move_up)
        btn_layout.addWidget(self.btn_up)
        
        self.btn_down = QPushButton("▼ Вниз")
        self.btn_down.clicked.connect(self.move_down)
        btn_layout.addWidget(self.btn_down)
        
        btn_layout.addStretch()
        
        self.btn_sort_name = QPushButton("📝 По имени")
        self.btn_sort_name.setToolTip("Сортировать по имени файла (A-Z)")
        self.btn_sort_name.clicked.connect(self.sort_by_name)
        btn_layout.addWidget(self.btn_sort_name)
        
        self.btn_sort_date = QPushButton("📅 По дате")
        self.btn_sort_date.setToolTip("Сортировать по дате изменения (старые → новые)")
        self.btn_sort_date.clicked.connect(self.sort_by_date)
        btn_layout.addWidget(self.btn_sort_date)
        
        layout.addLayout(btn_layout)
        
        # Кнопки действий
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.btn_ok = QPushButton("✓ Подготовить команду")
        self.btn_ok.clicked.connect(self.accept)
        action_layout.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("✗ Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        action_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(action_layout)
        self.setLayout(layout)
    
    def move_up(self):
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, item)
            self.list_widget.setCurrentItem(item)
    
    def move_down(self):
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row + 1, item)
            self.list_widget.setCurrentItem(item)
    
    def get_ordered_files(self):
        """Возвращает список файлов в выбранном порядке."""
        files = []
        for i in range(self.list_widget.count()):
            files.append(self.list_widget.item(i).data(Qt.UserRole))
        return files
    
    def sort_by_name(self):
        """Сортирует файлы по имени (алфавитный порядок)."""
        files = self.get_ordered_files()
        files.sort(key=lambda f: Path(f).name.lower())
        
        self.list_widget.clear()
        for f in files:
            item = QListWidgetItem(Path(f).name)
            item.setData(Qt.UserRole, f)
            self.list_widget.addItem(item)
    
    def sort_by_date(self):
        """Сортирует файлы по дате изменения (от старых к новым)."""
        files = self.get_ordered_files()
        files.sort(key=lambda f: Path(f).stat().st_mtime)
        
        self.list_widget.clear()
        for f in files:
            item = QListWidgetItem(Path(f).name)
            item.setData(Qt.UserRole, f)
            self.list_widget.addItem(item)


class ResultDialog(QDialog):
    """Диалог с результатом - командой для запуска."""
    
    def __init__(self, files, output_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Команда для создания PDF")
        self.setMinimumSize(750, 500)
        
        self.files = files
        self.output_path = output_path
        
        layout = QVBoxLayout()
        
        # Инструкция
        label = QLabel("Скопируйте эту команду и выполните её в терминале:\n"
                      "(img2pdf должен быть установлен: pip install img2pdf)")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        # Поле с командой
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.text_edit)
        
        # Обновляем текст команды
        self.update_command_text()
        
        # Список файлов в порядке страниц
        files_label = QLabel("Порядок страниц в PDF:")
        layout.addWidget(files_label)
        
        files_text = QTextEdit()
        files_text.setReadOnly(True)
        files_text.setMaximumHeight(100)
        files_text.setStyleSheet("font-family: Consolas, monospace; font-size: 10px; background: #f5f5f5;")
        
        files_list = "\n".join([f"{i+1}. {Path(f).name}" for i, f in enumerate(files)])
        files_text.setPlainText(files_list)
        layout.addWidget(files_text)
        
        # Информация о выходном файле
        info_label = QLabel(f"PDF будет сохранён как: {output_path}")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-weight: bold; color: #006400;")
        layout.addWidget(info_label)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton("📋 Копировать команду")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(btn_copy)
        
        btn_layout.addStretch()
        
        btn_close = QPushButton("✓ Закрыть")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def update_command_text(self):
        """Формирует команду для img2pdf."""
        escaped_files = [f'"{f}"' for f in self.files]
        files_str = " ".join(escaped_files)
        command = f'venv\\Scripts\\python.exe -m img2pdf {files_str} -o "{self.output_path}"'
        self.text_edit.setPlainText(command)
    
    def copy_to_clipboard(self):
        """Копирует команду в буфер обмена."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "Скопировано", "Команда скопирована в буфер обмена!")


class PngToPdfConverter(QWidget):
    """Главное окно конвертера."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("PNG в PDF (через img2pdf)")
        self.setMinimumSize(400, 200)
        
        layout = QVBoxLayout()
        
        # Инструкция
        label = QLabel("Выберите PNG-файлы и настройте их порядок для создания PDF.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        # Кнопка выбора файлов
        btn_select = QPushButton("📁 Выбрать PNG-файлы...")
        btn_select.clicked.connect(self.select_files)
        layout.addWidget(btn_select)
        
        # Предупреждение
        warn_label = QLabel("⚠️ img2pdf должен быть установлен:\npip install img2pdf")
        warn_label.setAlignment(Qt.AlignCenter)
        warn_label.setStyleSheet("color: orange; font-size: 10px;")
        layout.addWidget(warn_label)
        
        self.setLayout(layout)
    
    def select_files(self):
        """Открывает диалог выбора файлов."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите PNG-файлы",
            "",
            "PNG Images (*.png);;All Files (*)",
            options=QFileDialog.Options()
        )
        
        if not files:
            return
        
        # Показываем диалог изменения порядка (QFileDialog всегда сортирует по алфавиту)
        dialog = OrderDialog(files, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        
        ordered_files = dialog.get_ordered_files()
        
        # Диалог сохранения PDF
        default_name = Path(ordered_files[0]).stem + ".pdf"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить PDF как...",
            default_name,
            "PDF Files (*.pdf);;All Files (*)",
            options=QFileDialog.Options()
        )
        
        if not output_path:
            return
        
        if not output_path.endswith('.pdf'):
            output_path += '.pdf'
        
        # Показываем результат с командой
        result_dialog = ResultDialog(ordered_files, output_path, self)
        result_dialog.exec_()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    converter = PngToPdfConverter()
    converter.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
