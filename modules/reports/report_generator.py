# report_generator.py

import os
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, fields
from PIL import Image, ImageDraw, ImageFont
from modules.reports.report_data import ReportData, ShiftInfo, GoalInfo, PenaltyInfo, SegmentInfo

# ============================================
# ПОРЦИЯ 1: КОНСТАНТЫ И СТИЛИ
# ============================================

@dataclass(frozen=True)
class ReportStyles:
    """Все визуальные константы отчёта в одном месте."""
    
    # Шрифты (размеры в pt)
    HEADER_FONT_SIZE_PT = 14
    TABLE_HEADER_FONT_SIZE_PT = 8
    TABLE_DATA_FONT_SIZE_PT = 8
    FOOTER_FONT_SIZE_PT = 10
    GOALS_SCALE_FONT_SIZE_PT = 12
    TIME_SCALE_FONT_SIZE_PT = 14
    
    # Цвета (hex RGB)
    COLOR_WHITE = "#FFFFFF"
    COLOR_BLACK = "#000000"
    COLOR_HEADER_BG = "#EEEEEE"
    COLOR_GRID = "#C0C0C0"
    COLOR_GRID_LIGHT = "#E0E0E0"
    
    # Цвета событий
    COLOR_OUR_GOAL = "#0064C8"
    COLOR_THEIR_GOAL = "#C80032"
    COLOR_DIVIDER = "#A0A0A0"
    
    # Градиент смен
            # Цвета градиента
    COLOR_VERY_LIGHT_GREEN = (212, 247, 213)   # Почти белый зелёный 
    COLOR_DARK_GREEN = (18, 229, 29)             # Тёмно-зелёный
    COLOR_ORANGE = (231, 95, 36)               # Оранжевый
    COLOR_BRIGHT_RED = (79, 48, 15) 
    

    
    
    # Прозрачность
    GOAL_LINE_ALPHA = 128
    
    # Размеры
    DPI = 300
    FOOTER_HEIGHT_PX = 30
    HEADER_HEIGHT_RATIO = 1.4
    TABLE_GRID_LINE_WIDTH = 4
    
    # Отступы
    MARGIN_TOP = 100
    MARGIN_BOTTOM = 100
    MARGIN_LEFT = 100
    MARGIN_RIGHT = 50
    
    # Параметры шкал
    TIME_SCALE_HEIGHT_PX = 30
    GOALS_SCALE_HEIGHT_PX = 60
    GOALS_SCALE_TOP_HALF_PX = 15
    GOALS_SCALE_BOTTOM_HALF_PX = 15
    
    # Параметры таблицы (для совместимости со старым кодом)
    CONTENT_AREA_HEIGHT_PERCENT = 0.85
    CONTENT_AREA_TOP_MARGIN_PERCENT = 0.05
    TABLE_WIDTH_PERCENT_OF_CONTENT = 0.39
    TABLE_MAX_FONT_SIZE_PT = 12
    TABLE_MIN_FONT_SIZE_PT = 5
    TABLE_HEADER_DOUBLE_LINE_FONT_PT = 8
    TABLE_CELL_PADDING = 7
    TABLE_CELL_PADDING_NARROW = 2


# ============================================
# СТАРЫЕ КОНСТАНТЫ (для совместимости)
# ============================================

DPI = 300
A4_MM = (210, 297)
A3_MM = (297, 420)

def mm_to_px(mm_dim, dpi=DPI):
    mm_w, mm_h = mm_dim
    px_w = int((mm_w / 25.4) * dpi)
    px_h = int((mm_h / 25.4) * dpi)
    return px_w, px_h

A4_LANDSCAPE_PX = mm_to_px((A4_MM[1], A4_MM[0]))
A3_LANDSCAPE_PX = mm_to_px((A3_MM[1], A3_MM[0]))

SIZE_MAP = {
    'A4': A4_LANDSCAPE_PX,
    'A3': A3_LANDSCAPE_PX
}

# Старые константы (для совместимости со старыми методами)
MARGIN_TOP = 100
MARGIN_BOTTOM = 100
MARGIN_LEFT = 100
MARGIN_RIGHT = 50

COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_HEADER_BG = "#EEEEEE"
COLOR_GRID = "#000000"
COLOR_CELL_BG = "#FFFFFF"

TABLE_GRID_LINE_WIDTH = 4
TABLE_CELL_PADDING = 7
TABLE_CELL_PADDING_NARROW = 2
TABLE_HEADER_HEIGHT_RATIO = 1.4
TABLE_MAX_FONT_SIZE_PT = 12
TABLE_MIN_FONT_SIZE_PT = 5
TABLE_HEADER_DOUBLE_LINE_FONT_PT = 8
TABLE_WIDTH_PERCENT_OF_CONTENT = 0.39
CONTENT_AREA_HEIGHT_PERCENT = 0.85
CONTENT_AREA_TOP_MARGIN_PERCENT = 0.05

# Старые заголовки (для совместимости)
TABLE_HEADERS = ["№", "Ф.И.О.", "Смены 1/2/3", "Вр. 1/2/3", "Всего", "Г", "П", "+/-", "Ш"]

TABLE_PLACEHOLDERS = {
    "Смены 1/2/3": "X/Y/Z",
    "Вр. 1/2/3": "XX:XX/YY:YY/ZZ:ZZ",
    "Всего": "XX:YY",
    "Г": "X",
    "П": "X",
    "+/-": "+Z",
    "Ш": "YY"
}

TABLE_DEFAULT_ALIGNMENT = "center"
TABLE_DATA_NUMBER_ALIGNMENT = "right"
TABLE_DATA_NAME_ALIGNMENT = "left"

TABLE_COLUMN_ALIGNMENTS = {
    "№": TABLE_DATA_NUMBER_ALIGNMENT,
    "Ф.И.О.": TABLE_DATA_NAME_ALIGNMENT,
    "Смены 1/2/3": TABLE_DEFAULT_ALIGNMENT,
    "Вр. 1/2/3": TABLE_DEFAULT_ALIGNMENT,
    "Всего": TABLE_DEFAULT_ALIGNMENT,
    "Г": TABLE_DATA_NUMBER_ALIGNMENT,
    "П": TABLE_DATA_NUMBER_ALIGNMENT,
    "+/-": TABLE_DATA_NUMBER_ALIGNMENT,
    "Ш": TABLE_DATA_NUMBER_ALIGNMENT,
}

NARROW_COLUMNS = {"№", "Г", "П", "+/-", "Ш"}

TABLE_COLUMN_MAX_FONTS = {
    "Ф.И.О.": 11,
    "№": 10,
    "Смены 1/2/3": 9,
    "Вр. 1/2/3": 8,
    "Всего": 9,
    "Г": 10,
    "П": 10,
    "+/-": 10,
    "Ш": 10,
}


# ============================================
# НОВЫЕ НАБОРЫ КОЛОНОК
# ============================================

TABLE_HEADERS_MATCH = [
    "№", "Игрок", "Кол-во смен в матче", "Ср. время смены", "Время в матче", 
    "Больш.", "Меньш.", "Г", "П", "+/-", "Ш"
]

TABLE_HEADERS_PERIOD = [
    "№", "Игрок", "Смен в периоде", "Время в периоде", 
    "Больш.", "Меньш.", "Г", "П", "+/-", "Ш"
]

NEW_COLUMN_ALIGNMENTS = {
    "№": "right",
    "Игрок": "left",
    "Смены": "right",
    "Ср. вр. смены": "right",
    "Всего": "right",
    "Больш.": "right",
    "Меньш.": "right",
    "Г": "right",
    "П": "right",
    "+/-": "right",
    "Ш": "right",
    "Вр. в периоде": "right",
}


# ============================================
# КЛАСС ОТЧЁТА
# ============================================

