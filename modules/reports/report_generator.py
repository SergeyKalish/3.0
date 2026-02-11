# report_generator.py

import os
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, fields
from PIL import Image, ImageDraw, ImageFont
from modules.reports.report_data import ReportData, ShiftInfo, GoalInfo, PenaltyInfo, SegmentInfo


# ============================================
# КОНФИГУРАЦИЯ ТАБЛИЦ (не стили, структура данных)
# ============================================

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

TABLE_COLUMN_ALIGNMENTS = {
    "№": "right",
    "Ф.И.О.": "left",
    "Смены 1/2/3": "center",
    "Вр. 1/2/3": "center",
    "Всего": "center",
    "Г": "right",
    "П": "right",
    "+/-": "right",
    "Ш": "right",
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
    "Кол-во смен в матче": "right",
    "Ср. время смены": "right",
    "Время в матче": "right",
    "Больш.": "right",
    "Меньш.": "right",
    "Г": "right",
    "П": "right",
    "+/-": "right",
    "Ш": "right",
    "Смен в периоде": "right",
    "Время в периоде": "right",
}


# ============================================
# РАЗМЕРЫ ЛИСТОВ
# ============================================

DPI = 300
A4_MM = (210, 297)
A3_MM = (297, 420)


def mm_to_px(mm_dim: Tuple[int, int], dpi: int = DPI) -> Tuple[int, int]:
    """Конвертирует миллиметры в пиксели."""
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


# ============================================
# СТИЛИ ОТЧЁТА (все визуальные параметры)
# ============================================

