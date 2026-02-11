# ui/protocol_validation_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
from PyQt5.QtCore import Qt
from typing import List, Dict, Any

class ProtocolValidationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent  # Сохраняем ссылку на MainWindow
        self.layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Тип", "t1", "t2", "Игрок", "Команда", "Детали"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)

        # Настройка ширины колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Тип
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # t1
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # t2
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Игрок
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Команда
        header.setSectionResizeMode(5, QHeaderView.Stretch)          # Детали

        self.table.cellDoubleClicked.connect(self.on_event_double_clicked)

        self.layout.addWidget(self.table)
        self.events = []

    def set_events(self, events: List[Dict[str, Any]]):
        """Заполняет таблицу событиями из match.events."""
        self.events = events
        self.table.setRowCount(len(events))

        for row, event in enumerate(events):
            # Колонка 0: Тип
            event_type = "Гол" if event.get("type") == "goal" else "Удаление"
            self.table.setItem(row, 0, QTableWidgetItem(event_type))

            # Колонка 1: t1
            time1_sec = event.get("time_sec") if event_type == "Гол" else event.get("start_time_sec", 0)
            time1_str = f"{time1_sec // 60:02d}:{time1_sec % 60:02d}" if time1_sec is not None else ""
            self.table.setItem(row, 1, QTableWidgetItem(time1_str))

            # Колонка 2: t2
            time2_sec = None
            if event_type == "Удаление":
                time2_sec = event.get("end_time_sec", 0)
            time2_str = f"{time2_sec // 60:02d}:{time2_sec % 60:02d}" if time2_sec is not None else ""
            self.table.setItem(row, 2, QTableWidgetItem(time2_str))

            # Колонка 3: Игрок
            player_name = event.get("player_name", "—")
            self.table.setItem(row, 3, QTableWidgetItem(player_name))

            # Колонка 4: Команда
            team_key = event.get("team", "—")
            self.table.setItem(row, 4, QTableWidgetItem(team_key))

            # Колонка 5: Детали
            details = self._format_details(event)
            self.table.setItem(row, 5, QTableWidgetItem(details))

    def on_event_double_clicked(self, row: int, column: int):
        """Обработчик двойного клика по ячейке."""
        if row >= len(self.events):
            return

        event = self.events[row]
        event_type = "Гол" if event.get("type") == "goal" else "Удаление"

        # Определяем протокольное время
        if column == 1:  # t1
            if event_type == "Гол":
                time_sec = event.get("time_sec", 0)
            else:
                time_sec = event.get("start_time_sec", 0)
        elif column == 2:  # t2
            if event_type == "Удаление":
                time_sec = event.get("end_time_sec", 0)
            else:
                return
        else:
            return

        # 1. Определяем период и локальное время
        period_index = time_sec // 1200
        t_proto = time_sec % 1200
        period_num = period_index + 1
        period_name = f"Период {period_num}"

        # 2. Находим СЕГМЕНТ периода (не ЧИИ!)
        period_range = None
        for cr in self.main_window.project.match.calculated_ranges:
            if cr.name == period_name and cr.label_type == "Сегмент":
                period_range = cr
                break

        if period_range is None:
            QMessageBox.warning(self, "Предупреждение", f"Не найден сегмент '{period_name}'. Сначала разметьте 'Сегменты' и запустите SMART.")
            return

        # 3. Переключаем плеер на нужный период
        self.main_window._select_range_in_selector_and_playback(period_name)

        # 4. Находим все ЧИИ этого периода
        chi_ranges = []
        for cr in self.main_window.project.match.calculated_ranges:
            if cr.label_type == "ЧИИ" and cr.name.startswith(f"{period_name}. ЧИИ"):
                chi_ranges.append(cr)

        if not chi_ranges:
            QMessageBox.warning(self, "Предупреждение", f"Не найдены ЧИИ для {period_name}. Сначала разметьте паузы и запустите SMART.")
            return

        chi_ranges.sort(key=lambda x: x.start_time)

        # 5. Проекция на ЧИИ
        accumulated = 0.0
        target_global_time = None
        for chi in chi_ranges:
            chi_duration = chi.end_time - chi.start_time
            if accumulated + chi_duration >= t_proto:
                offset_in_chi = t_proto - accumulated
                target_global_time = chi.start_time + offset_in_chi
                break
            accumulated += chi_duration

        if target_global_time is None:
            QMessageBox.warning(self, "Предупреждение", f"Событие выходит за пределы всех ЧИИ {period_name}.")
            return

        # 6. Сохраняем событие для context
        self.main_window.set_active_protocol_event(dict(event))

        # 7. Устанавливаем фокус и тип метки
        self.main_window.video_player_widget.setFocus()
        self.main_window.universal_label_editor_widget.set_current_label_type(event_type)

        # 8. Переходим к времени
        self.main_window.go_to_time(target_global_time)

        self.main_window.status_label.setText(
            f"Перешли к {event_type}: {event.get('player_name', '—')} "
            f"(время: {target_global_time:.1f}s, в {period_name})"
        )
        # Обновляем активный диапазон на TimelineWidget
        self.main_window._update_timeline_active_range(period_name)
        
    def _format_details(self, event: Dict[str, Any]) -> str:
        """Форматирует детали события для отображения."""
        event_type = event.get("type")
        if event_type == "goal":
            assists = []
            if event.get("f-pass") != "N/A":
                assists.append(event.get("f-pass", ""))
            if event.get("s-pass") != "N/A":
                assists.append(event.get("s-pass", ""))
            if assists:
                return f": {', '.join(assists)}"
            else:
                return "Без ассистов"
        elif event_type == "penalty":
            violation = event.get("violation_type", "Нарушение не указано")
            duration = event.get("end_time_sec", 0) - event.get("start_time_sec", 0)
            if duration > 0:
                return f"{violation} ({int(duration)} с)"
            else:
                return violation
        return ""