class PlayerShiftMapReport:
    """
    Генератор отчёта "Карта смен игрока".
    Создаёт набор листов: Матч + Период 1 + Период 2 + Период 3 (+ ОТ)
    """
    
    def __init__(self, page_size: str = 'A4'):
        if page_size not in SIZE_MAP:
            raise ValueError(f"Неподдерживаемый размер страницы: {page_size}")
        
        self.page_size = page_size
        self.dpi = DPI
        self.width_px, self.height_px = SIZE_MAP[page_size]
        self.styles = ReportStyles()
        self.mode = 'game_on_sheet'
    
    # ============================================================
    # НОВЫЕ МЕТОДЫ (заглушки)
    # ============================================================
    
    def generate_all(self, report_data: ReportData) -> List[Image.Image]:
        """
        Генерирует полный набор листов отчёта с нумерацией.
        """
        images = []
        
        # Определяем общее количество листов
        num_periods = len(report_data.segments_info)
        total_pages = 1 + num_periods  # Матч + периоды
        
        # 1. Лист "Матч" (страница 1)
        print("Генерация листа 'Матч'...")
        match_sheet = self._generate_sheet_legacy(
            report_data, 
            mode='game_on_sheet',
            period_index=0,
            page_num=1,
            total_pages=total_pages
        )
        images.append(match_sheet)
        
        # 2-4(5). Листы периодов
        for i in range(num_periods):
            period_name = f"Период {i+1}" if i < 3 else "Овертайм"
            print(f"Генерация листа '{period_name}'...")
            period_sheet = self._generate_sheet_legacy(
                report_data,
                mode='period_on_sheet',
                period_index=i,
                page_num=i + 2,  # 2, 3, 4, 5...
                total_pages=total_pages
            )
            images.append(period_sheet)
        
        print(f"Всего сгенерировано листов: {len(images)}")
        return images
    
    # ============================================================
    # ПОРЦИЯ 2: ЗАГОЛОВОК И ПОДВАЛ (новые методы)
    # ============================================================
    
    def _draw_header(self, draw: ImageDraw, title: str, geom: dict):
        """
        Отрисовывает заголовок листа посередине сверху.
        :param draw: Объект ImageDraw
        :param title: Текст заголовка ("Карта смен — Матч" или "Карта смен — Период 1")
        :param geom: Геометрия content_area (для позиционирования)
        """
        styles = self.styles
        
        # Загружаем шрифт
        font_size_px = int(styles.HEADER_FONT_SIZE_PT * (self.dpi / 72))
        try:
            font = ImageFont.truetype("arial.ttf", font_size_px)
        except OSError:
            try:
                font = ImageFont.truetype("tahoma.ttf", font_size_px)
            except OSError:
                font = ImageFont.load_default()
        
        # Измеряем текст
        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # Позиция: по центру, над content_area
        content_x = geom["content_x"]
        content_y = geom["content_y"]
        content_width = geom["content_width"]
        
        x = content_x + (content_width - text_width) // 2
        y = 40  # Отступ от верхнего края листа (можно настроить)
        
        # Рисуем текст
        draw.text((x, y), title, fill=styles.COLOR_BLACK, font=font)
    
    def _draw_footer(self, draw: ImageDraw, page_num: int, total_pages: int, geom: dict):
        """
        Отрисовывает подвал с нумерацией и копирайтом.
        :param draw: Объект ImageDraw
        :param page_num: Номер текущей страницы (1-based)
        :param total_pages: Общее количество страниц
        :param geom: Геометрия content_area
        """
        styles = self.styles
        
        # Загружаем шрифт
        font_size_px = int(styles.FOOTER_FONT_SIZE_PT * (self.dpi / 72))
        try:
            font = ImageFont.truetype("arial.ttf", font_size_px)
        except OSError:
            try:
                font = ImageFont.truetype("tahoma.ttf", font_size_px)
            except OSError:
                font = ImageFont.load_default()
        
        content_x = geom["content_x"]
        content_width = geom["content_width"]
        footer_y = self.height_px - styles.FOOTER_HEIGHT_PX + 10  # Позиция текста в подвале
        
        # 1. Нумерация слева внизу: "1/5"
        page_text = f"{page_num}/{total_pages}"
        draw.text((content_x, footer_y), page_text, fill=styles.COLOR_BLACK, font=font)
        
        # 2. Копирайт по центру
        copyright_text = 'Отчет составлен программным комплексом "HockeyTagger v.4". Все права не защищены'
        text_bbox = draw.textbbox((0, 0), copyright_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x_center = content_x + (content_width - text_width) // 2
        draw.text((x_center, footer_y), copyright_text, fill=styles.COLOR_BLACK, font=font)
        
        # 3. Линия-разделитель над подвалом (опционально)
        line_y = self.height_px - styles.FOOTER_HEIGHT_PX
        draw.line(
            [(content_x, line_y), (content_x + content_width, line_y)],
            fill=styles.COLOR_GRID,
            width=1
        )
    
    
    def _generate_match_sheet(self, report_data: ReportData) -> Image.Image:
        """Генерирует лист типа 'Матч'."""
        return self._generate_sheet_legacy(report_data, mode='game_on_sheet')
    
    def _generate_period_sheet(self, report_data: ReportData, period_index: int) -> Image.Image:
        """Генерирует лист типа 'Период'."""
        return self._generate_sheet_legacy(report_data, mode='period_on_sheet', period_index=period_index)
    
    def _generate_sheet_legacy(self, report_data: ReportData, mode: str, 
                            period_index: int = 0, page_num: int = 1, 
                            total_pages: int = 1) -> Image.Image:
        """Временный метод для совместимости с новой архитектурой."""
        self.mode = mode
        
        # Определяем заголовок листа
        if mode == 'game_on_sheet':
            sheet_title = "Карта смен — Матч"
        else:
            period_name = f"Период {period_index + 1}" if period_index < 3 else "Овертайм"
            sheet_title = f"Карта смен — {period_name}"
        
        table_geom = self._calculate_table_geometry(report_data)
        graphic_geom = self._calculate_graphic_geometry(table_geom)
        
        img = Image.new('RGB', (self.width_px, self.height_px), color=COLOR_WHITE)
        draw = ImageDraw.Draw(img)
        
        # Рисуем заголовок листа
        self._draw_header(draw, sheet_title, table_geom)
        
        # Рисуем таблицу (НОВОЕ: выбираем тип таблицы)
        if mode == 'game_on_sheet':
            self._draw_match_table(draw, report_data, table_geom)
        else:
            self._draw_period_table(draw, report_data, table_geom, period_index)
        
        # Графическая часть (пока старая, будет заменена в Порции 4)
        # Вместо старого вызова:
        # self._draw_graphic_section(draw, report_data, graphic_geom, table_geom, period_index)

        # Новый вызов:
        # Внутри _generate_sheet_legacy, замените вызов графики на:
        if mode == 'game_on_sheet':
            self._draw_match_graphics(draw, report_data, graphic_geom, table_geom["header_height"])
        else:
            self._draw_period_graphics(draw, report_data, graphic_geom, period_index, table_geom["header_height"])
        
        # Рисуем подвал
        self._draw_footer(draw, page_num, total_pages, table_geom)
        
        return img
    
    # ============================================================
    # НОВЫЕ МЕТОДЫ ОТРИСОВКИ (заглушки)
    # ============================================================
    
    def _draw_match_table(self, draw: ImageDraw, report_data: ReportData, geom: dict):
        """
        Отрисовывает таблицу для листа 'Матч'.
        Колонки: №, Игрок, Смены, Ср. вр. смены, Всего, Больш., Меньш., Г, П, +/-, Ш
        """
        self._draw_generic_table(
            draw, report_data, geom, 
            headers=TABLE_HEADERS_MATCH,
            period_index=None  # None = все периоды
        )

    def _draw_period_table(self, draw: ImageDraw, report_data: ReportData, geom: dict, period_index: int):
        """
        Отрисовывает таблицу для листа 'Период'.
        Колонки: №, Игрок, Смены, Вр. в периоде, Больш., Меньш., Г, П, +/-, Ш
        """
        self._draw_generic_table(
            draw, report_data, geom,
            headers=TABLE_HEADERS_PERIOD,
            period_index=period_index
        )
    def _draw_generic_table(self, draw: ImageDraw, report_data: ReportData, geom: dict, 
                        headers: list, period_index: Optional[int]):
        """
        Универсальный метод отрисовки таблицы.
        """
        # Извлекаем параметры геометрии
        x_offset = geom["x"]
        y_offset = geom["y"]
        width = geom["width"]
        header_height = geom["header_height"]
        body_row_height = geom["body_row_height"]
        num_rows = geom["num_rows"]
        
        # Рассчитываем ширины колонок
        col_widths = self._calculate_column_widths(headers, width)
        
        # --- Заголовок ---
        current_x = x_offset
        header_y = y_offset
        
        for i, header in enumerate(headers):
            col_width = col_widths[i]
            
            # Фон заголовка
            draw.rectangle(
                [current_x, header_y, current_x + col_width, header_y + header_height],
                fill=self.styles.COLOR_HEADER_BG,
                outline=self.styles.COLOR_GRID,
                width=TABLE_GRID_LINE_WIDTH
            )
            
            # Текст заголовка
            self._draw_header_cell(draw, header, current_x, header_y, col_width, header_height)
            current_x += col_width
        
        # --- Строки данных ---
        for row_idx in range(num_rows):
            player = report_data.players_list[row_idx] if row_idx < len(report_data.players_list) else None
            row_y = y_offset + header_height + row_idx * body_row_height
            
            current_x = x_offset
            for col_idx, header in enumerate(headers):
                col_width = col_widths[col_idx]
                
                # Фон ячейки (белый)
                draw.rectangle(
                    [current_x, row_y, current_x + col_width, row_y + body_row_height],
                    fill=self.styles.COLOR_WHITE,
                    outline=self.styles.COLOR_GRID_LIGHT,
                    width=TABLE_GRID_LINE_WIDTH
                )
                
                # Текст ячейки
                if player:
                    text = self._get_cell_text(header, player, report_data, period_index)
                    align = NEW_COLUMN_ALIGNMENTS.get(header, "left")
                    self._draw_data_cell(draw, text, current_x, row_y, col_width, body_row_height, align)
                
                current_x += col_width

    def _calculate_column_widths(self, headers: list, total_width: int) -> list:
        """Распределяет ширину между колонками пропорционально."""
        # Пропорции: № (5%), Игрок (22%), остальные равномерно
        if len(headers) == 11:  # Матч
            ratios = [0.05, 0.22, 0.09, 0.11, 0.09, 0.09, 0.09, 0.06, 0.06, 0.06, 0.08]
        else:  # Период (10 колонок)
            ratios = [0.05, 0.25, 0.10, 0.12, 0.10, 0.10, 0.06, 0.06, 0.06, 0.10]
        
        widths = [int(total_width * r) for r in ratios]
        # Корректировка последней колонки чтобы сумма совпала с total_width
        widths[-1] = total_width - sum(widths[:-1])
        return widths  
     
    def _draw_header_cell(self, draw: ImageDraw, text: str, x: int, y: int, w: int, h: int):
        """Отрисовывает ячейку заголовка с многострочным текстом при необходимости."""
        font_size = self.styles.TABLE_HEADER_FONT_SIZE_PT
        font = self._get_font(font_size)
        
        # Если текст длинный (например, "Ср. вр. смены"), делаем перенос
        if len(text) > 8 and ' ' in text:
            # Двухстрочный заголовок как в старом коде
            parts = text.split(' ', 1)
            if len(parts) == 2:
                line1, line2 = parts
                bbox1 = draw.textbbox((0, 0), line1, font=font)
                bbox2 = draw.textbbox((0, 0), line2, font=font)
                h1 = bbox1[3] - bbox1[1]
                h2 = bbox2[3] - bbox2[1]
                total_h = h1 + h2 + 2
                
                y1 = y + (h - total_h) // 2
                y2 = y1 + h1 + 2
                
                x1 = x + (w - (bbox1[2]-bbox1[0])) // 2
                x2 = x + (w - (bbox2[2]-bbox2[0])) // 2
                
                draw.text((x1, y1), line1, fill=self.styles.COLOR_BLACK, font=font)
                draw.text((x2, y2), line2, fill=self.styles.COLOR_BLACK, font=font)
                return
        
        # Обычный однострочный заголовок
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x_pos = x + (w - text_w) // 2
        y_pos = y + (h - text_h) // 2
        draw.text((x_pos, y_pos), text, fill=self.styles.COLOR_BLACK, font=font)
        
    def _draw_data_cell(self, draw: ImageDraw, text: str, x: int, y: int, w: int, h: int, align: str):
        """Отрисовывает ячейку данных."""
        font_size = self.styles.TABLE_DATA_FONT_SIZE_PT
        font = self._get_font(font_size)
        
        bbox = draw.textbbox((0, 0), str(text), font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        padding = 3
        
        if align == "center":
            x_pos = x + (w - text_w) // 2
        elif align == "right":
            x_pos = x + w - text_w - padding
        else:  # left
            x_pos = x + padding
        
        y_pos = y + (h - text_h) // 2
        draw.text((x_pos, y_pos), str(text), fill=self.styles.COLOR_BLACK, font=font)

    def _get_cell_text(self, header: str, player, report_data: ReportData, period_index: Optional[int]) -> str:
        """Формирует текст для ячейки."""
        if header == "№":
            return player.number
        elif header == "Игрок":
            return player.full_name
        elif header == "Смены":
            # Количество смен (всего или за период)
            shifts = report_data.shifts_by_player_id.get(player.player_id, [])
            if period_index is not None:
                # Фильтруем смены по периоду
                seg = report_data.segments_info[period_index]
                count = sum(1 for s in shifts if seg.official_start <= s.official_start < seg.official_end)
            else:
                count = len(shifts)
            return str(count)
        elif header in ["Ср. вр. смены", "Всего", "Вр. в периоде", "Больш.", "Меньш.", "Г", "П", "+/-", "Ш"]:
            return "---"  # Заглушка для статистики
        else:
            return ""
        
    def _get_font(self, size_pt: int):
        """Вспомогательный метод для получения шрифта."""
        size_px = int(size_pt * (self.dpi / 72))
        try:
            return ImageFont.truetype("arial.ttf", size_px)
        except OSError:
            try:
                return ImageFont.truetype("tahoma.ttf", size_px)
            except OSError:
                return ImageFont.load_default()

    def _draw_match_graphics(self, draw: ImageDraw, report_data: ReportData, geom: dict, header_height: float):
        """
        Отрисовывает графику для листа 'Матч' (полная шкала 0-60/65 минут).
        """
        if not report_data.segments_info:
            return
        
        total_end = max(seg.official_end for seg in report_data.segments_info)
        time_range = total_end
        
        # Добавляем header_height в geom для передачи в _draw_top_time_scale
        geom_with_header = geom.copy()
        geom_with_header["header_height"] = header_height

        # Рисуем верхнюю шкалу времени (новая)
        self._draw_top_time_scale(draw, geom_with_header, time_range=time_range, is_match_level=True)
        
        # Рисуем смены (все)
        self._draw_shifts(draw, report_data, geom, time_range=time_range, period_start=0, header_height=header_height)
        
        # Рисуем нижнюю шкалу времени (существующая)
        self._draw_time_scale(draw, geom, time_range=time_range, is_match_level=True)
        
        # Рисуем шкалу голов (все голы) — возвращает Y для авторов
        authors_y = self._draw_goals_scale(draw, report_data, geom, time_range=time_range, period_start=0)
        
        # Рисуем авторов голов вертикально (снаружи geom)
        self._draw_goal_authors_vertical(draw, report_data, geom, time_range=time_range, period_start=0, authors_y=authors_y)

    def _draw_period_graphics(self, draw: ImageDraw, report_data: ReportData, geom: dict, period_index: int, header_height: float):
        """
        Отрисовывает графику для листа 'Период' (локальная шкала 0-20 минут).
        """
        if period_index >= len(report_data.segments_info):
            return
        
        segment = report_data.segments_info[period_index]
        period_start = segment.official_start
        period_end = segment.official_end
        time_range = period_end - period_start
        
        # Добавляем header_height в geom для передачи в _draw_top_time_scale
        geom_with_header = geom.copy()
        geom_with_header["header_height"] = header_height

        # Рисуем верхнюю шкалу времени (новая)
        self._draw_top_time_scale(draw, geom_with_header, time_range=time_range, is_match_level=False, period_abs_start=period_start)
        
        # Рисуем смены только этого периода
        self._draw_shifts(draw, report_data, geom, time_range=time_range, period_start=period_start, header_height=header_height)
        
        # Рисуем нижнюю шкалу времени периода
        self._draw_time_scale(draw, geom, time_range=time_range, is_match_level=False, period_abs_start=period_start)
        
        # Рисуем голы только этого периода
        authors_y = self._draw_goals_scale(draw, report_data, geom, time_range=time_range, period_start=period_start)
        
        # Рисуем авторов голов вертикально (снаружи geom)
        self._draw_goal_authors_vertical(draw, report_data, geom, time_range=time_range, period_start=period_start, authors_y=authors_y)
    
    def _draw_header(self, draw: ImageDraw, title: str, geom: dict):
        pass
    
    def _draw_footer(self, draw: ImageDraw, page_num: int, total_pages: int, geom: dict):
        pass
    
    # ============================================================
    # СУЩЕСТВУЮЩИЕ МЕТОДЫ (копируйте из текущего файла)
    # ============================================================
    
    def generate(self, report_data: ReportData):
        """УСТАРЕВШИЙ МЕТОД."""
        return self.generate_all(report_data)
    
    # Скопируйте сюда из текущего файла:
    # _calculate_table_geometry, _calculate_graphic_geometry,
    # _draw_table_section, _draw_graphic_section, _draw_shifts,
    # _draw_time_scale, _draw_goals_scale и все остальные методы
    def _calculate_graphic_geometry(self, table_geom: dict):
        """
        Вычисляет геометрию (x, y, width, height) для графической части отчёта.
        :param table_geom: Словарь с геометрическими параметрами таблицы.
        :return: Словарь с координатами и размерами графической области.
        """
        # Извлекаем параметры рабочей области и табличной части
        content_x = table_geom["content_x"]
        content_y = table_geom["content_y"]
        content_width = table_geom["content_width"]
        content_height = table_geom["content_height"]
        header_height = table_geom["header_height"]  # ← новое

        table_x = table_geom["x"]
        table_width = table_geom["width"]

        # --- Алгоритм ---
        graphic_x = table_x + table_width
        graphic_y = content_y
        graphic_width = (content_x + content_width) - graphic_x
        graphic_height = content_height
        # --- Конец алгоритма ---

        geometry = {
            "x": graphic_x,
            "y": graphic_y,                    # верх графической области
            "width": graphic_width,
            "height": graphic_height,
            "header_height": header_height,    # ← новое: высота заголовка таблицы
            "content_y": graphic_y + header_height,  # ← новое: низ заголовка = начало контента
        }

        print(f"DEBUG Graphic Geometry: {geometry}")
        return geometry
    # --- КОНЕЦ НОВОГО ---


    # --- НОВОЕ: Расчёт геометрии табличной части ---
    def _calculate_table_geometry(self, report_data: ReportData):
        """
        Вычисляет геометрию (x, y, width, height) для табличной части отчёта.
        :param report_ объект ReportData.
        :return: Словарь с координатами и размерами таблицы.
        """
        # --- НОВОЕ: Вычисление рабочей области ---
        # Вычисляем доступную высоту и ширину (между глобальными отступами)
        available_width = self.width_px - MARGIN_LEFT - MARGIN_RIGHT
        available_height = self.height_px - MARGIN_TOP - MARGIN_BOTTOM

        # Вычисляем высоту и вертикальное смещение рабочей области
        content_height = int(CONTENT_AREA_HEIGHT_PERCENT * available_height)
        content_top_margin = int(CONTENT_AREA_TOP_MARGIN_PERCENT * available_height)
        content_y = MARGIN_TOP + content_top_margin

        # Вычисляем ширину и горизонтальное смещение рабочей области
        content_width = available_width
        content_x = MARGIN_LEFT
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Вычисление размеров табличной области внутри рабочей ---
        table_width = int(content_width * TABLE_WIDTH_PERCENT_OF_CONTENT)
        table_x = content_x # Таблица начинается с левого края рабочей области

        # Высота таблицы теперь равна высоте рабочей области
        table_height = content_height
        table_y = content_y
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Фиксированное количество строк ---
        num_rows = 22
        # --- КОНЕЦ НОВОГО ---

        if num_rows == 0:
            print("Предупреждение: Количество строк для таблицы равно 0. Таблица не будет отрисована.")
            return {
                "x": table_x,
                "y": table_y,
                "width": table_width,
                "height": 0,
                "row_height": 0,
                "header_height": 0,
                "body_row_height": 0,
                "font_size_px": 0,
                "font_size_pt": 0,
                "column_widths": [],
                "content_x": content_x,
                "content_y": content_y,
                "content_width": content_width,
                "content_height": content_height
            }

        # --- НОВОЕ: Расчёт ширины колонок (улучшенный) ---
        # Загружаем шрифт для оценки размеров (используем max_font_size для оценки)
        # Попробуем использовать font_size в пикселях, но с максимальным размером для расчётов
        temp_font_size_px = TABLE_MAX_FONT_SIZE_PT * (self.dpi / 72) # Переводим pt в px
        if temp_font_size_px < 8: # Минимальный размер для корректного расчёта
             temp_font_size_px = 8
        try:
            temp_font = ImageFont.truetype("arial.ttf", int(temp_font_size_px))
        except OSError:
            try:
                temp_font = ImageFont.truetype("tahoma.ttf", int(temp_font_size_px))
            except OSError:
                temp_font = ImageFont.load_default()

        # Сначала определим минимальные ширины для всех колонок, кроме "Ф.И.О."
        min_widths = {}
        for header in TABLE_HEADERS:
            if header == "Ф.И.О.":
                continue # Пропускаем, будем считать его последним

            # Берём заполнитель для расчёта минимальной ширины
            placeholder = TABLE_PLACEHOLDERS.get(header, "X") # Если заполнителя нет, используем "X"
            # Используем самый короткий возможный текст для узких колонок
            if header in NARROW_COLUMNS:
                placeholder = "99" # Или "9", если ожидается одна цифра
            elif header == "Смены 1/2/3":
                placeholder = "X/Y/Z"
            elif header == "Вр. 1/2/3":
                placeholder = "XX:XX/YY:YY"
            elif header == "Всего":
                placeholder = "XX:YY"

            bbox = temp_font.getbbox(placeholder)
            text_width = bbox[2] - bbox[0]
             # --- ИСПРАВЛЕНИЕ: Отладка ширины заголовков ---
            bbox_debug = temp_font.getbbox(placeholder)
            print(f"DEBUG: Header '{header}' placeholder='{placeholder}' -> width={bbox_debug[2]-bbox_debug[0]} px")

            # --- ИСПРАВЛЕНО: Используем TABLE_CELL_PADDING_NARROW для узких колонок ---
            padding_to_use = TABLE_CELL_PADDING_NARROW if header in ["Смены 1/2/3", "Вр. 1/2/3"] else TABLE_CELL_PADDING
            min_widths[header] = max(text_width + 2 * padding_to_use, 10)
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Вычисляем сумму минимальных ширин для всех колонок, кроме "Ф.И.О."
        sum_min_widths_without_name = sum(min_widths.values())

        # Ширина для "Ф.И.О." = вся оставшаяся ширина
        available_width_for_name = table_width - sum_min_widths_without_name
        # Устанавливаем минимальную ширину для "Ф.И.О." как 100 пикселей (чтобы не было нулевой ширины)
        min_width_for_name = max(100, available_width_for_name)
        min_widths["Ф.И.О."] = min_width_for_name

        # Теперь у нас есть все минимальные ширины
        column_widths = []
        for header in TABLE_HEADERS:
            column_widths.append(min_widths[header])

        # --- КОНЕЦ НОВОГО ---

        # Нормализуем ширину, если сумма превышает доступную
        total_calculated_width = sum(column_widths)
        if total_calculated_width > table_width:
            scale_factor = table_width / total_calculated_width
            column_widths = [max(int(w * scale_factor), 10) for w in column_widths] # Минимум 10 px
            print(f"DEBUG: Ширина колонок масштабирована. Новая сумма: {sum(column_widths)} из {table_width}")

        # Если сумма меньше, можно распределить остаток, например, добавить его к "Ф.И.О."
        current_total_width = sum(column_widths)
        if current_total_width < table_width:
             extra_space = table_width - current_total_width
             # Добавляем весь остаток к колонке "Ф.И.О."
             name_index = TABLE_HEADERS.index("Ф.И.О.")
             column_widths[name_index] += extra_space
        # --- КОНЕЦ НОВОГО ---

        # --- НОВОЕ: Вычисление высоты строки ---

        # # Высота заголовка
        # calculated_header_height = int((table_height // (num_rows)) * TABLE_HEADER_HEIGHT_RATIO)
        # # Высота строки теперь определяется как высота рабочей области, делённая на количество строк
        # calculated_body_row_height = int((table_height - calculated_header_height) // num_rows)
        # # --- КОНЕЦ НОВОГО ---
                # Высота заголовка
        calculated_header_height = int((table_height // (num_rows + 1)) * TABLE_HEADER_HEIGHT_RATIO)
        # Высота строки теперь определяется как высота рабочей области, делённая на количество строк
        calculated_body_row_height = int((table_height - calculated_header_height) // num_rows)
        calculated_header_height = table_height - (calculated_body_row_height * num_rows)

        # --- КОНЕЦ НОВОГО ---

        geometry = {
            "x": table_x,
            "y": table_y,
            "width": table_width,
            "height": table_height,
            "row_height": calculated_body_row_height,
            "header_height": calculated_header_height,
            "body_row_height": calculated_body_row_height,
            # "font_size_px": final_font_size_px, # Больше не используется глобально
            # "font_size_pt": final_font_size_pt, # Больше не используется глобально
            "column_widths": column_widths,
            # Передаём параметры рабочей области
            "content_x": content_x,
            "content_y": content_y,
            "content_width": content_width,
            "content_height": content_height,
            # --- НОВОЕ: Передаём количество строк ---
            "num_rows": num_rows
            # --- КОНЕЦ НОВОГО ---
        }

        print(f"DEBUG Table Geometry: {geometry}")
        
        return geometry
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    # --- КОНЕЦ НОВОГО ---
    # --- НОВОЕ: Вспомогательный метод для динамического расчёта шрифта ---
    def _get_optimal_font_size_for_cell(self, text: str, available_width: int, available_height: int,
                                        max_size_pt: int = TABLE_MAX_FONT_SIZE_PT,
                                        min_size_pt: int = TABLE_MIN_FONT_SIZE_PT) -> int:
        """
        Находит оптимальный размер шрифта (в pt), чтобы текст поместился в ячейку.
        :param text: Текст для отображения.
        :param available_width: Доступная ширина ячейки (пиксели).
        :param available_height: Доступная высота ячейки (пиксели).
        :param max_size_pt: Максимальный размер шрифта (pt).
        :param min_size_pt: Минимальный размер шрифта (pt).
        :return: Оптимальный размер шрифта в pt.
        """
        # Учитываем внутренние отступы
        effective_width = available_width - 2 * TABLE_CELL_PADDING
        effective_height = available_height - 2 * TABLE_CELL_PADDING

        if effective_width <= 0 or effective_height <= 0:
            return min_size_pt

        # Сначала попробуем с максимальным размером
        for size_pt in range(max_size_pt, min_size_pt - 1, -1):
            try:
                font = ImageFont.truetype("arial.ttf", size_pt)
            except OSError:
                try:
                    font = ImageFont.truetype("tahoma.ttf", size_pt)
                except OSError:
                    font = ImageFont.load_default()

            # Получаем размеры текста
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Проверяем, помещается ли текст
            if text_width <= effective_width and text_height <= effective_height:
                return size_pt

        # Если ничего не подошло, возвращаем минимальный
        return min_size_pt
    # --- КОНЕЦ НОВОГО ---

    # --- НОВОЕ: Вспомогательный метод для отрисовки многострочного текста ---
    def _draw_multiline_text(self, draw: ImageDraw, text: str, xy: tuple, font, fill="black", line_spacing=1):
        """
        Рисует многострочный текст, разбивая его по символам '\n'.
        :param text: Строка с переносами '\n'.
        :param xy: Начальная позиция (x, y) для первой строки.
        :param font: Шрифт.
        :param fill: Цвет текста.
        :param line_spacing: Отступ между строками в пикселях.
        """
        lines = text.split('\n')
        x, y = xy
        for line in lines:
            # Получаем размеры текущей строки
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            # Рисуем строку
            draw.text((x, y), line, fill=fill, font=font)
            # Смещаем y для следующей строки
            y += line_height + line_spacing
    # --- КОНЕЦ НОВОГО ---

    # --- ОБНОВЛЕНО: Метод отрисовки табличной части ---
    def _draw_table_section(self, draw: ImageDraw, report_data: ReportData, table_geom: dict):
        """
        Отрисовывает левую табличную часть отчёта.
        :param draw: Объект ImageDraw.
        :param report_ Объект ReportData.
        :param table_geom: Словарь с геометрическими параметрами таблицы, включая ширину колонок, высоту строки и т.д.
        """
        # Извлекаем параметры из table_geom
        x_offset = table_geom["x"]
        y_offset = table_geom["y"]
        width = table_geom["width"]
        height = table_geom["height"]
        row_height = table_geom["row_height"]
        header_height = table_geom["header_height"]
        column_widths = table_geom["column_widths"] # Извлекаем список ширин колонок
        # --- НОВОЕ: Извлекаем количество строк ---
        num_rows_to_draw = table_geom["num_rows"]
        # --- КОНЕЦ НОВОГО ---

        if height == 0 or not column_widths: # Обновляем проверку
            print("Предупреждение: Высота таблицы 0 или ширина колонок не определена. Таблица не будет отрисована.")
            return

        # --- НОВОЕ: Загружаем шрифт для заголовков ---
        # Используем общий размер для заголовков, но можно также сделать динамический
        header_font_size_pt = min(TABLE_MAX_FONT_SIZE_PT, 10) # Например, 10pt для заголовков
        header_font_size_px = int(header_font_size_pt * (self.dpi / 72))
        try:
            header_font = ImageFont.truetype("arial.ttf", header_font_size_px)
        except OSError:
            try:
                header_font = ImageFont.truetype("tahoma.ttf", header_font_size_px)
            except OSError:
                header_font = ImageFont.load_default()
        # --- КОНЕЦ НОВОГО ---

        # --- Рисуем сетку, заголовки и данные ---
        current_y = y_offset
        # --- НОВОЕ: Отрисовка заголовков с поддержкой двух строк и специального шрифта ---
        header_y_pos = current_y
        current_x = x_offset
        for j, header_text in enumerate(TABLE_HEADERS):
            col_width = column_widths[j]
            alignment = TABLE_DEFAULT_ALIGNMENT

            # --- Специальная обработка для двухстрочных заголовков ---
            multiline_header = None
            if header_text == "Смены 1/2/3":
                multiline_header = ("Смены", "1 | 2 | 3")
                header_font_size_pt = TABLE_HEADER_DOUBLE_LINE_FONT_PT
            elif header_text == "Вр. 1/2/3":
                multiline_header = ("Время", "1 | 2 | 3")
                header_font_size_pt = TABLE_HEADER_DOUBLE_LINE_FONT_PT
            else:
                header_font_size_pt = header_font_size_pt # Используем общий размер
            # --- КОНЕЦ СПЕЦИАЛЬНОЙ ОБРАБОТКИ ---

            # Загружаем шрифт для этого заголовка
            header_font_size_px = int(header_font_size_pt * (self.dpi / 72))
            try:
                header_font = ImageFont.truetype("arial.ttf", header_font_size_px)
            except OSError:
                try:
                    header_font = ImageFont.truetype("tahoma.ttf", header_font_size_px)
                except OSError:
                    header_font = ImageFont.load_default()

            # Вычисляем смещение X для выравнивания
            text_to_measure = multiline_header[0] if multiline_header else header_text
            text_bbox = header_font.getbbox(text_to_measure)
            text_width = text_bbox[2] - text_bbox[0]

            align_x_offset = 0
            if alignment == "center":
                align_x_offset = (col_width - text_width) // 2
            elif alignment == "left":
                align_x_offset = TABLE_CELL_PADDING
            elif alignment == "right":
                align_x_offset = col_width - text_width - TABLE_CELL_PADDING

            header_x = current_x + align_x_offset
            # Центрируем по вертикали заголовка (для первой строки)
            text_height = text_bbox[3] - text_bbox[1]
            header_y = header_y_pos + (header_height - text_height) // 2

            # Фон для заголовка
            draw.rectangle([current_x, header_y_pos, current_x + col_width, header_y_pos + header_height], fill=COLOR_HEADER_BG)

            # --- ОТРИСОВКА ТЕКСТА ЗАГОЛОВКА ---
            if multiline_header:
                # Рисуем две строки с увеличенным отступом между ними
                line1, line2 = multiline_header
                # Вычисляем высоту каждой строки
                bbox1 = header_font.getbbox(line1)
                bbox2 = header_font.getbbox(line2)
                h1 = bbox1[3] - bbox1[1]
                h2 = bbox2[3] - bbox2[1]
                total_h = h1 + h2 + 6  # +3 для увеличенного отступа между строками

                # Центрируем обе строки по вертикали заголовка
                y1 = header_y_pos + (header_height - total_h) // 2
                y2 = y1 + h1 + 16

                # Центрируем каждую строку по ширине колонки
                bbox1_w = bbox1[2] - bbox1[0]
                bbox2_w = bbox2[2] - bbox2[0]
                x1 = current_x + (col_width - bbox1_w) // 2
                x2 = current_x + (col_width - bbox2_w) // 2

                draw.text((x1, y1), line1, fill=COLOR_BLACK, font=header_font, anchor="lt")
                draw.text((x2, y2), line2, fill=COLOR_BLACK, font=header_font, anchor="lt")
            else:
                draw.text((header_x, header_y), header_text, fill=COLOR_BLACK, font=header_font, anchor="lt")
            # --- КОНЕЦ ОТРИСОВКИ ТЕКСТА ЗАГОЛОВКА ---

            # Линия сетки справа от заголовка
            draw.line([(current_x + col_width, header_y_pos), (current_x + col_width, header_y_pos + header_height)], fill=COLOR_GRID, width=TABLE_GRID_LINE_WIDTH)

            current_x += col_width
        # --- КОНЕЦ НОВОГО ---
        # Линия сетки снизу заголовка
        draw.line([(x_offset, header_y_pos + header_height), (x_offset + width, header_y_pos + header_height)], fill=COLOR_GRID, width=TABLE_GRID_LINE_WIDTH)
        

        current_y += header_height # Переходим к телу таблицы

        # --- Рисуем строки данных ---
        # --- ИСПРАВЛЕНО: Цикл теперь по фиксированному числу строк (25) ---
        for i in range(num_rows_to_draw): # Цикл по фиксированному числу строк
            player = report_data.players_list[i] if i < len(report_data.players_list) else None # Получаем игрока или None
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            current_x = x_offset
            current_row_y = current_y + i * row_height

            # Рисуем линию сетки сверху строки (для первой строки это линия после заголовка, уже нарисована выше)
            if i > 0:
                draw.line([(x_offset, current_row_y), (x_offset + width, current_row_y)], fill=COLOR_GRID, width=TABLE_GRID_LINE_WIDTH)


            # Проходим по колонкам
            for j in range(len(TABLE_HEADERS)):
                col_width = column_widths[j] # Используем вычисленную ширину колонки
                cell_text = ""
                alignment = TABLE_COLUMN_ALIGNMENTS.get(TABLE_HEADERS[j], TABLE_DEFAULT_ALIGNMENT)

                # --- ИСПРАВЛЕНО: Обработка случая, когда игрока нет ---
                if player is None:
                    # Если игрока нет, ячейки оставляем пустыми
                    pass
                else:
                    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
                    if j == 0: # №
                        cell_text = player.number
                    elif j == 1: # Ф.И.О.
                        cell_text = player.full_name
                    else: # Остальные колонки - заполнители
                        placeholder_key = TABLE_HEADERS[j]
                        cell_text = TABLE_PLACEHOLDERS.get(placeholder_key, ".") # Если заполнитель не определён, используем "."

                # --- НОВОЕ: Рассчитываем оптимальный шрифт для каждой ячейки ---
                col_header = TABLE_HEADERS[j]
                max_font_for_cell = TABLE_COLUMN_MAX_FONTS.get(col_header, TABLE_MAX_FONT_SIZE_PT)

                optimal_font_size_pt = self._get_optimal_font_size_for_cell(
                    cell_text,
                    col_width,
                    row_height,
                    max_size_pt=max_font_for_cell,
                    min_size_pt=TABLE_MIN_FONT_SIZE_PT
                )
                optimal_font_size_px = int(optimal_font_size_pt * (self.dpi / 72))

                # Загружаем шрифт для этой ячейки
                try:
                    cell_font = ImageFont.truetype("arial.ttf", optimal_font_size_px)
                except OSError:
                    try:
                        cell_font = ImageFont.truetype("tahoma.ttf", optimal_font_size_px)
                    except OSError:
                        cell_font = ImageFont.load_default()
                # --- КОНЕЦ НОВОГО ---

                # Вычисляем bounding box для текста ячейки с *её* шрифтом
                text_bbox = cell_font.getbbox(cell_text)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # Вычисляем смещение для выравнивания
                align_x_offset = 0
                if alignment == "center":
                    align_x_offset = (col_width - text_width) // 2
                elif alignment == "left":
                    align_x_offset = TABLE_CELL_PADDING
                elif alignment == "right":
                    align_x_offset = col_width - text_width - TABLE_CELL_PADDING

                cell_x = current_x + align_x_offset
                # Центрируем по вертикали строки
                cell_y = current_row_y + (row_height - text_height) // 2

                # Рисуем текст
                draw.text((cell_x, cell_y), cell_text, fill=COLOR_BLACK, font=cell_font, anchor="lt")

                # Линия сетки справа от ячейки
                draw.line([(current_x + col_width, current_row_y), (current_x + col_width, current_row_y + row_height)], fill=COLOR_GRID, width=TABLE_GRID_LINE_WIDTH)
                print(f"777DEBUG: TABLE_GRID_LINE_WIDTH = {TABLE_GRID_LINE_WIDTH}")
                print(f"777DEBUG: id = {id(TABLE_GRID_LINE_WIDTH)}")

                current_x += col_width

            # Линия сетки снизу строки
            draw.line([(x_offset, current_row_y + row_height), (x_offset + width, current_row_y + row_height)], fill=COLOR_GRID, width=TABLE_GRID_LINE_WIDTH)
            print(f"888DEBUG: TABLE_GRID_LINE_WIDTH = {TABLE_GRID_LINE_WIDTH}")
            print(f"888DEBUG: id = {id(TABLE_GRID_LINE_WIDTH)}")

        # Рисуем внешнюю рамку таблицы (опционально, для наглядности)
        draw.rectangle([x_offset, y_offset, x_offset + width, y_offset + height], outline=COLOR_BLACK, width=5)
        print(f"999DEBUG: TABLE_GRID_LINE_WIDTH = {TABLE_GRID_LINE_WIDTH}")
        print(f"999DEBUG: id = {id(TABLE_GRID_LINE_WIDTH)}")


    # --- ОБНОВЛЕНО: Метод отрисовки графической части с передачей table_geom ---
    def _draw_graphic_section(self, draw: ImageDraw, report_data: ReportData, 
                              graphic_geom: dict, table_geom: dict, period_index: int = 0):
        """
        Отрисовывает правую графическую часть отчёта.
        """
        x = graphic_geom["x"]
        y = graphic_geom["y"]
        width = graphic_geom["width"]
        height = graphic_geom["height"]

        draw.rectangle([x, y, x + width, y + height], outline="blue", width=2)

        row_height = table_geom["body_row_height"]
        header_height = table_geom["header_height"]

        # Смены (с фильтрацией по периоду)
        self._draw_shifts(draw, report_data, graphic_geom, self.mode, 
                         row_height, header_height, period_index)

        # Шкала времени (с правильными подписями)
        self._draw_time_scale(draw, report_data, graphic_geom, self.mode, period_index)

        # Шкала голов (уже работает)
        self._draw_goals_scale(draw, report_data, graphic_geom, self.mode, period_index)

    def _draw_top_time_scale(self, draw: ImageDraw, geom: dict, time_range: float,
                            is_match_level: bool, period_abs_start: float = 0):
        """
        Верхняя шкала времени — располагается под заголовком таблицы.
        Нижняя линия шкалы совпадает с нижней линией строки-заголовка таблицы.
        """
        time_scale_x = geom["x"]
        time_scale_width = geom["width"]
        time_scale_height = self.styles.TIME_SCALE_HEIGHT_PX

        # Получаем высоту заголовка таблицы из geom
        header_height = geom["header_height"]

        # НИЖНЯЯ линия шкалы = нижняя линия заголовка таблицы
        scale_bottom_y = geom["y"] + header_height
        
        # ВЕРХНЯЯ линия шкалы = нижняя линия минус высота шкалы
        time_scale_y = scale_bottom_y - time_scale_height

        if time_range <= 0:
            return

        scale_factor = time_scale_width / time_range

        # Фон
        draw.rectangle([time_scale_x, time_scale_y,
                        time_scale_x + time_scale_width, scale_bottom_y],
                    outline="black", fill="white")

        # Шрифт
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = ImageFont.load_default()

        # Тики каждые 2 минуты для матча, 1 минута для периода
        tick_interval = 300 if is_match_level else 60

        for i, local_time in enumerate(range(0, int(time_range) + 1, tick_interval)):
            x_pos = time_scale_x + int(local_time * scale_factor)

            # Рисуем тик от верха до низа шкалы
            draw.line([(x_pos, time_scale_y), (x_pos, scale_bottom_y)],
                    fill="black", width=1)

            # Подпись
            if is_match_level:
                absolute_time = local_time
            else:
                absolute_time = period_abs_start + local_time

            minutes = int(absolute_time // 60)
            label_text = f"{minutes}'"

            text_bbox = draw.textbbox((0, 0), label_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Позиция X
            if i == 0:
                label_x = x_pos + 3
            else:
                if len(str(minutes)) == 1:
                    label_x = x_pos - 1 - text_width
                else:
                    label_x = x_pos - 3 - text_width

            # Центрируем по вертикали
            label_y = time_scale_y + (time_scale_height - text_height) // 2 - 2

            draw.text((label_x, label_y), label_text, fill="blue", font=font)

        # Линия-разделитель под шкалой (совпадает с низом заголовка таблицы)
        draw.line([(time_scale_x, scale_bottom_y), (time_scale_x + time_scale_width, scale_bottom_y)],
                fill=self.styles.COLOR_GRID, width=1)

    def _draw_time_scale(self, draw: ImageDraw, geom: dict, time_range: float, 
                        is_match_level: bool, period_abs_start: float = 0):
        """
        Шкала времени с учетом масштаба.
        :param is_match_level: True для матча (0-60), False для периода (локальное время)
        :param period_abs_start: Абсолютное начало периода (для подписей)
        """
        time_scale_x = geom["x"]
        time_scale_y = geom["y"] + geom["height"]
        time_scale_width = geom["width"]
        time_scale_height = self.styles.TIME_SCALE_HEIGHT_PX
        
        if time_range <= 0:
            return
        
        scale_factor = time_scale_width / time_range
        
        # Фон
        draw.rectangle([time_scale_x, time_scale_y, 
                    time_scale_x + time_scale_width, time_scale_y + time_scale_height], 
                    outline="black", fill="white")
        
        # Шрифт
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
        
        # Тики каждые 2 минуты (120 секунд)
        # Разный интервал тиков: 2 минуты для матча, 1 минута для периода
        tick_interval = 300 if is_match_level else 60  # 120 сек = 2 мин, 60 сек = 1 мин
        
        # Используем enumerate чтобы определить первую подпись (i == 0)
        for i, local_time in enumerate(range(0, int(time_range) + 1, tick_interval)):
            x_pos = time_scale_x + int(local_time * scale_factor)
            
            # Рисуем тик
            draw.line([(x_pos, time_scale_y), (x_pos, time_scale_y + time_scale_height)], 
                    fill="black", width=1)
            
            # Подпись
            if is_match_level:
                absolute_time = local_time
            else:
                absolute_time = period_abs_start + local_time
            
            minutes = int(absolute_time // 60)
            label_text = f"{minutes}'"
            
            # Измеряем текст
            text_bbox = draw.textbbox((0, 0), label_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # Определяем позицию X по новой логике
            if i == 0:  # Первая подпись (самая левая: 0, 20, 40 или 60)
                # Смещение вправо от тика на 7 пикселей
                label_x = x_pos + 3
            else:
                # Остальные подписи - слева от тика
                if len(str(minutes)) == 1:  # Однозначное число (0-9)
                    label_x = x_pos - 1 - text_width
                else:  # Двузначное число (10+)
                    label_x = x_pos - 3 - text_width
            
            # Центрируем по вертикали
            label_y = (time_scale_y + (time_scale_height - text_height) // 2) - 2
            
            draw.text((label_x, label_y), label_text, fill="blue", font=font)

    def _draw_shifts(self, draw: ImageDraw, report_data: ReportData, geom: dict, 
                 time_range: float, period_start: float, header_height: float):
        """
        Универсальный метод отрисовки смен с учетом временного диапазона.
        :param time_range: Длительность отображаемого периода (в секундах)
        :param period_start: Начало периода в абсолютном времени (для фильтрации)
        :param header_height: Высота заголовка таблицы для смещения линий
        """
        # Цвета градиента (из стилей)
        COLOR_VERY_LIGHT_GREEN = self.styles.COLOR_VERY_LIGHT_GREEN
        COLOR_DARK_GREEN = self.styles.COLOR_DARK_GREEN
        COLOR_ORANGE = self.styles.COLOR_ORANGE
        COLOR_BRIGHT_RED = self.styles.COLOR_BRIGHT_RED
        
        def interpolate_color(color1, color2, factor):
            r = int(color1[0] + (color2[0] - color1[0]) * factor)
            g = int(color1[1] + (color2[1] - color1[1]) * factor)
            b = int(color1[2] + (color2[2] - color1[2]) * factor)
            return (r, g, b)
        
        def get_gradient_color(duration, position_in_shift):
            if duration <= 35:
                return interpolate_color(COLOR_VERY_LIGHT_GREEN, COLOR_DARK_GREEN, position_in_shift)
            elif duration <= 70:
                threshold = 35 / duration
                if position_in_shift <= threshold:
                    local_pos = position_in_shift / threshold
                    return interpolate_color(COLOR_VERY_LIGHT_GREEN, COLOR_DARK_GREEN, local_pos)
                else:
                    local_pos = (position_in_shift - threshold) / (1 - threshold)
                    return interpolate_color(COLOR_DARK_GREEN, COLOR_ORANGE, local_pos)
            else:
                threshold1 = 35 / duration
                threshold2 = 70 / duration
                if position_in_shift <= threshold1:
                    local_pos = position_in_shift / threshold1
                    return interpolate_color(COLOR_VERY_LIGHT_GREEN, COLOR_DARK_GREEN, local_pos)
                elif position_in_shift <= threshold2:
                    local_pos = (position_in_shift - threshold1) / (threshold2 - threshold1)
                    return interpolate_color(COLOR_DARK_GREEN, COLOR_ORANGE, local_pos)
                else:
                    local_pos = (position_in_shift - threshold2) / (1 - threshold2)
                    return interpolate_color(COLOR_ORANGE, COLOR_BRIGHT_RED, local_pos)

        graphic_width = geom["width"]
        graphic_x = geom["x"]
        graphic_y = geom["content_y"]  # ← стало: начинаем от низа верхней шкалы
        # graphic_height больше не нужен для линий, но оставим для контроля границ
        #graphic_height = geom["height"]
        
        if time_range <= 0:
            return

        scale_factor = graphic_width / time_range
        
        # Рисуем горизонтальные линии строк (как в старом коде)
        # Рисуем горизонтальные линии строк (теперь с правильным смещением)
        row_height = self._calculate_table_geometry(report_data)["body_row_height"]
        num_rows = len(report_data.players_list) if report_data.players_list else 22
        
        for row_idx in range(num_rows + 1):
            line_y = graphic_y + row_idx * row_height
            # Проверяем, чтобы линия не вышла за пределы графической области
            if line_y <= geom["y"] + geom["height"]:
                draw.line(
                    [(graphic_x, line_y), (graphic_x + graphic_width, line_y)], 
                    fill=self.styles.COLOR_GRID_LIGHT,
                    width=1
                )
        


        # Рисуем смены игроков (также с учетом смещения)
        for player_index, player_info in enumerate(report_data.players_list):
            y_pos = graphic_y + player_index * row_height  # Теперь y_pos начинается с первой строки данных
            y_middle = y_pos + (row_height // 2)
            y_bottom = y_pos + row_height

            player_shifts = report_data.shifts_by_player_id.get(player_info.player_id, [])
            
            for shift_info in player_shifts:
                # Фильтруем смены по времени (для периода)
                if shift_info.official_end <= period_start or shift_info.official_start >= period_start + time_range:
                    continue
                
                # Преобразуем в локальные координаты
                local_start = max(shift_info.official_start - period_start, 0)
                local_end = min(shift_info.official_end - period_start, time_range)
                
                x_start = graphic_x + int(local_start * scale_factor)
                x_end = graphic_x + int(local_end * scale_factor)
                
                if x_end <= x_start:
                    x_end = x_start + 2
                
                shift_width = x_end - x_start
                duration = shift_info.duration

                # Верхняя часть с градиентом
                for dx in range(shift_width):
                    x = x_start + dx
                    position = dx / shift_width if shift_width > 0 else 0
                    color = get_gradient_color(duration, position)
                    draw.line([(x, y_pos), (x, y_middle)], fill=color)
                
                # Контур
                draw.line([(x_start, y_pos), (x_end, y_pos)], fill="black", width=1)
                draw.line([(x_start, y_pos), (x_start, y_middle)], fill="black", width=1)
                draw.line([(x_end, y_pos), (x_end, y_middle)], fill="black", width=1)

                # Нижняя часть (белая)
                draw.rectangle([x_start, y_middle, x_end, y_bottom], fill="white", outline="black", width=1)
                draw.line([(x_start, y_middle), (x_end, y_middle)], fill="black", width=1)

                # Подпись номера смены и длительности
                self._draw_shift_label(draw, x_start, x_end, y_pos, y_middle, y_bottom, row_height, shift_info, graphic_x, graphic_width)

    def _draw_shift_label(self, draw: ImageDraw, x_start: int, x_end: int, y_pos: int, 
                      y_middle: int, y_bottom: int, row_height: int, shift_info,
                      graphic_x: int, graphic_width: int):
        """Отрисовывает подпись смены (номер и длительность) - горизонтально или вертикально."""
        MIN_WIDTH_FOR_HORIZONTAL_TEXT = 50  # Увеличили с учетом шрифта 16
        TEXT_PADDING_X = 3
        
        shift_number_text = f"#{shift_info.number}"
        duration_text = f"{int(shift_info.duration)}\""
        
        try:
            label_font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            try:
                label_font = ImageFont.truetype("tahoma.ttf", 16)
            except OSError:
                label_font = ImageFont.load_default()

        number_bbox = draw.textbbox((0, 0), shift_number_text, font=label_font)
        duration_bbox = draw.textbbox((0, 0), duration_text, font=label_font)
        
        number_width = number_bbox[2] - number_bbox[0]
        duration_width = duration_bbox[2] - duration_bbox[0]
        text_height = number_bbox[3] - number_bbox[1]
        
        total_text_width = number_width + duration_width + (TEXT_PADDING_X * 3)
        shift_width = x_end - x_start
        lower_half_height = row_height // 2

        # Проверяем, помещается ли текст горизонтально
        if shift_width >= MIN_WIDTH_FOR_HORIZONTAL_TEXT and total_text_width <= shift_width:
            # Горизонтальный текст
            text_y = y_middle + (lower_half_height - text_height) // 2
            number_x = x_start + TEXT_PADDING_X
            draw.text((number_x, text_y), shift_number_text, fill="black", font=label_font)
            duration_x = x_end - duration_width - TEXT_PADDING_X
            draw.text((duration_x, text_y), duration_text, fill="black", font=label_font)
            
        else:
            # Вертикальный текст
            vertical_text = f"#{shift_info.number}    {int(shift_info.duration)}\""
            
            # Создаем временное изображение для текста
            margin = 2
            temp_img_size = (200, 100)  # Увеличили размер для шрифта 16
            temp_img = Image.new('RGBA', temp_img_size, (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((margin, margin), vertical_text, fill="black", font=label_font)
            
            # Находим границы текста
            text_bbox = temp_draw.textbbox((margin, margin), vertical_text, font=label_font)
            crop_box = (
                max(0, text_bbox[0] - 1),
                max(0, text_bbox[1] - 1),
                min(temp_img_size[0], text_bbox[2] + 1),
                min(temp_img_size[1], text_bbox[3] + 1)
            )
            text_only = temp_img.crop(crop_box)
            
            # Поворачиваем на 90 градусов
            rotated = text_only.rotate(90, expand=True, resample=Image.BICUBIC)
            
            # Определяем позицию: первая смена (слева от неё таблица) — подпись справа, остальные — слева
            # Считаем смену "первой" если она начинается в первых 5% времени периода
            # Но точнее — по позиции x_start относительно начала графической области
            is_first_shift = x_start < (graphic_x + graphic_width * 0.05)
            
            label_offset = 3
            
            if is_first_shift:
                # Первая смена — подпись справа
                label_x = x_end + label_offset
            else:
                # Остальные — подпись слева
                label_x = x_start - rotated.width - label_offset
            
            # Центрируем по вертикали строки
            label_y = y_pos + (row_height - rotated.height) // 2
            
            # Проверяем границы чтобы не выйти за пределы листа
            if label_x < 0:
                label_x = x_end + label_offset  # Если слева не помещается — ставим справа
            
            # Накладываем повернутый текст
            if rotated.mode == 'RGBA':
                # Создаем белый фон под текст
                background = Image.new('RGB', rotated.size, (255, 255, 255))
                background.paste(rotated, mask=rotated.split()[3])
                rotated = background
            
            # Рисуем на основном изображении
            draw._image.paste(rotated, (label_x, label_y))

    # --- НОВОЕ: Отрисовка шкалы голов ---
    def _draw_goals_scale(self, draw: ImageDraw, report_data: ReportData, geom: dict, 
                        time_range: float, period_start: float) -> int:
        """
        Шкала голов с новой структурой:
        - Верхняя половина: колышки
        - Нижняя половина: счёт после гола
        Возвращает Y-координату нижней границы шкалы (для отрисовки авторов снаружи).
        """
        # Цвета
        COLOR_OUR_GOAL = self.styles.COLOR_OUR_GOAL
        COLOR_THEIR_GOAL = self.styles.COLOR_THEIR_GOAL
        COLOR_DIVIDER = self.styles.COLOR_DIVIDER
        COLOR_TEXT = self.styles.COLOR_BLACK
        
        # Новая высота шкалы
        SCALE_HEIGHT = 60  # Увеличено с 30 до 60
        TOP_HALF_HEIGHT = 30  # Для колышков
        BOTTOM_HALF_HEIGHT = 30  # Для счёта
        
        # Позиция шкалы (под нижней временной шкалой)
        time_scale_height = self.styles.TIME_SCALE_HEIGHT_PX
        time_scale_y = geom["y"] + geom["height"]
        scale_y = time_scale_y + time_scale_height
        
        scale_x = geom["x"]
        scale_width = geom["width"]
        
        # Рисуем фон шкалы
        draw.rectangle([scale_x, scale_y, scale_x + scale_width, scale_y + SCALE_HEIGHT], 
                    fill="white", outline=COLOR_DIVIDER, width=1)
        
        # Разделительная линия посередине
        divider_y = scale_y + TOP_HALF_HEIGHT
        draw.line([(scale_x, divider_y), (scale_x + scale_width, divider_y)], 
                fill=COLOR_DIVIDER, width=1)
        
        if time_range <= 0:
            return scale_y + SCALE_HEIGHT
        
        scale_factor = scale_width / time_range
        
        # Шрифт для счёта
        try:
            score_font = ImageFont.truetype("arial.ttf", 14)
        except OSError:
            score_font = ImageFont.load_default()
        
        # Получаем данные о счёте из calculated_ranges
        score_ranges = self._get_score_ranges(report_data, period_start, time_range)
        
        # Фильтруем и рисуем голы
        for goal in report_data.goals:
            if not (period_start <= goal.official_time < period_start + time_range):
                continue
            
            # Определяем цвет (наш или соперник)
            team = goal.context.get('team', '')
            is_our_goal = (team == report_data.our_team_key)
            color = COLOR_OUR_GOAL if is_our_goal else COLOR_THEIR_GOAL
            
            # Позиция X
            local_time = goal.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)
            
            # === ВЕРХНЯЯ ПОЛОВИНА: колышек ===
            peg_top = scale_y + 3
            peg_bottom = divider_y - 2
            draw.line([(x_pos, peg_top), (x_pos, peg_bottom)], fill=color, width=2)
            # Основание колышка
            draw.line([(x_pos - 2, peg_bottom), (x_pos + 2, peg_bottom)], fill=color, width=2)
            
            # === НИЖНЯЯ ПОЛОВИНА: счёт после гола ===
            score_text = self._get_score_at_time(score_ranges, goal.official_time)
            if score_text:
                text_bbox = draw.textbbox((0, 0), score_text, font=score_font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                text_x = x_pos - text_width // 2
                text_y = divider_y + (BOTTOM_HALF_HEIGHT - text_height) // 2
                
                # Проверка границ
                if text_x < scale_x + 2:
                    text_x = scale_x + 2
                if text_x + text_width > scale_x + scale_width - 2:
                    text_x = scale_x + scale_width - text_width - 2
                
                draw.text((text_x, text_y), score_text, fill=COLOR_TEXT, font=score_font)
            
            # === ПУНКТИРНАЯ ЛИНИЯ ВВЕРХ ===
            # От колышка до низа верхней шкалы времени (начало контента)
            line_top = geom["content_y"]  # ← было: geom["y"]
            line_bottom = scale_y
            
            # Рисуем пунктирную линию (точками)
            dot_spacing = 8
            for y in range(int(line_top), int(line_bottom), dot_spacing):
                dot_y_end = min(y + 3, int(line_bottom))
                # Полупрозрачность через RGBA не работает напрямую в Draw, 
                # используем обычный цвет с меньшей интенсивностью или штриховку
                draw.line([(x_pos, y), (x_pos, dot_y_end)], fill=color, width=1)
        
        return scale_y + SCALE_HEIGHT

    def _get_score_ranges(self, report_data: ReportData, period_start: float, time_range: float) -> list:
        """
        Извлекает диапазоны счёта из calculated_ranges для отображения на шкале.
        """
        score_ranges = []
        
        # Ищем в оригинальном проекте calculated_ranges с label_type="Счёт"
        match_obj = report_data.original_project.match
        calculated_ranges = getattr(match_obj, 'calculated_ranges', [])
        
        for cr in calculated_ranges:
            if getattr(cr, 'label_type', '') == 'Счёт':
                # Конвертируем время в official_time
                from utils.helpers import convert_global_to_official_time
                try:
                    official_start = convert_global_to_official_time(cr.start_time, calculated_ranges)
                    official_end = convert_global_to_official_time(cr.end_time, calculated_ranges)
                    
                    if official_start is not None and official_end is not None:
                        score_ranges.append({
                            'name': cr.name,  # "2:1", "3:1" и т.д.
                            'start': official_start,
                            'end': official_end
                        })
                except:
                    continue
        
        return score_ranges

    def _get_score_at_time(self, score_ranges: list, goal_time: float) -> str:
        """
        Возвращает счёт после гола (берём диапазон, который начинается в момент гола).
        """
        for sr in score_ranges:
            # Счёт "после" гола — это диапазон, который начинается в момент гола
            # или ближайший следующий диапазон
            if sr['start'] <= goal_time < sr['end']:
                # Если гол в начале диапазона — это счёт после гола
                if abs(sr['start'] - goal_time) < 1.0:  # Допуск 1 секунда
                    return sr['name']
        
        # Если не нашли точное совпадение, ищем ближайший следующий диапазон
        for sr in score_ranges:
            if sr['start'] > goal_time:
                return sr['name']
        
        return ""

    def _draw_goal_authors_vertical(self, draw: ImageDraw, report_data: ReportData, geom: dict, 
                                    time_range: float, period_start: float, authors_y: int):
        """
        Отрисовывает авторов голов вертикально под шкалой (снаружи geom).
        С возможностью смещения при перекрытии.
        """
        COLOR_TEXT = self.styles.COLOR_BLACK
        
        if time_range <= 0:
            return
        
        scale_x = geom["x"]
        scale_width = geom["width"]
        scale_factor = scale_width / time_range
        
        # Шрифт для авторов
        try:
            author_font = ImageFont.truetype("arial.ttf", 10)
        except OSError:
            author_font = ImageFont.load_default()
        
        # Собираем голы с позициями
        goals_with_positions = []
        for goal in report_data.goals:
            if not (period_start <= goal.official_time < period_start + time_range):
                continue
            
            local_time = goal.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)
            
            # Формируем текст автора
            player_name = goal.context.get('player_name', 'Unknown')
            player_id_fhm = goal.context.get('player_id_fhm', '')
            
            # Ищем номер игрока
            player_number = ""
            for player in report_data.players_list:
                if player.player_id == player_id_fhm:
                    player_number = player.number
                    break
            
            # Формат: "77 Иванов И."
            author_text = f"{player_number} {player_name}" if player_number else player_name
            
            goals_with_positions.append({
                'goal': goal,
                'x': x_pos,
                'text': author_text
            })
        
        # Определяем смещения для перекрывающихся подписей
        MIN_SPACING = 20  # Минимальное расстояние между центрами подписей
        
        # Сортируем по X
        goals_with_positions.sort(key=lambda g: g['x'])
        
        # Определяем позиции: 0=центр, -1=слева, 1=справа
        positions = []  # (goal_data, offset_x)
        
        for i, gwp in enumerate(goals_with_positions):
            base_x = gwp['x']
            
            # Проверяем перекрытие с предыдущими
            offset = 0  # По умолчанию центр
            
            # Измеряем ширину текста
            text_bbox = draw.textbbox((0, 0), gwp['text'], font=author_font)
            text_width = text_bbox[2] - text_bbox[0]
            
            # Проверяем соседей слева
            conflict_left = False
            for prev_g, prev_offset, prev_x, prev_width in positions:
                prev_actual_x = prev_x + prev_offset
                if abs(base_x - prev_actual_x) < MIN_SPACING:
                    conflict_left = True
                    break
            
            if conflict_left:
                # Пробуем справа
                offset = text_width // 2 + 5
                # Проверяем не вылезем ли за правый край
                if base_x + offset + text_width > scale_x + scale_width:
                    # Пробуем слева
                    offset = -(text_width // 2 + 5)
                    # Проверяем не вылезем ли за левый край
                    if base_x + offset < scale_x:
                        offset = 0  # Возвращаем в центр, если никуда не влезает
            
            positions.append((gwp, offset, base_x, text_width))
        
        # Рисуем подписи
        for gwp, offset, base_x, text_width in positions:
            # Создаём временное изображение для вертикального текста
            text = gwp['text']
            
            # Размеры текста
            text_bbox = draw.textbbox((0, 0), text, font=author_font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            
            # Создаём временное изображение
            temp_img = Image.new('RGBA', (text_w + 4, text_h + 4), (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((2, 2), text, fill=COLOR_TEXT, font=author_font)
            
            # Поворачиваем на 90 градусов
            rotated = temp_img.rotate(90, expand=True, resample=Image.BICUBIC)
            
            # Позиция для вставки
            final_x = base_x + offset - rotated.width // 2
            final_y = authors_y + 5  # Небольшой отступ от шкалы
            
            # Проверка границ
            if final_x < scale_x:
                final_x = scale_x
            if final_x + rotated.width > scale_x + scale_width:
                final_x = scale_x + scale_width - rotated.width
            
            # Накладываем на основное изображение
            if rotated.mode == 'RGBA':
                draw._image.paste(rotated, (final_x, final_y), rotated)
            else:
                draw._image.paste(rotated, (final_x, final_y))