@dataclass(frozen=True)
class ReportStyles:
    """Все визуальные константы отчёта в одном месте."""
    
    # --- Шрифты ---
    FONT_FAMILY_PRIMARY: str = "arial.ttf"           # Основной шрифт
    FONT_FAMILY_FALLBACK: str = "tahoma.ttf"         # Запасной шрифт
    FONT_FAMILY_HEADER: str = "arial.ttf"            # Шрифт для заголовков
    
    # --- Размеры шрифтов (pt) ---
    HEADER_FONT_SIZE_PT: int = 12                    # Заголовок листа ("Карта смен — Матч")
    TABLE_HEADER_FONT_SIZE_PT: int = 8               # Заголовки колонок таблицы
    TABLE_DATA_FONT_SIZE_PT: int = 8                 # Данные в ячейках таблицы
    FOOTER_FONT_SIZE_PT: int = 5                    # Нумерация страниц, копирайт
    GOALS_SCALE_FONT_SIZE_PT: int = 6               # Счёт на шкале голов
    TIME_SCALE_FONT_SIZE_PT: int = 6                # Подписи времени на шкалах
    SHIFT_LABEL_FONT_SIZE_PT: int = 4               # Номер и длительность смены
    GOAL_AUTHOR_FONT_SIZE_PT: int = 5               # Авторы голов (вертикально)
    
    # --- Цвета (hex RGB) ---
    COLOR_WHITE: str = "#FFFFFF"
    COLOR_BLACK: str = "#000000"
    COLOR_HEADER_BG: str = "#EEEEEE"                 # Фон заголовка таблицы
    COLOR_GRID: str = "#C0C0C0"                      # Линии сетки таблицы
    COLOR_GRID_LIGHT: str = "#E0E0E0"                # Линии сетки смен
    
    # Цвета голов
    COLOR_OUR_GOAL: str = "#0064C8"                  # Наши голы
    COLOR_THEIR_GOAL: str = "#C80032"                # Голы соперника
    COLOR_DIVIDER: str = "#A0A0A0"                   # Разделители
    
    # Цвета градиента смен (RGB tuples)
    COLOR_VERY_LIGHT_GREEN: Tuple[int, int, int] = (212, 247, 213)  # До 35 сек
    COLOR_DARK_GREEN: Tuple[int, int, int] = (18, 229, 29)          # 35-70 сек
    COLOR_ORANGE: Tuple[int, int, int] = (231, 95, 36)              # 70+ сек, фаза 1
    COLOR_BRIGHT_RED: Tuple[int, int, int] = (79, 48, 15)           # 70+ сек, фаза 2
    
    # --- Геометрия и отступы (px) ---
    DPI: int = 300
    
    # Поля листа
    MARGIN_TOP: int = 100
    MARGIN_BOTTOM: int = 100
    MARGIN_LEFT: int = 100
    MARGIN_RIGHT: int = 50
    
    # Рабочая область
    CONTENT_AREA_HEIGHT_PERCENT: float = 0.85
    CONTENT_AREA_TOP_MARGIN_PERCENT: float = 0.05
    TABLE_WIDTH_PERCENT_OF_CONTENT: float = 0.39
    
    # Таблица
    TABLE_GRID_LINE_WIDTH: int = 3                   # Толщина линий сетки таблицы
    TABLE_OUTLINE_WIDTH: int = 1                     # Внешняя рамка таблицы
    TABLE_MAX_FONT_SIZE_PT: int = 12                 # Макс. размер шрифта в ячейке
    TABLE_MIN_FONT_SIZE_PT: int = 5                  # Мин. размер шрифта в ячейке
    TABLE_HEADER_DOUBLE_LINE_FONT_PT: int = 8        # Для двухстрочных заголовков
    TABLE_CELL_PADDING: int = 7                      # Отступ текста от края ячейки
    TABLE_CELL_PADDING_NARROW: int = 2               # Узкий отступ для коротких колонок
    # Графическая область
    GRAPHIC_AREA_BORDER_WIDTH: int = 2             # Толщина рамки (2px — заметнее)
    GRAPHIC_AREA_BORDER_COLOR: str = "#B31919"     # Цвет рамки (темно-серый, отличимый от сетки)
    
    # Шкалы
    TIME_SCALE_HEIGHT_PX: int = 30                   # Высота верхней/нижней шкалы времени
    TIME_SCALE_TICK_WIDTH: int = 1                   # Тики на шкалах времени
    TIME_SCALE_OUTLINE_WIDTH: int = 2                # Рамка шкалы времени
    
    GOALS_SCALE_HEIGHT_PX: int = 60                  # Высота шкалы голов
    GOALS_SCALE_TOP_HALF_PX: int = 30                # Верхняя половина (колышки)
    GOALS_SCALE_BOTTOM_HALF_PX: int = 30             # Нижняя половина (счёт)
    GOAL_PEG_WIDTH: int = 3                          # Колышек гола
    GOAL_PEG_BASE_WIDTH: int = 2                     # Основание колышка
    GOAL_DASHED_LINE_WIDTH: int = 2                  # Пунктирная линия вверх от гола
    GOALS_SCALE_OUTLINE_WIDTH: int = 2               # Рамка шкалы голов
    GOALS_SCALE_DIVIDER_WIDTH: int = 1               # Разделитель посередине шкалы голов
    
    # Смены
    SHIFT_GRID_LINE_WIDTH: int = 1                   # Горизонтальные линии строк смен
    SHIFT_BORDER_WIDTH: int = 1                      # Контур смены (верх, лево, право)
    SHIFT_DIVIDER_WIDTH: int = 1                     # Разделитель в смене (середина)
    
    # Подвал
    FOOTER_HEIGHT_PX: int = 30                       # Высота подвала с нумерацией
    FOOTER_DIVIDER_WIDTH: int = 1                    # Линия-разделитель над подвалом
    
    # Прочее
    GOAL_LINE_ALPHA: int = 128                       # Прозрачность линий голов
    HEADER_HEIGHT_RATIO: float = 1.4                 # Коэффициент высоты заголовка таблицы

    # Новые константы для шкалы game_mode
    GAME_MODE_SCALE_HEIGHT_PX = 30
    GAME_MODE_FONT_SIZE_PT = 5
    GAME_MODE_BG_COLOR = "#F5F5F5"
    GAME_MODE_TEXT_COLOR = "#000000"
    GAME_MODE_GRID_COLOR = "#C0C0C0"
    GAME_MODE_LINE_WIDTH = 1
    GAME_MODE_MIN_WIDTH_FOR_HORIZONTAL = 60  # минимальная ширина для горизонтального текста


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
        
        # Проверка консистентности
        assert self.styles.TABLE_GRID_LINE_WIDTH > 0, "Толщина линий должна быть > 0"

    def _get_font(self, size_pt: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """
        Возвращает шрифт с fallback.
        
        Args:
            size_pt: Размер шрифта в пунктах
            bold: Не используется (зарезервировано для будущего)
            
        Returns:
            Объект шрифта PIL
        """
        size_px = int(size_pt * (self.styles.DPI / 72))
        families = [self.styles.FONT_FAMILY_PRIMARY, self.styles.FONT_FAMILY_FALLBACK]
        
        for family in families:
            try:
                return ImageFont.truetype(family, size_px)
            except OSError:
                continue
        
        return ImageFont.load_default()

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
        match_sheet = self._generate_sheet(
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
            period_sheet = self._generate_sheet(
                report_data,
                mode='period_on_sheet',
                period_index=i,
                page_num=i + 2,  # 2, 3, 4, 5...
                total_pages=total_pages
            )
            images.append(period_sheet)

        print(f"Всего сгенерировано листов: {len(images)}")
        return images

    def _generate_sheet(self, report_data: ReportData, mode: str,
                        period_index: int = 0, page_num: int = 1,
                        total_pages: int = 1) -> Image.Image:
        """Генерирует один лист отчёта."""
        self.mode = mode

        # Определяем заголовок листа
        if mode == 'game_on_sheet':
            sheet_title = "Карта смен — Матч"
        else:
            period_name = f"Период {period_index + 1}" if period_index < 3 else "Овертайм"
            sheet_title = f"Карта смен — {period_name}"

        table_geom = self._calculate_table_geometry(report_data)
        graphic_geom = self._calculate_graphic_geometry(table_geom)

        img = Image.new('RGB', (self.width_px, self.height_px), 
                        color=self.styles.COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        # Рисуем заголовок листа
        self._draw_sheet_header(draw, sheet_title, table_geom)

        # Рисуем таблицу
        if mode == 'game_on_sheet':
            self._draw_match_table(draw, report_data, table_geom)
        else:
            self._draw_period_table(draw, report_data, table_geom, period_index)

        # Рисуем графическую часть
        if mode == 'game_on_sheet':
            self._draw_graphics_match(draw, report_data, graphic_geom, 
                                    table_geom["header_height"])
        else:
            self._draw_graphics_period(draw, report_data, graphic_geom, 
                                    period_index, table_geom["header_height"])

        # === НОВОЕ: Рамка вокруг графической области ===
        self._draw_graphic_area_border(draw, graphic_geom)

        # Рисуем подвал
        self._draw_sheet_footer(draw, page_num, total_pages, table_geom)

        return img

    def _draw_graphic_area_border(self, draw: ImageDraw, geom: dict):
        """
        Рисует рамку вокруг графической области.
        """
        styles = self.styles
        
        draw.rectangle(
            [geom["x"], geom["y"], geom["x"] + geom["width"], geom["y"] + geom["height"]],
            outline=styles.GRAPHIC_AREA_BORDER_COLOR,
            width=styles.GRAPHIC_AREA_BORDER_WIDTH
        )


    def _draw_sheet_header(self, draw: ImageDraw, title: str, geom: dict):
        """
        Отрисовывает заголовок листа посередине сверху.
        """
        styles = self.styles

        # Загружаем шрифт
        font = self._get_font(styles.HEADER_FONT_SIZE_PT)

        # Измеряем текст
        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Позиция: по центру, над content_area
        content_x = geom["content_x"]
        content_width = geom["content_width"]

        x = content_x + (content_width - text_width) // 2
        y = 40  # Отступ от верхнего края листа

        # Рисуем текст
        draw.text((x, y), title, fill=styles.COLOR_BLACK, font=font)

    def _draw_sheet_footer(self, draw: ImageDraw, page_num: int, total_pages: int, geom: dict):
        """
        Отрисовывает подвал с нумерацией и копирайтом.
        Размещается внизу листа с отступом от края.
        """
        styles = self.styles

        # Загружаем шрифт
        font = self._get_font(styles.FOOTER_FONT_SIZE_PT)

        content_x = geom["content_x"]
        content_width = geom["content_width"]
        
        # === ИСПРАВЛЕНО: Подвал прижат к низу листа с минимальным отступом ===
        # Отступ от нижнего края листа (небольшой зазор)
        BOTTOM_PADDING = 20  # px от края листа
        
        # Низ текста = низ листа - отступ
        text_bottom = self.height_px - BOTTOM_PADDING
        
        # Измеряем высоту текста
        sample_bbox = draw.textbbox((0, 0), "1/5", font=font)
        text_height = sample_bbox[3] - sample_bbox[1]
        
        # Y для текста (базовая линия)
        footer_y = text_bottom - text_height
        
        # Линия-разделитель чуть выше текста
        line_y = footer_y - 5  # 5px зазор между линией и текстом

        # 1. Нумерация слева: "1/5"
        page_text = f"{page_num}/{total_pages}"
        draw.text((content_x, footer_y), page_text, fill=styles.COLOR_BLACK, font=font)

        # 2. Копирайт по центру
        copyright_text = 'Отчет составлен программным комплексом "HockeyTagger v.4". Все права не защищены'
        text_bbox = draw.textbbox((0, 0), copyright_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x_center = content_x + (content_width - text_width) // 2 * 2
        draw.text((x_center, footer_y), copyright_text, fill=styles.COLOR_BLACK, font=font)

        # 3. Линия-разделитель над подвалом
        draw.line(
            [(content_x, line_y), (content_x + content_width, line_y)],
            fill=styles.COLOR_GRID,
            width=styles.FOOTER_DIVIDER_WIDTH
        )
        
    def _calculate_table_geometry(self, report_data: ReportData) -> dict:
        """
        Вычисляет геометрию для табличной части отчёта.
        """
        styles = self.styles
        
        # Вычисляем доступную высоту и ширину
        available_width = self.width_px - styles.MARGIN_LEFT - styles.MARGIN_RIGHT
        available_height = self.height_px - styles.MARGIN_TOP - styles.MARGIN_BOTTOM

        # Вычисляем высоту и вертикальное смещение рабочей области
        content_height = int(styles.CONTENT_AREA_HEIGHT_PERCENT * available_height)
        content_top_margin = int(styles.CONTENT_AREA_TOP_MARGIN_PERCENT * available_height)
        content_y = styles.MARGIN_TOP + content_top_margin

        # Вычисляем ширину и горизонтальное смещение рабочей области
        content_width = available_width
        content_x = styles.MARGIN_LEFT

        # Вычисление размеров табличной области
        table_width = int(content_width * styles.TABLE_WIDTH_PERCENT_OF_CONTENT)
        table_x = content_x
        table_height = content_height
        table_y = content_y

        # Фиксированное количество строк
        num_rows = 22

        if num_rows == 0:
            print("Предупреждение: Количество строк для таблицы равно 0.")
            return {
                "x": table_x,
                "y": table_y,
                "width": table_width,
                "height": 0,
                "row_height": 0,
                "header_height": 0,
                "body_row_height": 0,
                "column_widths": [],
                "content_x": content_x,
                "content_y": content_y,
                "content_width": content_width,
                "content_height": content_height,
                "num_rows": 0
            }

        # Расчёт ширины колонок
        temp_font = self._get_font(styles.TABLE_MAX_FONT_SIZE_PT)
        
        min_widths = {}
        for header in TABLE_HEADERS:
            if header == "Ф.И.О.":
                continue

            placeholder = TABLE_PLACEHOLDERS.get(header, "X")
            if header in NARROW_COLUMNS:
                placeholder = "99"
            elif header == "Смены 1/2/3":
                placeholder = "X/Y/Z"
            elif header == "Вр. 1/2/3":
                placeholder = "XX:XX/YY:YY"
            elif header == "Всего":
                placeholder = "XX:YY"

            bbox = temp_font.getbbox(placeholder)
            text_width = bbox[2] - bbox[0]
            
            padding_to_use = (styles.TABLE_CELL_PADDING_NARROW 
                            if header in ["Смены 1/2/3", "Вр. 1/2/3"] 
                            else styles.TABLE_CELL_PADDING)
            min_widths[header] = max(text_width + 2 * padding_to_use, 10)

        sum_min_widths_without_name = sum(min_widths.values())
        available_width_for_name = table_width - sum_min_widths_without_name
        min_width_for_name = max(100, available_width_for_name)
        min_widths["Ф.И.О."] = min_width_for_name

        column_widths = [min_widths[header] for header in TABLE_HEADERS]

        # Нормализуем ширину
        total_calculated_width = sum(column_widths)
        if total_calculated_width > table_width:
            scale_factor = table_width / total_calculated_width
            column_widths = [max(int(w * scale_factor), 10) for w in column_widths]

        current_total_width = sum(column_widths)
        if current_total_width < table_width:
            extra_space = table_width - current_total_width
            name_index = TABLE_HEADERS.index("Ф.И.О.")
            column_widths[name_index] += extra_space

        # === РАСЧЁТ ВЫСОТЫ С УЧЁТОМ КРАТНОСТИ ===
        # Сначала считаем базовую высоту строки данных
        # table_height = header_height + num_rows * body_row_height
        # header_height = body_row_height * HEADER_HEIGHT_RATIO
        # table_height = body_row_height * (HEADER_HEIGHT_RATIO + num_rows)
        
        base_height = table_height / (styles.HEADER_HEIGHT_RATIO + num_rows)
        calculated_body_row_height = int(base_height)
        
        # Вычисляем остаток от деления и добавляем к заголовку
        total_body_height = calculated_body_row_height * num_rows
        remaining_space = table_height - total_body_height
        
        # Весь остаток идёт в заголовок (с учётом коэффициента)
        calculated_header_height = remaining_space
        
        # Минимальные проверки
        calculated_header_height = max(calculated_header_height, int(calculated_body_row_height * styles.HEADER_HEIGHT_RATIO))
        calculated_header_height = max(calculated_header_height, 30)  # Абсолютный минимум 30px
        calculated_body_row_height = max(calculated_body_row_height, 15)  # Абсолютный минимум 15px

        geometry = {
            "x": table_x,
            "y": table_y,
            "width": table_width,
            "height": table_height,
            "row_height": calculated_body_row_height,
            "header_height": calculated_header_height,
            "body_row_height": calculated_body_row_height,
            "column_widths": column_widths,
            "content_x": content_x,
            "content_y": content_y,
            "content_width": content_width,
            "content_height": content_height,
            "num_rows": num_rows
        }

        print(f"DEBUG Table Geometry: {geometry}")
        return geometry


    def _calculate_graphic_geometry(self, table_geom: dict) -> dict:
        """
        Вычисляет геометрию для графической части отчёта.
        
        Args:
            table_geom: Словарь с геометрическими параметрами таблицы
            
        Returns:
            Словарь с координатами и размерами графической области.
            Включает header_height и content_y для позиционирования элементов
            относительно низа заголовка таблицы.
        """
        content_x = table_geom["content_x"]
        content_y = table_geom["content_y"]
        content_width = table_geom["content_width"]
        content_height = table_geom["content_height"]

        table_x = table_geom["x"]
        table_width = table_geom["width"]
        header_height = table_geom["header_height"]

        graphic_x = table_x + table_width
        graphic_y = content_y
        graphic_width = (content_x + content_width) - graphic_x
        graphic_height = content_height

        geometry = {
            "x": graphic_x,
            "y": graphic_y,                    # верх графической области (совпадает с таблицей)
            "width": graphic_width,
            "height": graphic_height,
            "header_height": header_height,    # высота заголовка таблицы
            "content_y": graphic_y + header_height,  # низ заголовка = начало контента графики
        }

        print(f"DEBUG Graphic Geometry: {geometry}")
        return geometry


    def _draw_match_table(self, draw: ImageDraw, report_data: ReportData, geom: dict):
        """
        Отрисовывает таблицу для листа 'Матч'.
        """
        self._draw_generic_table(
            draw, report_data, geom,
            headers=TABLE_HEADERS_MATCH,
            period_index=None
        )

    def _draw_period_table(self, draw: ImageDraw, report_data: ReportData, 
                           geom: dict, period_index: int):
        """
        Отрисовывает таблицу для листа 'Период'.
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
        styles = self.styles
        
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
                fill=styles.COLOR_HEADER_BG,
                outline=styles.COLOR_GRID,
                width=styles.TABLE_GRID_LINE_WIDTH
            )

            # Текст заголовка
            self._draw_header_cell(draw, header, current_x, header_y, col_width, header_height)
            current_x += col_width

        # --- Строки данных ---
        for row_idx in range(num_rows):
            player = (report_data.players_list[row_idx] 
                      if row_idx < len(report_data.players_list) else None)
            row_y = y_offset + header_height + row_idx * body_row_height

            current_x = x_offset
            for col_idx, header in enumerate(headers):
                col_width = col_widths[col_idx]

                # Фон ячейки
                draw.rectangle(
                    [current_x, row_y, current_x + col_width, row_y + body_row_height],
                    fill=styles.COLOR_WHITE,
                    outline=styles.COLOR_GRID_LIGHT,
                    width=styles.TABLE_GRID_LINE_WIDTH
                )

                # Текст ячейки
                if player:
                    text = self._get_cell_text(header, player, report_data, period_index)
                    align = NEW_COLUMN_ALIGNMENTS.get(header, "left")
                    self._draw_data_cell(draw, text, current_x, row_y, col_width, 
                                         body_row_height, align)

                current_x += col_width

        # Внешняя рамка таблицы
        draw.rectangle([x_offset, y_offset, x_offset + width, y_offset + geom["height"]],
                       outline=styles.COLOR_BLACK, width=styles.TABLE_OUTLINE_WIDTH)

    def _calculate_column_widths(self, headers: list, total_width: int) -> list:
        """Распределяет ширину между колонками пропорционально."""
        if len(headers) == 11:  # Матч
            ratios = [0.05, 0.22, 0.09, 0.11, 0.09, 0.09, 0.09, 0.06, 0.06, 0.06, 0.08]
        else:  # Период (10 колонок)
            ratios = [0.05, 0.25, 0.10, 0.12, 0.10, 0.10, 0.06, 0.06, 0.06, 0.10]

        widths = [int(total_width * r) for r in ratios]
        widths[-1] = total_width - sum(widths[:-1])
        return widths

    def _draw_header_cell(self, draw: ImageDraw, text: str, x: int, y: int, w: int, h: int):
        """Отрисовывает ячейку заголовка с многострочным текстом при необходимости."""
        styles = self.styles
        font_size = styles.TABLE_HEADER_FONT_SIZE_PT
        font = self._get_font(font_size)

        # Двухстрочный заголовок
        if len(text) > 8 and ' ' in text:
            parts = text.split(' ', 1)
            if len(parts) == 2:
                line1, line2 = parts
                font = self._get_font(styles.TABLE_HEADER_DOUBLE_LINE_FONT_PT)
                
                bbox1 = draw.textbbox((0, 0), line1, font=font)
                bbox2 = draw.textbbox((0, 0), line2, font=font)
                h1 = bbox1[3] - bbox1[1]
                h2 = bbox2[3] - bbox2[1]
                total_h = h1 + h2 + 2

                y1 = y + (h - total_h) // 2
                y2 = y1 + h1 + 2

                x1 = x + (w - (bbox1[2]-bbox1[0])) // 2
                x2 = x + (w - (bbox2[2]-bbox2[0])) // 2

                draw.text((x1, y1), line1, fill=styles.COLOR_BLACK, font=font)
                draw.text((x2, y2), line2, fill=styles.COLOR_BLACK, font=font)
                return

        # Однострочный заголовок
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x_pos = x + (w - text_w) // 2
        y_pos = y + (h - text_h) // 2
        draw.text((x_pos, y_pos), text, fill=styles.COLOR_BLACK, font=font)

    def _draw_data_cell(self, draw: ImageDraw, text: str, x: int, y: int, 
                        w: int, h: int, align: str):
        """Отрисовывает ячейку данных."""
        styles = self.styles
        font = self._get_font(styles.TABLE_DATA_FONT_SIZE_PT)

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
        draw.text((x_pos, y_pos), str(text), fill=styles.COLOR_BLACK, font=font)

    def _get_cell_text(self, header: str, player, report_data: ReportData, 
                       period_index: Optional[int]) -> str:
        """Формирует текст для ячейки."""
        if header == "№":
            return player.number
        elif header == "Игрок":
            return player.full_name
        elif header in ["Кол-во смен в матче", "Смен в периоде"]:
            shifts = report_data.shifts_by_player_id.get(player.player_id, [])
            if period_index is not None:
                seg = report_data.segments_info[period_index]
                count = sum(1 for s in shifts 
                           if seg.official_start <= s.official_start < seg.official_end)
            else:
                count = len(shifts)
            return str(count)
        elif header in ["Ср. время смены", "Время в матче", "Время в периоде",
                       "Больш.", "Меньш.", "Г", "П", "+/-", "Ш"]:
            return "---"  # Заглушка для статистики
        else:
            return ""

    def _draw_graphics_match(self, draw: ImageDraw, report_data: ReportData, 
                             geom: dict, header_height: float):
        """
        Отрисовывает графику для листа 'Матч' (полная шкала 0-60/65 минут).
        """
        if not report_data.segments_info:
            return

        total_end = max(seg.official_end for seg in report_data.segments_info)
        time_range = total_end

        # Рисуем шкалу game_mode (НОВОЕ)
        self._draw_game_mode_scale(draw, report_data, geom, time_range=time_range, 
                                is_match_level=True, period_abs_start=0)

        # Рисуем верхнюю шкалу времени
        self._draw_top_time_scale(draw, geom, time_range=time_range, is_match_level=True)

        # Рисуем смены
        self._draw_shifts(draw, report_data, geom, time_range=time_range, 
                          period_start=0, header_height=header_height)

        # Рисуем нижнюю шкалу времени
        self._draw_time_scale(draw, geom, time_range=time_range, is_match_level=True)

        # Рисуем шкалу голов
        authors_y = self._draw_goals_scale(draw, report_data, geom, 
                                           time_range=time_range, period_start=0)

        # Рисуем авторов голов
        self._draw_goal_authors_vertical(draw, report_data, geom, time_range=time_range,
                                         period_start=0, authors_y=authors_y)

    def _draw_graphics_period(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                              period_index: int, header_height: float):
        """
        Отрисовывает графику для листа 'Период' (локальная шкала 0-20 минут).
        """
        if period_index >= len(report_data.segments_info):
            return

        segment = report_data.segments_info[period_index]
        period_start = segment.official_start
        period_end = segment.official_end
        time_range = period_end - period_start

        # Рисуем шкалу game_mode (НОВОЕ)
        self._draw_game_mode_scale(draw, report_data, geom, time_range=time_range,
                                is_match_level=False, period_abs_start=period_start)

        # Рисуем верхнюю шкалу времени
        self._draw_top_time_scale(draw, geom, time_range=time_range, 
                                  is_match_level=False, period_abs_start=period_start)

        # Рисуем смены только этого периода
        self._draw_shifts(draw, report_data, geom, time_range=time_range,
                          period_start=period_start, header_height=header_height)

        # Рисуем нижнюю шкалу времени периода
        self._draw_time_scale(draw, geom, time_range=time_range, 
                              is_match_level=False, period_abs_start=period_start)

        # Рисуем голы только этого периода
        authors_y = self._draw_goals_scale(draw, report_data, geom, 
                                           time_range=time_range, period_start=period_start)

        # Рисуем авторов голов
        self._draw_goal_authors_vertical(draw, report_data, geom, time_range=time_range,
                                         period_start=period_start, authors_y=authors_y)

    def _draw_top_time_scale(self, draw: ImageDraw, geom: dict, time_range: float,
                            is_match_level: bool, period_abs_start: float = 0):
        """
        Верхняя шкала времени — располагается на линии низа заголовка таблицы.
        """
        styles = self.styles
        
        time_scale_x = geom["x"]
        time_scale_width = geom["width"]
        time_scale_height = styles.TIME_SCALE_HEIGHT_PX
        
        # Низ шкалы = content_y (низ заголовка таблицы)
        scale_bottom_y = geom["content_y"]
        time_scale_y = scale_bottom_y - time_scale_height

        if time_range <= 0:
            return

        scale_factor = time_scale_width / time_range

        # Фон
        draw.rectangle([time_scale_x, time_scale_y,
                    time_scale_x + time_scale_width, scale_bottom_y],
                    outline=styles.COLOR_BLACK, 
                    fill=styles.COLOR_WHITE,
                    width=styles.TIME_SCALE_OUTLINE_WIDTH)

        # Шрифт
        font = self._get_font(styles.TIME_SCALE_FONT_SIZE_PT)

        tick_interval = 300 if is_match_level else 60

        for i, local_time in enumerate(range(0, int(time_range) + 1, tick_interval)):
            x_pos = time_scale_x + int(local_time * scale_factor)

            draw.line([(x_pos, time_scale_y), (x_pos, scale_bottom_y)],
                    fill=styles.COLOR_BLACK, 
                    width=styles.TIME_SCALE_TICK_WIDTH)

            absolute_time = local_time if is_match_level else period_abs_start + local_time
            minutes = int(absolute_time // 60)
            label_text = f"{minutes}'"

            text_bbox = draw.textbbox((0, 0), label_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            if i == 0:
                label_x = x_pos + 3
            else:
                if len(str(minutes)) == 1:
                    label_x = x_pos - 1 - text_width
                else:
                    label_x = x_pos - 3 - text_width

            label_y = time_scale_y + (time_scale_height - text_height) // 2 - 4
            draw.text((label_x, label_y), label_text, fill=styles.COLOR_BLACK, font=font)

        # Линия-разделитель под шкалой (совпадает с content_y)
        draw.line([(time_scale_x, scale_bottom_y), 
                (time_scale_x + time_scale_width, scale_bottom_y)],
                fill=styles.COLOR_GRID, 
                width=styles.TABLE_GRID_LINE_WIDTH)

    def _draw_time_scale(self, draw: ImageDraw, geom: dict, time_range: float,
                         is_match_level: bool, period_abs_start: float = 0):
        """
        Нижняя шкала времени.
        """
        styles = self.styles
        
        time_scale_x = geom["x"]
        time_scale_y = geom["y"] + geom["height"]
        time_scale_width = geom["width"]
        time_scale_height = styles.TIME_SCALE_HEIGHT_PX

        if time_range <= 0:
            return

        scale_factor = time_scale_width / time_range

        # Фон
        draw.rectangle([time_scale_x, time_scale_y,
                       time_scale_x + time_scale_width, time_scale_y + time_scale_height],
                      outline=styles.COLOR_BLACK,
                      fill=styles.COLOR_WHITE,
                      width=styles.TIME_SCALE_OUTLINE_WIDTH)

        # Шрифт
        font = self._get_font(styles.TIME_SCALE_FONT_SIZE_PT)

        # Тики
        tick_interval = 300 if is_match_level else 60

        for i, local_time in enumerate(range(0, int(time_range) + 1, tick_interval)):
            x_pos = time_scale_x + int(local_time * scale_factor)

            draw.line([(x_pos, time_scale_y), 
                      (x_pos, time_scale_y + time_scale_height)],
                     fill=styles.COLOR_BLACK,
                     width=styles.TIME_SCALE_TICK_WIDTH)

            absolute_time = local_time if is_match_level else period_abs_start + local_time
            minutes = int(absolute_time // 60)
            label_text = f"{minutes}'"

            text_bbox = draw.textbbox((0, 0), label_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            if i == 0:
                label_x = x_pos + 3
            else:
                if len(str(minutes)) == 1:
                    label_x = x_pos - 1 - text_width
                else:
                    label_x = x_pos - 3 - text_width

            label_y = (time_scale_y + (time_scale_height - text_height) // 2) - 4
            draw.text((label_x, label_y), label_text, fill=styles.COLOR_BLACK, font=font)

    def _draw_shifts(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                    time_range: float, period_start: float, header_height: float):
        """
        Универсальный метод отрисовки смен.
        """
        styles = self.styles
        
        def interpolate_color(color1, color2, factor):
            r = int(color1[0] + (color2[0] - color1[0]) * factor)
            g = int(color1[1] + (color2[1] - color1[1]) * factor)
            b = int(color1[2] + (color2[2] - color1[2]) * factor)
            return (r, g, b)

        def get_gradient_color(duration, position_in_shift):
            if duration <= 35:
                return interpolate_color(styles.COLOR_VERY_LIGHT_GREEN, 
                                        styles.COLOR_DARK_GREEN, 
                                        position_in_shift)
            elif duration <= 70:
                threshold = 35 / duration
                if position_in_shift <= threshold:
                    local_pos = position_in_shift / threshold
                    return interpolate_color(styles.COLOR_VERY_LIGHT_GREEN,
                                            styles.COLOR_DARK_GREEN,
                                            local_pos)
                else:
                    local_pos = (position_in_shift - threshold) / (1 - threshold)
                    return interpolate_color(styles.COLOR_DARK_GREEN,
                                            styles.COLOR_ORANGE,
                                            local_pos)
            else:
                threshold1 = 35 / duration
                threshold2 = 70 / duration
                if position_in_shift <= threshold1:
                    local_pos = position_in_shift / threshold1
                    return interpolate_color(styles.COLOR_VERY_LIGHT_GREEN,
                                            styles.COLOR_DARK_GREEN,
                                            local_pos)
                elif position_in_shift <= threshold2:
                    local_pos = (position_in_shift - threshold1) / (threshold2 - threshold1)
                    return interpolate_color(styles.COLOR_DARK_GREEN,
                                            styles.COLOR_ORANGE,
                                            local_pos)
                else:
                    local_pos = (position_in_shift - threshold2) / (1 - threshold2)
                    return interpolate_color(styles.COLOR_ORANGE,
                                            styles.COLOR_BRIGHT_RED,
                                            local_pos)

        graphic_width = geom["width"]
        graphic_x = geom["x"]
        # === ИСПРАВЛЕНО: начинаем от content_y, а не от geom["y"] + header_height ===
        graphic_y = geom["content_y"]
        graphic_height = geom["height"] - (geom["content_y"] - geom["y"])

        if time_range <= 0:
            return

        scale_factor = graphic_width / time_range

        # Рисуем горизонтальные линии строк
        row_height = self._calculate_table_geometry(report_data)["body_row_height"]
        num_rows = len(report_data.players_list) if report_data.players_list else 22

        for row_idx in range(num_rows + 1):
            line_y = graphic_y + row_idx * row_height
            if line_y <= geom["y"] + geom["height"]:
                draw.line([(graphic_x, line_y), (graphic_x + graphic_width, line_y)],
                        fill=styles.COLOR_GRID_LIGHT,
                        width=styles.SHIFT_GRID_LINE_WIDTH)

        # Рисуем смены игроков
        for player_index, player_info in enumerate(report_data.players_list):
            y_pos = graphic_y + player_index * row_height
            y_middle = y_pos + (row_height // 2)
            y_bottom = y_pos + row_height

            player_shifts = report_data.shifts_by_player_id.get(player_info.player_id, [])

            for shift_info in player_shifts:
                if shift_info.official_end <= period_start or shift_info.official_start >= period_start + time_range:
                    continue

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
                draw.line([(x_start, y_pos), (x_end, y_pos)], 
                        fill=styles.COLOR_BLACK, 
                        width=styles.SHIFT_BORDER_WIDTH)
                draw.line([(x_start, y_pos), (x_start, y_middle)], 
                        fill=styles.COLOR_BLACK,
                        width=styles.SHIFT_BORDER_WIDTH)
                draw.line([(x_end, y_pos), (x_end, y_middle)], 
                        fill=styles.COLOR_BLACK,
                        width=styles.SHIFT_BORDER_WIDTH)

                # Нижняя часть (белая)
                draw.rectangle([x_start, y_middle, x_end, y_bottom],
                            fill=styles.COLOR_WHITE,
                            outline=styles.COLOR_BLACK,
                            width=styles.SHIFT_BORDER_WIDTH)
                draw.line([(x_start, y_middle), (x_end, y_middle)], 
                        fill=styles.COLOR_BLACK,
                        width=styles.SHIFT_DIVIDER_WIDTH)

                # Подпись номера смены и длительности
                self._draw_shift_label(draw, x_start, x_end, y_pos, y_middle, 
                                    y_bottom, row_height, shift_info, 
                                    graphic_x, graphic_width)

    def _draw_shift_label(self, draw: ImageDraw, x_start: int, x_end: int, y_pos: int,
                          y_middle: int, y_bottom: int, row_height: int, shift_info,
                          graphic_x: int, graphic_width: int):
        """Отрисовывает подпись смены (номер и длительность)."""
        styles = self.styles
        
        MIN_WIDTH_FOR_HORIZONTAL_TEXT = 50
        TEXT_PADDING_X = 3

        shift_number_text = f"{shift_info.number}."
        duration_text = f'{int(shift_info.duration)}"'

        font = self._get_font(styles.SHIFT_LABEL_FONT_SIZE_PT)

        number_bbox = draw.textbbox((0, 0), shift_number_text, font=font)
        duration_bbox = draw.textbbox((0, 0), duration_text, font=font)

        number_width = number_bbox[2] - number_bbox[0]
        duration_width = duration_bbox[2] - duration_bbox[0]
        text_height = number_bbox[3] - number_bbox[1]

        total_text_width = number_width + duration_width + (TEXT_PADDING_X * 3)
        shift_width = x_end - x_start
        lower_half_height = row_height // 2

        if shift_width >= MIN_WIDTH_FOR_HORIZONTAL_TEXT and total_text_width <= shift_width:
            # Горизонтальный текст
            text_y = y_middle + (lower_half_height - text_height) // 2
            number_x = x_start + TEXT_PADDING_X
            draw.text((number_x, text_y), shift_number_text, 
                     fill=styles.COLOR_BLACK, font=font)
            duration_x = x_end - duration_width - TEXT_PADDING_X
            draw.text((duration_x, text_y), duration_text, 
                     fill=styles.COLOR_BLACK, font=font)
        else:
            # Вертикальный текст
            vertical_text = f"{shift_info.number}.     {int(shift_info.duration)}\""
            
            margin = 2
            temp_img_size = (200, 100)
            temp_img = Image.new('RGBA', temp_img_size, (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((margin, margin), vertical_text, 
                          fill=styles.COLOR_BLACK, font=font)

            text_bbox = temp_draw.textbbox((margin, margin), vertical_text, font=font)
            crop_box = (
                max(0, text_bbox[0] - 1),
                max(0, text_bbox[1] - 1),
                min(temp_img_size[0], text_bbox[2] + 1),
                min(temp_img_size[1], text_bbox[3] + 1)
            )
            text_only = temp_img.crop(crop_box)
            rotated = text_only.rotate(90, expand=True, resample=Image.BICUBIC)

            is_first_shift = x_start < (graphic_x + graphic_width * 0.05)
            label_offset = 3

            if is_first_shift:
                label_x = x_end + label_offset
            else:
                label_x = x_start - rotated.width - label_offset

            label_y = y_pos + (row_height - rotated.height) // 2

            if label_x < 0:
                label_x = x_end + label_offset

            if rotated.mode == 'RGBA':
                background = Image.new('RGB', rotated.size, (255, 255, 255))
                background.paste(rotated, mask=rotated.split()[3])
                rotated = background

            draw._image.paste(rotated, (label_x, label_y))

    def _draw_goals_scale(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                        time_range: float, period_start: float) -> int:
        """
        Шкала голов.
        """
        styles = self.styles
        
        COLOR_OUR_GOAL = styles.COLOR_OUR_GOAL
        COLOR_THEIR_GOAL = styles.COLOR_THEIR_GOAL
        COLOR_DIVIDER = styles.COLOR_DIVIDER
        COLOR_TEXT = styles.COLOR_BLACK

        SCALE_HEIGHT = styles.GOALS_SCALE_HEIGHT_PX
        TOP_HALF_HEIGHT = styles.GOALS_SCALE_TOP_HALF_PX
        BOTTOM_HALF_HEIGHT = styles.GOALS_SCALE_BOTTOM_HALF_PX

        time_scale_height = styles.TIME_SCALE_HEIGHT_PX
        time_scale_y = geom["y"] + geom["height"]
        scale_y = time_scale_y + time_scale_height

        scale_x = geom["x"]
        scale_width = geom["width"]

        # Рисуем фон шкалы
        draw.rectangle([scale_x, scale_y, scale_x + scale_width, scale_y + SCALE_HEIGHT],
                    fill=styles.COLOR_WHITE,
                    outline=COLOR_DIVIDER,
                    width=styles.GOALS_SCALE_OUTLINE_WIDTH)

        divider_y = scale_y + TOP_HALF_HEIGHT
        draw.line([(scale_x, divider_y), (scale_x + scale_width, divider_y)],
                fill=COLOR_DIVIDER,
                width=styles.GOALS_SCALE_DIVIDER_WIDTH)

        if time_range <= 0:
            return scale_y + SCALE_HEIGHT

        scale_factor = scale_width / time_range
        font = self._get_font(styles.GOALS_SCALE_FONT_SIZE_PT)
        score_ranges = self._get_score_ranges(report_data, period_start, time_range)

        # === content_y — низ заголовка таблицы, куда идут линии голов ===
        content_y = geom["content_y"]

        for goal in report_data.goals:
            if not (period_start <= goal.official_time < period_start + time_range):
                continue

            team = goal.context.get('team', '')
            is_our_goal = (team == report_data.our_team_key)
            color = COLOR_OUR_GOAL if is_our_goal else COLOR_THEIR_GOAL

            local_time = goal.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)

            # ВЕРХНЯЯ ПОЛОВИНА: колышек
            peg_top = scale_y + 3
            peg_bottom = divider_y - 2
            draw.line([(x_pos, peg_top), (x_pos, peg_bottom)], 
                    fill=color, 
                    width=styles.GOAL_PEG_WIDTH)
            draw.line([(x_pos - 2, peg_bottom), (x_pos + 2, peg_bottom)], 
                    fill=color,
                    width=styles.GOAL_PEG_BASE_WIDTH)

            # НИЖНЯЯ ПОЛОВИНА: счёт
            score_text = self._get_score_at_time(score_ranges, goal.official_time)
            if score_text:
                text_bbox = draw.textbbox((0, 0), score_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                text_x = x_pos - text_width // 2
                text_y = (divider_y + (BOTTOM_HALF_HEIGHT - text_height) // 2) - 4

                if text_x < scale_x + 2:
                    text_x = scale_x + 2
                if text_x + text_width > scale_x + scale_width - 2:
                    text_x = scale_x + scale_width - text_width - 2

                draw.text((text_x, text_y), score_text, fill=COLOR_TEXT, font=font)

            # ПУНКТИРНАЯ ЛИНИЯ ВВЕРХ — до content_y (низ заголовка таблицы)
            line_top = content_y
            line_bottom = scale_y

            dot_spacing = 8
            for y in range(int(line_top), int(line_bottom), dot_spacing):
                dot_y_end = min(y + 3, int(line_bottom))
                draw.line([(x_pos, y), (x_pos, dot_y_end)], 
                        fill=color,
                        width=styles.GOAL_DASHED_LINE_WIDTH)

        return scale_y + SCALE_HEIGHT

    def _get_score_ranges(self, report_data: ReportData, period_start: float, 
                          time_range: float) -> list:
        """Извлекает диапазоны счёта из calculated_ranges."""
        score_ranges = []

        match_obj = report_data.original_project.match
        calculated_ranges = getattr(match_obj, 'calculated_ranges', [])

        for cr in calculated_ranges:
            if getattr(cr, 'label_type', '') == 'Счёт':
                from utils.helpers import convert_global_to_official_time
                try:
                    official_start = convert_global_to_official_time(cr.start_time, calculated_ranges)
                    official_end = convert_global_to_official_time(cr.end_time, calculated_ranges)

                    if official_start is not None and official_end is not None:
                        score_ranges.append({
                            'name': cr.name,
                            'start': official_start,
                            'end': official_end
                        })
                except:
                    continue

        return score_ranges

    def _get_score_at_time(self, score_ranges: list, goal_time: float) -> str:
        """Возвращает счёт после гола."""
        for sr in score_ranges:
            if sr['start'] <= goal_time < sr['end']:
                if abs(sr['start'] - goal_time) < 1.0:
                    return sr['name']

        for sr in score_ranges:
            if sr['start'] > goal_time:
                return sr['name']

        return ""

    def _draw_goal_authors_vertical(self, draw: ImageDraw, report_data: ReportData, 
                                    geom: dict, time_range: float, period_start: float, 
                                    authors_y: int):
        """Отрисовывает авторов голов вертикально под шкалой."""
        styles = self.styles
        
        COLOR_TEXT = styles.COLOR_BLACK

        if time_range <= 0:
            return

        scale_x = geom["x"]
        scale_width = geom["width"]
        scale_factor = scale_width / time_range

        font = self._get_font(styles.GOAL_AUTHOR_FONT_SIZE_PT)

        # Собираем голы с позициями
        goals_with_positions = []
        for goal in report_data.goals:
            if not (period_start <= goal.official_time < period_start + time_range):
                continue

            local_time = goal.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)

            player_name = goal.context.get('player_name', 'Unknown')
            player_id_fhm = goal.context.get('player_id_fhm', '')

            player_number = ""
            for player in report_data.players_list:
                if player.player_id == player_id_fhm:
                    player_number = player.number
                    break

            author_text = f"{player_number} {player_name}" if player_number else player_name

            goals_with_positions.append({
                'goal': goal,
                'x': x_pos,
                'text': author_text
            })

        MIN_SPACING = 20
        goals_with_positions.sort(key=lambda g: g['x'])
        positions = []

        for i, gwp in enumerate(goals_with_positions):
            base_x = gwp['x']
            offset = 0

            text_bbox = draw.textbbox((0, 0), gwp['text'], font=font)
            text_width = text_bbox[2] - text_bbox[0]

            conflict_left = False
            for prev_g, prev_offset, prev_x, prev_width in positions:
                prev_actual_x = prev_x + prev_offset
                if abs(base_x - prev_actual_x) < MIN_SPACING:
                    conflict_left = True
                    break

            if conflict_left:
                offset = text_width // 2 + 5
                if base_x + offset + text_width > scale_x + scale_width:
                    offset = -(text_width // 2 + 5)
                    if base_x + offset < scale_x:
                        offset = 0

            positions.append((gwp, offset, base_x, text_width))

        # Рисуем подписи
        for gwp, offset, base_x, text_width in positions:
            text = gwp['text']

            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]

            temp_img = Image.new('RGBA', (text_w + 4, text_h + 4), (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((2, 2), text, fill=COLOR_TEXT, font=font)

            rotated = temp_img.rotate(90, expand=True, resample=Image.BICUBIC)

            final_x = base_x + offset - rotated.width // 2
            final_y = authors_y + 5

            if final_x < scale_x:
                final_x = scale_x
            if final_x + rotated.width > scale_x + scale_width:
                final_x = scale_x + scale_width - rotated.width

            if rotated.mode == 'RGBA':
                draw._image.paste(rotated, (final_x, final_y), rotated)
            else:
                draw._image.paste(rotated, (final_x, final_y))

    def _draw_game_mode_scale(self, draw: ImageDraw, report_data: ReportData,
                            geom: dict, time_range: float,
                            is_match_level: bool, period_abs_start: float = 0):
        """
        Отрисовывает шкалу численного состава (game_mode) над верхней шкалой времени.
        Показывает режимы игры: "5 на 5", "5 на 4", "4 на 5" и т.д.
        """
        styles = self.styles
        
        # Координаты и размеры
        scale_x = geom["x"]
        scale_width = geom["width"]
        scale_height = styles.GAME_MODE_SCALE_HEIGHT_PX
        
        # Получаем высоту заголовка таблицы для позиционирования
        header_height = geom.get("header_height", 0)
        
        # НОВОЕ: шкала в самом верху графической области
        scale_y = geom["y"]
        scale_bottom_y = scale_y + scale_height
        
        if time_range <= 0:
            return
        
        scale_factor = scale_width / time_range
        
        # Фон шкалы
        draw.rectangle(
            [scale_x, scale_y, scale_x + scale_width, scale_bottom_y],
            fill=styles.GAME_MODE_BG_COLOR,
            outline=styles.GAME_MODE_GRID_COLOR,
            width=styles.GAME_MODE_LINE_WIDTH
        )
        
        # Загружаем шрифт
        font_size_px = int(styles.GAME_MODE_FONT_SIZE_PT * (self.dpi / 72))
        try:
            font = ImageFont.truetype("arial.ttf", font_size_px)
        except OSError:
            try:
                font = ImageFont.truetype("tahoma.ttf", font_size_px)
            except OSError:
                font = ImageFont.load_default()
        
        # Получаем и фильтруем game_modes
        game_modes = self._get_filtered_game_modes(
            report_data, time_range, period_abs_start, is_match_level
        )
        
        # Рисуем каждый режим
        for gm in game_modes:
            # Преобразуем в локальные координаты
            local_start = gm['local_start']
            local_end = gm['local_end']
            mode_name = gm['name']
            
            x_start = scale_x + int(local_start * scale_factor)
            x_end = scale_x + int(local_end * scale_factor)
            
            # Гарантируем минимальную ширину в 1 пиксель
            if x_end <= x_start:
                x_end = x_start + 1
            
            interval_width = x_end - x_start
            
            # Вертикальные линии-тики на границах
            draw.line(
                [(x_start, scale_y), (x_start, scale_bottom_y)],
                fill=styles.GAME_MODE_GRID_COLOR,
                width=styles.GAME_MODE_LINE_WIDTH
            )
            draw.line(
                [(x_end, scale_y), (x_end, scale_bottom_y)],
                fill=styles.GAME_MODE_GRID_COLOR,
                width=styles.GAME_MODE_LINE_WIDTH
            )
            
            # Рисуем текст режима
            text_bbox = draw.textbbox((0, 0), mode_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # Определяем ориентацию текста
            if interval_width >= styles.GAME_MODE_MIN_WIDTH_FOR_HORIZONTAL and text_width <= interval_width - 6:
                # Горизонтальный текст
                text_x = x_start + (interval_width - text_width) // 2
                text_y = scale_y + (scale_height - text_height) // 2 - 2
                draw.text((text_x, text_y), mode_name, fill=styles.GAME_MODE_TEXT_COLOR, font=font)
            else:
                # Вертикальный текст
                self._draw_vertical_game_mode_text(
                    draw, mode_name, x_start, x_end, scale_y, scale_height, 
                    styles.GAME_MODE_TEXT_COLOR, font
                )
        
        # Нижняя граница (разделитель с временной шкалой)
        draw.line(
            [(scale_x, scale_bottom_y), (scale_x + scale_width, scale_bottom_y)],
            fill=styles.GAME_MODE_GRID_COLOR,
            width=styles.GAME_MODE_LINE_WIDTH
        )


    def _get_filtered_game_modes(self, report_data: ReportData, time_range: float,
                                period_abs_start: float, is_match_level: bool) -> list:
        """
        Фильтрует и преобразует game_modes для отображения.
        Возвращает список словарей с local_start, local_end, name.
        """
        result = []
        
        # Получаем сырые данные
        raw_modes = getattr(report_data.original_project.match, 'calculated_ranges', [])
        game_modes = [cr for cr in raw_modes if getattr(cr, 'label_type', '') == 'game_mode']
        
        if not game_modes:
            return result
        
        # Сортируем по времени начала
        game_modes.sort(key=lambda x: x.start_time)
        
        # Конвертируем время и фильтруем
        from utils.helpers import convert_global_to_official_time
        
        for gm in game_modes:
            try:
                official_start = convert_global_to_official_time(
                    gm.start_time, 
                    report_data.original_project.match.calculated_ranges
                )
                official_end = convert_global_to_official_time(
                    gm.end_time,
                    report_data.original_project.match.calculated_ranges
                )
            except:
                continue
            
            if official_start is None or official_end is None:
                continue
            
            # Для периода: фильтруем по пересечению с периодом
            if not is_match_level:
                period_end = period_abs_start + time_range
                # Проверяем пересечение
                if official_end <= period_abs_start or official_start >= period_end:
                    continue
                
                # Обрезаем границы периодом
                display_start = max(official_start, period_abs_start)
                display_end = min(official_end, period_end)
            else:
                display_start = official_start
                display_end = official_end
            
            # Преобразуем в локальное время
            local_start = display_start - period_abs_start
            local_end = display_end - period_abs_start
            
            # Ограничиваем диапазон
            local_start = max(0, local_start)
            local_end = min(time_range, local_end)
            
            if local_end > local_start:
                result.append({
                    'local_start': local_start,
                    'local_end': local_end,
                    'name': getattr(gm, 'name', '5 на 5')
                })
        
        return result


    def _draw_vertical_game_mode_text(self, draw: ImageDraw, text: str, 
                                    x_start: int, x_end: int, scale_y: int, 
                                    scale_height: int, color: str, font):
        """
        Рисует текст режима вертикально (поворот на 90 градусов).
        """
        # Создаём временное изображение для текста
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        margin = 2
        temp_width = text_width + 2 * margin
        temp_height = text_height + 2 * margin
        
        temp_img = Image.new('RGBA', (temp_width, temp_height), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((margin, margin), text, fill=color, font=font)
        
        # Поворачиваем на 90 градусов
        rotated = temp_img.rotate(90, expand=True, resample=Image.BICUBIC)
        
        # Центрируем по интервалу
        interval_width = x_end - x_start
        label_x = x_start + (interval_width - rotated.height) // 2
        label_y = scale_y + (scale_height - rotated.width) // 2
        
        # Проверка границ
        if label_x < x_start:
            label_x = x_start + 2
        if label_x + rotated.width > x_end:
            label_x = x_end - rotated.width - 2
        
        # Накладываем на основное изображение
        if rotated.mode == 'RGBA':
            draw._image.paste(rotated, (label_x, label_y), rotated)
        else:
            draw._image.paste(rotated, (label_x, label_y))
