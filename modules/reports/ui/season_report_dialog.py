"""
UI-диалоги для Отчёта №2 «Сводная статистика игрока».
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QFileDialog,
    QMessageBox
)
from PyQt5.QtCore import Qt
from modules.reports.season_report_data import PlayerSeasonSummary


class SeasonReportPlayerDialog(QDialog):
    """
    Диалог выбора игроков для генерации отчёта.
    """
    def __init__(self, players: list[PlayerSeasonSummary], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор игроков для отчёта")
        self.setMinimumSize(500, 600)
        self.players = players
        self.selected_players: list[PlayerSeasonSummary] = []

        layout = QVBoxLayout()

        # Заголовок
        info = QLabel(f"Найдено игроков: {len(players)}  |  Выберите нужных:")
        layout.addWidget(info)

        # Список игроков
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        for p in players:
            item = QListWidgetItem(f"№{p.player_number}  {p.player_full_name or p.player_name}  ({len(p.matches)} матчей)")
            item.setData(Qt.UserRole, p)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        # Кнопки управления выбором
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Выбрать все")
        self.btn_deselect_all = QPushButton("Снять все")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        layout.addLayout(btn_layout)

        # OK / Отмена
        ok_cancel = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Отмена")
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)
        ok_cancel.addWidget(self.btn_ok)
        ok_cancel.addWidget(self.btn_cancel)
        layout.addLayout(ok_cancel)

        self.setLayout(layout)

    def _select_all(self):
        self.list_widget.selectAll()

    def _deselect_all(self):
        self.list_widget.clearSelection()

    def _on_ok(self):
        self.selected_players = [
            item.data(Qt.UserRole)
            for item in self.list_widget.selectedItems()
        ]
        if not self.selected_players:
            QMessageBox.warning(self, "Внимание", "Не выбран ни один игрок.")
            return
        self.accept()

    def get_selected(self) -> list[PlayerSeasonSummary]:
        return self.selected_players
