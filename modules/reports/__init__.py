"""
Модуль генерации отчётов по сменам игроков.
"""
from .report_data import ReportData
from .report_generator import PlayerShiftMapReport

# Пока не импортируем UI, чтобы не тянуть PyQt лишний раз в тестах
# from .ui.report_generation_dialog import ReportGenerationDialog