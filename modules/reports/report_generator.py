# report_generator.py — рефакторинг табличной части

import os
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, fields
from PIL import Image, ImageDraw, ImageFont
from modules.reports.report_data import ReportData, ShiftInfo, GoalInfo, PenaltyInfo, SegmentInfo


# ============================================
# КОНФИГУРАЦИЯ ТАБЛИЦ (новая версия)
# ============================================

# Описание колонки: ключ, ожидаемый формат для расчёта ширины, выравнивание
@dataclass
class ColumnConfig:
    key: str                    # Ключ для идентификации
    width_format: str           # Строка для измерения ширины при TABLE_DATA_FONT_SIZE_PT
    align: str                  # "left", "right", "center"
    is_player_name: bool = False  # Особая логика для фамилий


# Конфигурация для отчёта "Матч" (11 колонок)
TABLE_CONFIG_MATCH = [
    ColumnConfig("number", "99", "right"),           # №
    ColumnConfig("player", "", "left", is_player_name=True),  # Игрок (ширина динамическая)
    ColumnConfig("shifts_count", "99", "center"),    # СМ
    ColumnConfig("avg_shift", "99\"", "center"),     # СрСм (секунды со знаком")
    ColumnConfig("total_time", "99:99", "center"),   # ВрМ
    ColumnConfig("powerplay", "99:99", "center"),    # Б
    ColumnConfig("penalty_kill", "99:99", "center"), # М
    ColumnConfig("goals", "9", "right"),             # Г
    ColumnConfig("assists", "9", "right"),           # П
    ColumnConfig("plus_minus", "+9", "right"),       # +/-
    ColumnConfig("penalties", "99", "right"),        # Ш
]

# Конфигурация для отчёта "Период" (10 колонок)
TABLE_CONFIG_PERIOD = [
    ColumnConfig("number", "99", "right"),           # №
    ColumnConfig("player", "", "left", is_player_name=True),  # Игрок
    ColumnConfig("shifts_count", "99", "center"),    # СП
    ColumnConfig("period_time", "99:99", "center"),  # ВрП
    ColumnConfig("powerplay", "99:99", "center"),    # Б
    ColumnConfig("penalty_kill", "99:99", "center"), # М
    ColumnConfig("goals", "9", "right"),             # Г
    ColumnConfig("assists", "9", "right"),           # П
    ColumnConfig("plus_minus", "+9", "right"),       # +/-
    ColumnConfig("penalties", "99", "right"),        # Ш
]


# ============================================
# РАЗМЕРЫ ЛИСТОВ (без изменений)
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
# СТИЛИ ОТЧЁТА (обновлённые)
# ============================================


@dataclass(frozen=True)
class ReportStyles:
    """
    Все визуальные константы отчёта в одном месте.
    При frozen=True экземпляр неизменяем — защита от случайных модификаций.
    """
    
    # ============================================
    # ШРИФТЫ
    # ============================================
    
    # Основной шрифт для всего отчёта (таблица, шкалы, подписи)
    # Должен поддерживать кириллицу и быть моноширинным или пропорциональным
    FONT_FAMILY_PRIMARY: str = "arial.ttf"
    
    # Запасной шрифт, если основной не найден в системе
    FONT_FAMILY_FALLBACK: str = "tahoma.ttf"
    
    # ============================================
    # РАЗМЕРЫ ШРИФТОВ (в пунктах, pt)
    # ============================================
    
    # Заголовок листа ("Карта смен — Матч/Период 1")
    # Крупный, заметный, по центру вверху страницы
    HEADER_FONT_SIZE_PT: int = 12
    
    # Основной размер для данных в таблице (номера, время, статистика)
    # Баланс между читаемостью и компактностью
    TABLE_DATA_FONT_SIZE_PT: int = 9
    
    # Минимальный размер для длинных фамилий (динамически подбирается 8-9pt)
    # Не меньше 8pt чтобы оставаться читаемым после печати
    TABLE_DATA_MIN_FONT_SIZE_PT: int = 8
    
    # Мелкий шрифт для подвала (нумерация страниц, копирайт)
    # Может быть мелким — служебная информация
    FOOTER_FONT_SIZE_PT: int = 5
    
    # Размер счёта на шкале голов ("2:1", "3:2")
    # Компактный, много подписей в ограниченном пространстве
    GOALS_SCALE_FONT_SIZE_PT: int = 6
    
    # Подписи времени на временных шкалах ("0'", "20'", "40'")
    TIME_SCALE_FONT_SIZE_PT: int = 6
    
    # Номер смены и её длительность внутри прямоугольника смены ("5. 45\"")
    # Минимальный читаемый размер для плотной информации
    SHIFT_LABEL_FONT_SIZE_PT: int = 5
    
    # Авторы голов под шкалой голов ("77 Иванов")
    GOAL_AUTHOR_FONT_SIZE_PT: int = 5
    
    # ============================================
    # ЦВЕТА (hex RGB)
    # ============================================
    
    # Белый фон для всех ячеек и областей по умолчанию
    COLOR_WHITE: str = "#FFFFFF"
    
    # Чёрный цвет для текста и линий сетки
    COLOR_BLACK: str = "#000000"
    
    # Светло-серый фон для заголовка таблицы (отличие от данных)
    COLOR_HEADER_BG: str = "#EEEEEE"
    
    # Основной цвет линий сетки таблицы (средне-серый, заметный)
    COLOR_GRID: str = "#9B9B9B"
    
    # Светлый серый для горизонтальных линий в графической части (разделение строк)
    COLOR_GRID_LIGHT: str = "#E0E0E0"
    
    # Синий — наши голы на шкале голов
    COLOR_OUR_GOAL: str = "#0064C8"
    
    # Красный — голы соперника на шкале голов
    COLOR_THEIR_GOAL: str = "#C80032"
    
    # Серый для разделителей и вспомогательных линий
    COLOR_DIVIDER: str = "#A0A0A0"
    
    # ============================================
    # ЦВЕТА ГРАДИЕНТА СМЕН (RGB tuples)
    # ============================================
    
    # Очень светло-зелёный: смена до 35 секунд (начало градиента)
    COLOR_VERY_LIGHT_GREEN: Tuple[int, int, int] = (212, 247, 213)
    
    # Насыщенный зелёный: 35-70 секунд (средняя длительность)
    COLOR_DARK_GREEN: Tuple[int, int, int] = (18, 229, 29)
    
    # Оранжевый: 70+ секунд, первая фаза (длинная смена, внимание)
    COLOR_ORANGE: Tuple[int, int, int] = (231, 95, 36)
    
    # Тёмно-красный: 70+ секунд, вторая фаза (критически длинная смена)
    COLOR_BRIGHT_RED: Tuple[int, int, int] = (79, 48, 15)
    
    # ============================================
    # ЦВЕТА GAME MODE (неравные составы)
    # ============================================
    
    # Светло-зелёный: наше большинство +1 (5 на 4, 4 на 3)
    COLOR_GM_POWERPLAY_LIGHT: str = "#90EE90"
    
    # Насыщенный зелёный: наше большинство +2 (5 на 3)
    COLOR_GM_POWERPLAY_STRONG: str = "#228B22"
    
    # Светло-жёлтый: наше меньшинство −1 (4 на 5, 3 на 4)
    COLOR_GM_PENALTY_KILL_LIGHT: str = "#FFE4B5"
    
    # Насыщенный жёлтый: наше меньшинство −2 (3 на 5)
    COLOR_GM_PENALTY_KILL_STRONG: str = "#FFA500"
    
    # Светло-фиолетовый: равные составы 4 на 4
    COLOR_GM_EVEN_4ON4: str = "#DDA0DD"
    
    # Насыщенный фиолетовый: равные составы 3 на 3 (овертайм)
    COLOR_GM_EVEN_3ON3: str = "#9370DB"
    
    # ============================================
    # БАЗОВЫЕ ПАРАМЕТРЫ
    # ============================================
    
    # Разрешение печати (точек на дюйм)
    # 300 DPI — стандарт качественной печати, чёткие линии и текст
    DPI: int = 300
    
    # ============================================
    # ПОЛЯ ЛИСТА (отступы от краёв в пикселях)
    # ============================================
    
    # Верхнее поле — место для заголовка листа
    MARGIN_TOP: int = 100
    
    # Нижнее поле — место для подвала с нумерацией
    MARGIN_BOTTOM: int = 100
    
    # Левое поле — отступ для таблицы
    MARGIN_LEFT: int = 100
    
    # Правое поле — минимальный отступ
    MARGIN_RIGHT: int = 50
    
    # ============================================
    # РАБОЧАЯ ОБЛАСТЬ (основное пространство листа)
    # ============================================
    
    # Высота рабочей области как доля от доступной (85% — остальное на поля и заголовок)
    CONTENT_AREA_HEIGHT_PERCENT: float = 0.85
    
    # Отступ сверху внутри рабочей области (5% — воздух под заголовком листа)
    CONTENT_AREA_TOP_MARGIN_PERCENT: float = 0.05
    
    # Максимальная ширина таблицы (39% — остальное 61% под графику минимум)
    TABLE_MAX_WIDTH_PERCENT: float = 0.25
    
    # ============================================
    # ПАРАМЕТРЫ ТАБЛИЦЫ
    # ============================================
    
    # Фиксированное количество строк (22 игрока максимум, включая запасных)
    NUM_TABLE_ROWS: int = 22
    
    # Высота заголовка таблицы относительно обычной строки (1.5 = в полтора раза выше)
    # Позволяет разместить многострочные или наклонные заголовки
    HEADER_HEIGHT_RATIO: float = 1.5
    
    # Толщина линий сетки таблицы (внутренние границы ячеек)
    TABLE_GRID_LINE_WIDTH: int = 2
    
    # Толщина внешней рамки таблицы (контур всей таблицы)
    TABLE_OUTLINE_WIDTH: int = 2
    
    # Горизонтальный отступ текста от края ячейки (3px — минимум для читаемости)
    TABLE_CELL_PADDING_X: int = 6
    
    # Вертикальный отступ (минимальный, текст центрируется по высоте)
    TABLE_CELL_PADDING_Y: int = 2
    
    # Процент фамилий, которые должны влезать в колонку основным шрифтом (9pt)
    # Остальные подбирают размер 8-9pt динамически
    PLAYER_NAME_COVERAGE_PERCENT: float = 0.80
    
    # ============================================
    # ГРАФИЧЕСКАЯ ОБЛАСТЬ
    # ============================================
    
    # Толщина рамки вокруг всей графической области (2px — заметная граница)
    GRAPHIC_AREA_BORDER_WIDTH: int = 2
    
    # Цвет рамки графической области (тёмно-красный, отличимый от сетки)
    GRAPHIC_AREA_BORDER_COLOR: str = "#B31919"
    
    # ============================================
    # ВРЕМЕННЫЕ ШКАЛЫ (верхняя и нижняя)
    # ============================================
    
    # Высота шкалы времени (30px — место для тиков и подписей)
    TIME_SCALE_HEIGHT_PX: int = 30
    
    # Толщина вертикальных тиков (меток времени)
    TIME_SCALE_TICK_WIDTH: int = 1
    
    # Толщина рамки шкалы времени
    TIME_SCALE_OUTLINE_WIDTH: int = 2
    
    # ============================================
    # ШКАЛА ГОЛОВ
    # ============================================
    
    # Общая высота шкалы голов (60px — две половины по 30px)
    GOALS_SCALE_HEIGHT_PX: int = 60
    
    # Высота верхней половины (колышки голов)
    GOALS_SCALE_TOP_HALF_PX: int = 30
    
    # Высота нижней половины (счёт матча)
    GOALS_SCALE_BOTTOM_HALF_PX: int = 30
    
    # Толщина вертикальной линии колышка гола
    GOAL_PEG_WIDTH: int = 3
    
    # Ширина горизонтального основания колышка (чтобы было похоже на "Т")
    GOAL_PEG_BASE_WIDTH: int = 4
    
    # Толщина пунктирной линии вверх от гола к графику смен
    GOAL_DASHED_LINE_WIDTH: int = 4
    
    # Толщина рамки шкалы голов
    GOALS_SCALE_OUTLINE_WIDTH: int = 2
    
    # Толщина разделителя между верхней и нижней половиной
    GOALS_SCALE_DIVIDER_WIDTH: int = 1
    
    # ============================================
    # ОТРИСОВКА СМЕН (графическая часть)
    # ============================================
    
    # Толщина горизонтальных линий, разделяющих строки игроков
    SHIFT_GRID_LINE_WIDTH: int = 2
    
    # Толщина контура смены (верх, лево, право)
    SHIFT_BORDER_WIDTH: int = 1
    
    # Толщина разделителя внутри смены (между градиентом и белой частью)
    SHIFT_DIVIDER_WIDTH: int = 1
    
    # ============================================
    # ПОДВАЛ ЛИСТА
    # ============================================
    
    # Высота подвала (нумерация, копирайт)
    FOOTER_HEIGHT_PX: int = 30
    
    # Толщина линии-разделителя над подвалом
    FOOTER_DIVIDER_WIDTH: int = 1
    
    # ============================================
    # ШКАЛА GAME MODE (численный состав)
    # ============================================
    
    # Высота шкалы game_mode (тонкая полоска под верхней временной шкалой)
    GAME_MODE_SCALE_HEIGHT_PX: int = 30
    
    # Размер шрифта для подписей режимов ("5 на 5", "5 на 4")
    GAME_MODE_FONT_SIZE_PT: int = 6
    
    # Фон шкалы game_mode (белый, как и везде)
    GAME_MODE_BG_COLOR: str = "#FFFFFF"
    
    # Цвет текста подписей режимов
    GAME_MODE_TEXT_COLOR: str = "#000000"
    
    # Цвет линий сетки и границ интервалов
    GAME_MODE_GRID_COLOR: str = "#818181"
    
    # Толщина линий шкалы game_mode
    GAME_MODE_LINE_WIDTH: int = 2
    
    # Минимальная ширина интервала для горизонтального текста (иначе — под шкалой)
    GAME_MODE_MIN_WIDTH_FOR_HORIZONTAL: int = 60
    
    # Прозрачность цветных наложений (0-255, 120 = полупрозрачный)
    GAME_MODE_OVERLAY_ALPHA: int = 120
    
    # Толщина рамки вокруг наложения game_mode
    GAME_MODE_BORDER_WIDTH: int = 2
    
    # ============================================
    # УДАЛЕНИЯ (штрафы)
    # ============================================
    
    # Цвет рамки и диагоналей удаления (красный, заметный)
    COLOR_PENALTY_BOX: str = "#D21111"
    
    # Толщина линий удаления (крест-накрест)
    PENALTY_LINE_WIDTH: int = 3
    
    # ============================================
    # ШКАЛА ВБРАСЫВАНИЙ (ЧИИ)
    # ============================================
    
    # Высота шкалы вбрасываний (под верхней временной шкалой)
    FACEOFF_SCALE_HEIGHT_PX: int = 30
    
    # Толщина вертикальной линии колышка вбрасывания
    FACEOFF_PEG_WIDTH: int = 3
    
    # Ширина горизонтальной перекладины "Т"
    FACEOFF_PEG_BASE_WIDTH: int = 6
    
    # Цвет колышка вбрасывания (серый, нейтральный)
    FACEOFF_PEG_COLOR: str = "#808080"
    
    # Цвет вертикальной линии вниз от вбрасывания
    FACEOFF_LINE_COLOR: str = "#A0A0A0"
    
    # Толщина вертикальной линии вниз
    FACEOFF_LINE_WIDTH: int = 1
    
    # Пунктирная линия вниз: (3px линия, 3px пробел)
    FACEOFF_LINE_DASH: tuple = (3, 3)


# ============================================
# КЛАСС ОТЧЁТА (обновлённая табличная часть)
# ============================================

class PlayerShiftMapReport:
    """
    Генератор отчёта "Карта смен игрока".
    """

    def __init__(self, page_size: str = 'A4'):
        if page_size not in SIZE_MAP:
            raise ValueError(f"Неподдерживаемый размер страницы: {page_size}")

        self.page_size = page_size
        self.dpi = DPI
        self.width_px, self.height_px = SIZE_MAP[page_size]
        self.styles = ReportStyles()
        self.mode = 'game_on_sheet'
        
        # Кэш для шрифтов
        self._font_cache: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}

    def _get_font(self, size_pt: float, bold: bool = False) -> ImageFont.FreeTypeFont:
        """
        Возвращает шрифт с кэшированием.
        """
        cache_key = (round(size_pt * 10), bold)  # Округляем для кэша
        
        if cache_key not in self._font_cache:
            size_px = int(size_pt * (self.styles.DPI / 72))
            families = [self.styles.FONT_FAMILY_PRIMARY, self.styles.FONT_FAMILY_FALLBACK]
            
            font = None
            for family in families:
                try:
                    font = ImageFont.truetype(family, size_px)
                    break
                except OSError:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
            
            self._font_cache[cache_key] = font
        
        return self._font_cache[cache_key]

    def _measure_text_width(self, text: str, font_size_pt: float) -> int:
        """
        Измеряет ширину текста в пикселях.
        """
        if not text:
            return 0
        
        font = self._get_font(font_size_pt)
        # Используем временный ImageDraw для измерения
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0]

    def generate_all(self, report_data: ReportData) -> List[Image.Image]:
        """
        Генерирует полный набор листов отчёта.
        """
        images = []
        num_periods = len(report_data.segments_info)
        total_pages = 1 + num_periods

        # Лист "Матч"
        print("Генерация листа 'Матч'...")
        match_sheet = self._generate_sheet(
            report_data,
            mode='game_on_sheet',
            period_index=0,
            page_num=1,
            total_pages=total_pages
        )
        images.append(match_sheet)

        # Листы периодов
        for i in range(num_periods):
            period_name = f"Период {i+1}" if i < 3 else "Овертайм"
            print(f"Генерация листа '{period_name}'...")
            period_sheet = self._generate_sheet(
                report_data,
                mode='period_on_sheet',
                period_index=i,
                page_num=i + 2,
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

        # Заголовок листа
        if mode == 'game_on_sheet':
            sheet_title = "Карта смен — Матч"
            columns_config = TABLE_CONFIG_MATCH
        else:
            period_name = f"Период {period_index + 1}" if period_index < 3 else "Овертайм"
            sheet_title = f"Карта смен — {period_name}"
            columns_config = TABLE_CONFIG_PERIOD

        # Расчёт геометрии
        table_geom = self._calculate_table_geometry_v2(report_data, columns_config)
        graphic_geom = self._calculate_graphic_geometry(table_geom)

        # Создание изображения
        img = Image.new('RGB', (self.width_px, self.height_px), 
                        color=self.styles.COLOR_WHITE)
        draw = ImageDraw.Draw(img)

        # Заголовок листа
        self._draw_sheet_header(draw, sheet_title, table_geom)

        # Таблица (новая версия)
        self._draw_table_v2(draw, report_data, table_geom, columns_config, period_index)

        # Графическая часть (существующая, без изменений)
        if mode == 'game_on_sheet':
            self._draw_graphics_match(draw, report_data, graphic_geom, 
                                    table_geom["header_height"])
        else:
            self._draw_graphics_period(draw, report_data, graphic_geom, 
                                     period_index, table_geom["header_height"])

        # Рамка графической области
        self._draw_graphic_area_border(draw, graphic_geom)

        # Подвал
        self._draw_sheet_footer(draw, page_num, total_pages, table_geom)

        return img

    # ============================================
    # НОВАЯ ТАБЛИЧНАЯ ЧАСТЬ (v2)
    # ============================================

    def _calculate_table_geometry_v2(self, report_data: ReportData, 
                                     columns_config: List[ColumnConfig]) -> dict:
        """
        Расчёт геометрии таблицы v2.
        """
        styles = self.styles
        
        # Доступное пространство
        available_width = self.width_px - styles.MARGIN_LEFT - styles.MARGIN_RIGHT
        available_height = self.height_px - styles.MARGIN_TOP - styles.MARGIN_BOTTOM
        
        content_height = int(styles.CONTENT_AREA_HEIGHT_PERCENT * available_height)
        content_top_margin = int(styles.CONTENT_AREA_TOP_MARGIN_PERCENT * available_height)
        content_y = styles.MARGIN_TOP + content_top_margin
        
        content_width = available_width
        content_x = styles.MARGIN_LEFT
        
        # Максимальная ширина таблицы
        max_table_width = int(content_width * styles.TABLE_MAX_WIDTH_PERCENT)
        
        # Расчёт ширин колонок
        col_widths = []
        player_col_index = -1
        player_col_width = 0
        
        for i, col_config in enumerate(columns_config):
            if col_config.is_player_name:
                # Игрок — отложим на потом
                player_col_index = i
                col_widths.append(0)  # Заглушка
                continue
            
            # Измеряем ширину формата
            text_width = self._measure_text_width(
                col_config.width_format, 
                styles.TABLE_DATA_FONT_SIZE_PT
            )
            col_width = text_width + 2 * styles.TABLE_CELL_PADDING_X
            col_widths.append(col_width)
        
        # Ширина для колонки "Игрок"
        sum_other_widths = sum(col_widths)
        player_col_width = max_table_width - sum_other_widths
        
        # Минимальная ширина для игрока (чтобы не было абсурда)
        min_player_width = int(max_table_width * 0.25)  # Мин. 25% от макс. таблицы
        if player_col_width < min_player_width:
            player_col_width = min_player_width
            # Пересчитываем: уменьшаем другие колонки пропорционально, если нужно
            # Пока оставляем как есть — графика пострадает, но таблица читаема
        
        col_widths[player_col_index] = player_col_width
        
        # Расчёт высоты строк
        total_rows_height = content_height
        draft_row_height = total_rows_height / (styles.NUM_TABLE_ROWS + styles.HEADER_HEIGHT_RATIO)
        
        row_height = int(draft_row_height)
        header_height = total_rows_height - (styles.NUM_TABLE_ROWS * row_height)
        
        # Минимальные проверки
        min_row_height = int(self._measure_text_width("99", styles.TABLE_DATA_MIN_FONT_SIZE_PT) * 1.5)
        if row_height < min_row_height:
            row_height = min_row_height
            header_height = total_rows_height - (styles.NUM_TABLE_ROWS * row_height)
        
        min_header_height = int(row_height * styles.HEADER_HEIGHT_RATIO)
        if header_height < min_header_height:
            header_height = min_header_height
            # Пересчитываем row_height
            row_height = (total_rows_height - header_height) // styles.NUM_TABLE_ROWS
        
        # Подготовка данных для фамилий
        player_fonts = self._prepare_player_fonts(
            report_data.players_list, 
            player_col_width,
            styles.TABLE_DATA_FONT_SIZE_PT,
            styles.TABLE_DATA_MIN_FONT_SIZE_PT,
            styles.TABLE_CELL_PADDING_X
        )
        
        geometry = {
            "x": content_x,
            "y": content_y,
            "width": sum(col_widths),
            "height": total_rows_height,
            "header_height": header_height,
            "row_height": row_height,
            "column_widths": col_widths,
            "content_x": content_x,
            "content_y": content_y,
            "content_width": content_width,
            "content_height": content_height,
            "player_fonts": player_fonts,  # Кэш шрифтов для игроков
        }
        
        print(f"DEBUG Table Geometry v2: width={geometry['width']}, "
              f"player_col={player_col_width}, row_height={row_height}, "
              f"header_height={header_height}")
        
        return geometry

    def _prepare_player_fonts(self, players_list: List, player_col_width: int,
                              normal_size: float, min_size: float, 
                              padding: int) -> Dict[str, Dict]:
        """
        Подбирает шрифт для каждого игрока.
        Возвращает: player_id -> {'font_size': size, 'text': formatted_name}
        """
        result = {}
        max_text_width = player_col_width - 2 * padding
        
        for player in players_list:
            formatted_name = self._format_player_name(player.full_name)
            
            # Бинарный поиск оптимального размера шрифта
            low, high = min_size, normal_size
            best_size = min_size
            
            while high - low > 0.25:  # Точность 0.25pt
                mid = (low + high) / 2
                text_width = self._measure_text_width(formatted_name, mid)
                
                if text_width <= max_text_width:
                    best_size = mid
                    low = mid  # Пробуем больше
                else:
                    high = mid  # Нужно меньше
            
            result[player.player_id] = {
                'font_size': best_size,
                'text': formatted_name
            }
        
        return result

    def _format_player_name(self, full_name: str) -> str:
        """
        Форматирует Ф.И.О. в "Фамилия И."
        """
        if not full_name:
            return "?"
        
        parts = full_name.strip().split()
        if len(parts) >= 2:
            surname = parts[0]
            initial = parts[1][0] + "." if parts[1] else ""
            return f"{surname} {initial}"
        return full_name

    def _draw_table_v2(self, draw: ImageDraw, report_data: ReportData, 
                       geom: dict, columns_config: List[ColumnConfig],
                       period_index: Optional[int]):
        """
        Отрисовка таблицы v2.
        """
        styles = self.styles
        
        x_offset = geom["x"]
        y_offset = geom["y"]
        header_height = geom["header_height"]
        row_height = geom["row_height"]
        col_widths = geom["column_widths"]
        player_fonts = geom["player_fonts"]
        
        # --- Заголовок ---
        header_y = y_offset
        current_x = x_offset
        
        for i, col_config in enumerate(columns_config):
            col_width = col_widths[i]
            
            # Фон заголовка
            draw.rectangle(
                [current_x, header_y, current_x + col_width, header_y + header_height],
                fill=styles.COLOR_HEADER_BG,
                outline=styles.COLOR_GRID,
                width=styles.TABLE_GRID_LINE_WIDTH
            )
            
            # Текст заголовка (пока как есть, позже сократим)
            self._draw_header_cell_v2(draw, col_config.key, current_x, header_y, 
                                      col_width, header_height)
            
            current_x += col_width
        
        # --- Строки данных ---
        num_rows = styles.NUM_TABLE_ROWS
        
        for row_idx in range(num_rows):
            player = report_data.players_list[row_idx] if row_idx < len(report_data.players_list) else None
            row_y = y_offset + header_height + row_idx * row_height
            
            current_x = x_offset
            for i, col_config in enumerate(columns_config):
                col_width = col_widths[i]
                
                # Фон ячейки
                draw.rectangle(
                    [current_x, row_y, current_x + col_width, row_y + row_height],
                    fill=styles.COLOR_WHITE,
                    outline=styles.COLOR_GRID_LIGHT,
                    width=styles.TABLE_GRID_LINE_WIDTH
                )
                
                # Текст ячейки
                if player:
                    if col_config.is_player_name:
                        # Особая отрисовка игрока с подобранным шрифтом
                        font_info = player_fonts.get(player.player_id, {
                            'font_size': styles.TABLE_DATA_MIN_FONT_SIZE_PT,
                            'text': "?"
                        })
                        self._draw_player_cell(draw, font_info, current_x, row_y,
                                              col_width, row_height, col_config.align)
                    else:
                        # Обычная ячейка
                        text = self._get_cell_text_v2(col_config.key, player, 
                                                      report_data, period_index)
                        self._draw_data_cell_v2(draw, text, current_x, row_y, 
                                                col_width, row_height, 
                                                col_config.align, 
                                                styles.TABLE_DATA_FONT_SIZE_PT)
                
                current_x += col_width
        
        # Внешняя рамка
        draw.rectangle(
            [x_offset, y_offset, x_offset + geom["width"], y_offset + geom["height"]],
            outline=styles.COLOR_BLACK,
            width=styles.TABLE_OUTLINE_WIDTH
        )

    def _draw_header_cell_v2(self, draw: ImageDraw, text: str, x: int, y: int,
                             w: int, h: int):
        """
        Отрисовка ячейки заголовка v2.
        Пока просто центрируем. Позже: сокращения, переносы.
        """
        styles = self.styles
        font = self._get_font(styles.TABLE_DATA_FONT_SIZE_PT)
        
        # Замена на временные сокращения для компактности
        display_text = self._shorten_header(text)
        
        bbox = draw.textbbox((0, 0), display_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        x_pos = x + (w - text_w) // 2
        y_pos = y + (h - text_h) // 2
        
        draw.text((x_pos, y_pos), display_text, fill=styles.COLOR_BLACK, font=font)

    def _shorten_header(self, key: str) -> str:
        """Временные сокращения для заголовков."""
        mapping = {
            "number": "№",
            "player": "Игрок",
            "shifts_count": "СМ",
            "avg_shift": "СрСм",
            "total_time": "ВрМ",
            "period_time": "ВрП",
            "powerplay": "Б",
            "penalty_kill": "М",
            "goals": "Г",
            "assists": "П",
            "plus_minus": "+/-",
            "penalties": "Ш",
        }
        return mapping.get(key, key)

    def _draw_player_cell(self, draw: ImageDraw, font_info: dict, x: int, y: int,
                          w: int, h: int, align: str):
        """
        Отрисовка ячейки с именем игрока (с динамическим шрифтом).
        """
        styles = self.styles
        
        text = font_info['text']
        font_size = font_info['font_size']
        font = self._get_font(font_size)
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # Выравнивание
        padding = styles.TABLE_CELL_PADDING_X
        if align == "center":
            x_pos = x + (w - text_w) // 2
        elif align == "right":
            x_pos = x + w - text_w - padding
        else:  # left
            x_pos = x + padding
        
        y_pos = y + (h - text_h) // 2
        
        draw.text((x_pos, y_pos), text, fill=styles.COLOR_BLACK, font=font)

    def _draw_data_cell_v2(self, draw: ImageDraw, text: str, x: int, y: int,
                           w: int, h: int, align: str, font_size: float):
        """
        Отрисовка обычной ячейки данных v2.
        """
        styles = self.styles
        font = self._get_font(font_size)
        
        bbox = draw.textbbox((0, 0), str(text), font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        padding = styles.TABLE_CELL_PADDING_X
        
        if align == "center":
            x_pos = x + (w - text_w) // 2
        elif align == "right":
            x_pos = x + w - text_w - padding
        else:  # left
            x_pos = x + padding
        
        y_pos = y + (h - text_h) // 2
        
        draw.text((x_pos, y_pos), str(text), fill=styles.COLOR_BLACK, font=font)

    def _get_cell_text_v2(self, key: str, player, report_data: ReportData,
                          period_index: Optional[int]) -> str:
        """
        Получение текста для ячейки v2.
        """
        shifts = report_data.shifts_by_player_id.get(player.player_id, [])
        
        # Фильтрация смен по периоду (если нужно)
        if period_index is not None:
            seg = report_data.segments_info[period_index]
            period_shifts = [s for s in shifts 
                           if seg.official_start <= s.official_start < seg.official_end]
        else:
            period_shifts = shifts
        
        # Подсчёт статистики
        if key == "number":
            return player.number
        
        elif key == "shifts_count":
            return str(len(period_shifts))
        
        elif key == "avg_shift":
            # Среднее время смены в секундах
            if not period_shifts:
                return "0\""
            total_duration = sum(s.duration for s in period_shifts)
            avg_seconds = int(total_duration / len(period_shifts))
            return f"{avg_seconds}\""
        
        elif key in ["total_time", "period_time"]:
            # Общее время в формате MM:SS
            if not period_shifts:
                return "0:00"
            total_seconds = int(sum(s.duration for s in period_shifts))
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02d}"
        
        elif key in ["powerplay", "penalty_kill"]:
            # Время в большинстве/меньшинстве — пока заглушка
            return "0:00"
        
        elif key == "goals":
            # Голы игрока — пока заглушка
            return "0"
        
        elif key == "assists":
            # Передачи — пока заглушка
            return "0"
        
        elif key == "plus_minus":
            # +/- — пока заглушка
            return "0"
        
        elif key == "penalties":
            # Штрафные минуты — пока заглушка
            return "0"
        
        return ""

    # ============================================
    # СУЩЕСТВУЮЩИЕ МЕТОДЫ (без изменений или минимальные правки)
    # ============================================

    def _draw_sheet_header(self, draw: ImageDraw, title: str, geom: dict):
        """Заголовок листа."""
        styles = self.styles
        font = self._get_font(styles.HEADER_FONT_SIZE_PT)
        
        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        content_x = geom["content_x"]
        content_width = geom["content_width"]
        
        x = content_x + (content_width - text_width) // 2
        y = 40
        
        draw.text((x, y), title, fill=styles.COLOR_BLACK, font=font)

    def _draw_sheet_footer(self, draw: ImageDraw, page_num: int, total_pages: int, geom: dict):
        """Подвал с нумерацией."""
        styles = self.styles
        font = self._get_font(styles.FOOTER_FONT_SIZE_PT)
        
        content_x = geom["content_x"]
        content_width = geom["content_width"]
        
        BOTTOM_PADDING = 20
        text_bottom = self.height_px - BOTTOM_PADDING
        
        sample_bbox = draw.textbbox((0, 0), "1/5", font=font)
        text_height = sample_bbox[3] - sample_bbox[1]
        
        footer_y = text_bottom - text_height
        line_y = footer_y - 5
        
        page_text = f"{page_num}/{total_pages}"
        draw.text((content_x, footer_y), page_text, fill=styles.COLOR_BLACK, font=font)
        
        copyright_text = 'Отчет составлен программным комплексом "HockeyTagagger v.4". Все права не защищены'
        text_bbox = draw.textbbox((0, 0), copyright_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x_center = content_x + (content_width - text_width) // 2 * 2
        draw.text((x_center, footer_y), copyright_text, fill=styles.COLOR_BLACK, font=font)
        
        draw.line(
            [(content_x, line_y), (content_x + content_width, line_y)],
            fill=styles.COLOR_GRID,
            width=styles.FOOTER_DIVIDER_WIDTH
        )

    def _calculate_graphic_geometry(self, table_geom: dict) -> dict:
        """Расчёт геометрии графической части."""
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
        
        return {
            "x": graphic_x,
            "y": graphic_y,
            "width": graphic_width,
            "height": graphic_height,
            "header_height": header_height,
            "content_y": graphic_y + header_height,
        }

    def _draw_graphic_area_border(self, draw: ImageDraw, geom: dict):
        """Рамка вокруг графической области."""
        styles = self.styles
        
        draw.rectangle(
            [geom["x"], geom["y"], geom["x"] + geom["width"], geom["y"] + geom["height"]],
            outline=styles.GRAPHIC_AREA_BORDER_COLOR,
            width=styles.GRAPHIC_AREA_BORDER_WIDTH
        )

    # ============================================
    # ГРАФИЧЕСКАЯ ЧАСТЬ (сохранена как есть из оригинала)
    # ============================================
    
    def _draw_graphics_match(self, draw: ImageDraw, report_data: ReportData, 
                             geom: dict, header_height: float):
        """Графика для листа 'Матч'."""
        if not report_data.segments_info:
            return

        total_end = max(seg.official_end for seg in report_data.segments_info)
        time_range = total_end

        self._draw_game_mode_scale_lines(draw, report_data, geom, time_range=time_range, 
                                is_match_level=True, period_abs_start=0)
        
        self._draw_game_mode_overlays(draw, report_data, geom, time_range=time_range,
                                      is_match_level=True, period_abs_start=0)

        authors_y = self._draw_goals_scale(draw, report_data, geom, 
                                           time_range=time_range, period_start=0)

        self._draw_goal_authors_horizontal(draw, report_data, geom, 
                                        time_range=time_range, 
                                        period_start=0, 
                                        authors_y=authors_y)

        self._draw_penalties(draw, report_data, geom, time_range=time_range, 
                            period_start=0)

        self._draw_shifts(draw, report_data, geom, time_range=time_range, 
                          period_start=0, header_height=header_height)

        self._draw_time_scale(draw, geom, time_range=time_range, is_match_level=True)

        self._draw_top_time_scale(draw, geom, time_range=time_range, is_match_level=True)

        self._draw_game_mode_scale_text(draw, report_data, geom, time_range=time_range, 
                                is_match_level=True, period_abs_start=0)
        
        self._draw_faceoffs_scale(draw, report_data, geom,
                                time_range=time_range, 
                                period_start=0)

    def _draw_graphics_period(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                              period_index: int, header_height: float):
        """Графика для листа 'Период'."""
        if period_index >= len(report_data.segments_info):
            return

        segment = report_data.segments_info[period_index]
        period_start = segment.official_start
        period_end = segment.official_end
        time_range = period_end - period_start

        self._draw_game_mode_scale_lines(draw, report_data, geom, time_range=time_range,
                                is_match_level=False, period_abs_start=period_start)
        
        self._draw_game_mode_overlays(draw, report_data, geom, time_range=time_range,
                                      is_match_level=False, period_abs_start=period_start)

        authors_y = self._draw_goals_scale(draw, report_data, geom, 
                                           time_range=time_range, period_start=period_start)
        
        self._draw_goal_authors_horizontal(draw, report_data, geom, 
                                        time_range=time_range, 
                                        period_start=period_start, 
                                        authors_y=authors_y)

        self._draw_penalties(draw, report_data, geom, time_range=time_range, 
                            period_start=period_start)

        self._draw_shifts(draw, report_data, geom, time_range=time_range,
                          period_start=period_start, header_height=header_height)
        
        self._draw_time_scale(draw, geom, time_range=time_range, 
                              is_match_level=False, period_abs_start=period_start)
                   
        self._draw_top_time_scale(draw, geom, time_range=time_range, 
                                  is_match_level=False, period_abs_start=period_start)
 
        self._draw_game_mode_scale_text(draw, report_data, geom, time_range=time_range,
                                is_match_level=False, period_abs_start=period_start)
        
        self._draw_faceoffs_scale(draw, report_data, geom,
                                time_range=time_range, 
                                period_start=period_start)

    # --- Все методы графики из оригинала (сохранены без изменений) ---
    
    def _draw_top_time_scale(self, draw: ImageDraw, geom: dict, time_range: float,
                            is_match_level: bool, period_abs_start: float = 0):
        """Верхняя шкала времени."""
        styles = self.styles
        
        time_scale_x = geom["x"]
        time_scale_width = geom["width"]
        time_scale_height = styles.TIME_SCALE_HEIGHT_PX
        
        scale_bottom_y = geom["content_y"]
        time_scale_y = scale_bottom_y - time_scale_height

        if time_range <= 0:
            return

        scale_factor = time_scale_width / time_range

        draw.rectangle([time_scale_x, time_scale_y,
                    time_scale_x + time_scale_width, scale_bottom_y],
                    outline=styles.COLOR_BLACK, 
                    width=styles.TIME_SCALE_OUTLINE_WIDTH)

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

        draw.line([(time_scale_x, scale_bottom_y), 
                (time_scale_x + time_scale_width, scale_bottom_y)],
                fill=styles.COLOR_GRID, 
                width=styles.TABLE_GRID_LINE_WIDTH)

    def _draw_time_scale(self, draw: ImageDraw, geom: dict, time_range: float,
                         is_match_level: bool, period_abs_start: float = 0):
        """Нижняя шкала времени."""
        styles = self.styles
        
        time_scale_x = geom["x"]
        time_scale_y = geom["y"] + geom["height"]
        time_scale_width = geom["width"]
        time_scale_height = styles.TIME_SCALE_HEIGHT_PX

        if time_range <= 0:
            return

        scale_factor = time_scale_width / time_range

        draw.rectangle([time_scale_x, time_scale_y,
                       time_scale_x + time_scale_width, time_scale_y + time_scale_height],
                      outline=styles.COLOR_BLACK,
                      width=styles.TIME_SCALE_OUTLINE_WIDTH)

        font = self._get_font(styles.TIME_SCALE_FONT_SIZE_PT)

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
        """Отрисовка смен."""
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
        graphic_y = geom["content_y"]
        graphic_height = geom["height"] - (geom["content_y"] - geom["y"])

        if time_range <= 0:
            return

        scale_factor = graphic_width / time_range

        # Рисуем горизонтальные линии строк
        row_height = self._calculate_table_geometry_v2(report_data, TABLE_CONFIG_MATCH)["row_height"]
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
        """Отрисовывает подпись смены."""
        styles = self.styles
        
        MIN_WIDTH_FOR_HORIZONTAL_TEXT = 50
        TEXT_PADDING_X = 3

        shift_number_text = f"{shift_info.number}."
        duration_text = f'{int(shift_info.duration)}"'
        
        shift_width = x_end - x_start
        
        font_horizontal = self._get_font(styles.SHIFT_LABEL_FONT_SIZE_PT)
        number_bbox = draw.textbbox((0, 0), shift_number_text, font=font_horizontal)
        duration_bbox = draw.textbbox((0, 0), duration_text, font=font_horizontal)
        number_width = number_bbox[2] - number_bbox[0]
        duration_width = duration_bbox[2] - duration_bbox[0]
        text_height = number_bbox[3] - number_bbox[1]
        total_text_width = number_width + duration_width + (TEXT_PADDING_X * 3)

        if shift_width >= MIN_WIDTH_FOR_HORIZONTAL_TEXT and total_text_width <= shift_width:
            # Горизонтальный текст
            lower_half_height = row_height // 2
            text_y = y_middle + (lower_half_height - text_height) // 2
            
            number_x = x_start + TEXT_PADDING_X
            draw.text((number_x, text_y), shift_number_text, 
                     fill=styles.COLOR_BLACK, font=font_horizontal)
            
            duration_x = x_end - duration_width - TEXT_PADDING_X
            draw.text((duration_x, text_y), duration_text, 
                     fill=styles.COLOR_BLACK, font=font_horizontal)
        else:
            # Вертикальный текст
            number_len = len(str(shift_info.number))
            duration_len = len(str(int(shift_info.duration)))

            if number_len == 1 and duration_len == 1:
                vertical_text = f"{shift_info.number}.     {int(shift_info.duration)}\""
            elif number_len == 1 and duration_len == 2:
                vertical_text = f"{shift_info.number}.    {int(shift_info.duration)}\""
            elif number_len == 1 and duration_len == 3:
                vertical_text = f"{shift_info.number}.  {int(shift_info.duration)}\""
            elif number_len == 2 and duration_len == 1:
                vertical_text = f"{shift_info.number}.    {int(shift_info.duration)}\""
            elif number_len == 2 and duration_len == 2:
                vertical_text = f"{shift_info.number}.   {int(shift_info.duration)}\""
            elif number_len == 2 and duration_len == 3:
                vertical_text = f"{shift_info.number}. {int(shift_info.duration)}\""
            else:
                vertical_text = f"{shift_info.number}. {int(shift_info.duration)}\""
            
            font_size = styles.SHIFT_LABEL_FONT_SIZE_PT
            font = self._get_font(font_size)
            
            temp_width = 200
            temp_height = 50
            temp_img = Image.new('RGBA', (temp_width, temp_height), (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            
            margin = 2
            temp_draw.text((margin, margin), vertical_text, fill=styles.COLOR_BLACK, font=font)
            
            text_bbox = temp_draw.textbbox((margin, margin), vertical_text, font=font)
            crop_left = max(0, text_bbox[0] - 1)
            crop_top = max(0, text_bbox[1] - 1)
            crop_right = min(temp_width, text_bbox[2] + 1)
            crop_bottom = min(temp_height, text_bbox[3] + 1)
            
            text_only = temp_img.crop((crop_left, crop_top, crop_right, crop_bottom))
            rotated = text_only.rotate(90, expand=True, resample=Image.BICUBIC)
            
            text_w, text_h = rotated.size
            
            is_first_shift = x_start < (graphic_x + graphic_width * 0.05)
            label_offset = 3
            
            if is_first_shift:
                paste_x = x_end + label_offset
            else:
                paste_x = x_start - text_w - label_offset
            
            paste_y = y_pos + (row_height - text_h) // 2
            
            if paste_x < graphic_x:
                paste_x = x_end + label_offset
            
            main_image = draw._image
            
            img_width, img_height = main_image.size
            if (paste_x < 0 or paste_y < 0 or 
                paste_x + text_w > img_width or paste_y + text_h > img_height):
                paste_x = max(0, min(paste_x, img_width - text_w))
                paste_y = max(0, min(paste_y, img_height - text_h))
            
            background = main_image.crop((paste_x, paste_y, paste_x + text_w, paste_y + text_h))
            
            if background.mode != 'RGBA':
                background = background.convert('RGBA')
            
            composite = Image.alpha_composite(background, rotated)
            main_image.paste(composite, (paste_x, paste_y))

    def _draw_goals_scale(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                        time_range: float, period_start: float) -> int:
        """Шкала голов."""
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

        goals_with_data = []
        for goal in report_data.goals:
            if not (period_start <= goal.official_time < period_start + time_range):
                continue

            team = goal.context.get('team', '')
            is_our_goal = (team == report_data.our_team_key)
            color = COLOR_OUR_GOAL if is_our_goal else COLOR_THEIR_GOAL

            local_time = goal.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)

            score_text = self._get_score_at_time(score_ranges, goal.official_time)
            
            if score_text:
                text_bbox = draw.textbbox((0, 0), score_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
            else:
                text_width = 0
                text_height = 0

            goals_with_data.append({
                'goal': goal,
                'x': x_pos,
                'color': color,
                'score_text': score_text,
                'text_width': text_width,
                'text_height': text_height
            })

        current_level_is_top = False
        
        for i, gwd in enumerate(goals_with_data):
            if not gwd['score_text']:
                continue
                
            need_switch_to_top = False
            
            if i > 0 and not current_level_is_top:
                prev_gwd = goals_with_data[i - 1]
                if prev_gwd['score_text']:
                    prev_center_x = prev_gwd['x']
                    curr_center_x = gwd['x']
                    prev_half_width = prev_gwd['text_width'] / 2
                    curr_half_width = gwd['text_width'] / 2
                    
                    prev_left = prev_center_x - prev_half_width
                    prev_right = prev_center_x + prev_half_width
                    curr_left = curr_center_x - curr_half_width
                    curr_right = curr_center_x + curr_half_width
                    
                    if curr_left < prev_right + 3:
                        need_switch_to_top = True
            
            is_top = need_switch_to_top
            current_level_is_top = is_top
            
            if is_top:
                text_y = scale_y + (TOP_HALF_HEIGHT - gwd['text_height']) // 2 - 2
            else:
                text_y = (divider_y + (BOTTOM_HALF_HEIGHT - gwd['text_height']) // 2) - 4

            peg_top = scale_y + 3
            peg_bottom = divider_y - 2
            draw.line([(gwd['x'], peg_top), (gwd['x'], peg_bottom)], 
                    fill=gwd['color'], 
                    width=styles.GOAL_PEG_WIDTH)
            draw.line([(gwd['x'] - 2, peg_bottom), (gwd['x'] + 2, peg_bottom)], 
                    fill=gwd['color'],
                    width=styles.GOAL_PEG_BASE_WIDTH)

            text_x = gwd['x'] - gwd['text_width'] // 2
            
            if text_x < scale_x + 2:
                text_x = scale_x + 2
            if text_x + gwd['text_width'] > scale_x + scale_width - 2:
                text_x = scale_x + scale_width - gwd['text_width'] - 2

            draw.text((text_x, text_y), gwd['score_text'], fill=COLOR_TEXT, font=font)

        content_y = geom["content_y"]
        line_top = max(content_y - styles.TIME_SCALE_HEIGHT_PX, 0)
        
        for gwd in goals_with_data:
            dot_spacing = 8
            for y in range(int(line_top), int(scale_y), dot_spacing):
                dot_y_end = min(y + 3, int(scale_y))
                draw.line([(gwd['x'], y), (gwd['x'], dot_y_end)], 
                        fill=gwd['color'],
                        width=styles.GOAL_DASHED_LINE_WIDTH)

        return scale_y + SCALE_HEIGHT

    def _get_score_ranges(self, report_data: ReportData, period_start: float, 
                          time_range: float) -> list:
        """Извлекает диапазоны счёта."""
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

    def _draw_goal_authors_horizontal(self, draw: ImageDraw, report_data: ReportData, 
                                    geom: dict, time_range: float, period_start: float, 
                                    authors_y: int):
        """Авторы голов горизонтально с змейкой."""
        styles = self.styles
        
        MIN_SPACING = 25
        LEVEL_HEIGHT = 22
        MAX_LEVEL = 4
        LEADER_LINE_COLOR = "#808080"
        LEADER_LINE_DASH = (2, 4)

        if time_range <= 0:
            return

        scale_x = geom["x"]
        scale_width = geom["width"]
        scale_factor = scale_width / time_range

        font = self._get_font(styles.GOAL_AUTHOR_FONT_SIZE_PT)

        player_number_by_id = {
            player.player_id: player.number 
            for player in report_data.players_list
        }

        goals_with_data = []
        for goal in report_data.goals:
            if not (period_start <= goal.official_time < period_start + time_range):
                continue

            local_time = goal.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)

            team = goal.context.get('team', '')
            is_our_goal = (team == report_data.our_team_key)
            color = styles.COLOR_OUR_GOAL if is_our_goal else styles.COLOR_THEIR_GOAL

            player_name = goal.context.get('player_name', 'Unknown')
            player_id_fhm = goal.context.get('player_id_fhm', '')
            player_number = player_number_by_id.get(player_id_fhm, '')
            
            if not player_number and 'player_number' in goal.context:
                player_number = goal.context.get('player_number', '')

            author_text = f"{player_number} {player_name}" if player_number else player_name

            text_bbox = draw.textbbox((0, 0), author_text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]

            goals_with_data.append({
                'goal': goal,
                'base_x': x_pos,
                'peg_y': authors_y - styles.GOALS_SCALE_HEIGHT_PX,
                'text': author_text,
                'text_w': text_w,
                'text_h': text_h,
                'color': color,
                'level': 0,
                'final_x': x_pos,
                'final_y': authors_y
            })

        for i, gwd in enumerate(goals_with_data):
            if gwd['base_x'] - gwd['text_w'] // 2 < scale_x + 2:
                gwd['final_x'] = scale_x + gwd['text_w'] // 2 + 2
            
            if gwd['base_x'] + gwd['text_w'] // 2 > scale_x + scale_width - 2:
                gwd['final_x'] = scale_x + scale_width - gwd['text_w'] // 2 - 2

            if i == 0:
                gwd['level'] = 0
                continue

            current_level = 0
            while current_level < MAX_LEVEL:
                has_overlap = False
                for prev in goals_with_data[:i]:
                    if prev['level'] != current_level:
                        continue
                    prev_left = prev['final_x'] - prev['text_w'] // 2 - 2
                    prev_right = prev['final_x'] + prev['text_w'] // 2 + 2
                    curr_left = gwd['final_x'] - gwd['text_w'] // 2 - 2
                    curr_right = gwd['final_x'] + gwd['text_w'] // 2 + 2
                    
                    if not (curr_right < prev_left or curr_left > prev_right):
                        has_overlap = True
                        break
                
                if not has_overlap:
                    break
                current_level += 1
            
            gwd['level'] = min(current_level, MAX_LEVEL)
            gwd['final_y'] = authors_y + gwd['level'] * LEVEL_HEIGHT

        for gwd in goals_with_data:
            text_x = gwd['final_x'] - gwd['text_w'] // 2
            text_y = gwd['final_y']
            
            if text_x < scale_x + 2:
                text_x = scale_x + 2
            if text_x + gwd['text_w'] > scale_x + scale_width - 2:
                text_x = scale_x + scale_width - gwd['text_w'] - 2

            if gwd['level'] > 0:
                start_x = gwd['base_x']
                start_y = gwd['peg_y']
                end_x = text_x + gwd['text_w'] // 2
                end_y = text_y + gwd['text_h'] // 2
                
                self._draw_dashed_line(draw, start_x, start_y, end_x, end_y, 
                                    LEADER_LINE_COLOR, LEADER_LINE_DASH, 1)

            draw.text((text_x, text_y), gwd['text'], fill=gwd['color'], font=font)

    def _draw_dashed_line(self, draw: ImageDraw, x1: int, y1: int, x2: int, y2: int,
                        color: str, dash: tuple, width: int):
        """Рисует пунктирную линию."""
        dash_len, gap_len = dash
        total_len = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        
        if total_len == 0:
            return
        
        dx = (x2 - x1) / total_len
        dy = (y2 - y1) / total_len
        
        current_dist = 0
        is_dash = True
        
        while current_dist < total_len:
            segment_len = dash_len if is_dash else gap_len
            segment_len = min(segment_len, total_len - current_dist)
            
            if is_dash:
                start_x = int(x1 + dx * current_dist)
                start_y = int(y1 + dy * current_dist)
                end_x = int(x1 + dx * (current_dist + segment_len))
                end_y = int(y1 + dy * (current_dist + segment_len))
                draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
            
            current_dist += segment_len
            is_dash = not is_dash

    def _draw_game_mode_scale_lines(self, draw: ImageDraw, report_data: ReportData,
                                    geom: dict, time_range: float,
                                    is_match_level: bool, period_abs_start: float = 0):
        """Линии шкалы game_mode."""
        styles = self.styles

        scale_x = geom["x"]
        scale_width = geom["width"]
        scale_height = styles.GAME_MODE_SCALE_HEIGHT_PX

        scale_y = geom["y"]
        scale_bottom_y = scale_y + scale_height

        if time_range <= 0:
            return

        scale_factor = scale_width / time_range

        draw.rectangle(
            [scale_x, scale_y, scale_x + scale_width, scale_bottom_y],
            fill=styles.GAME_MODE_BG_COLOR,
            outline=styles.GAME_MODE_GRID_COLOR,
            width=styles.GAME_MODE_LINE_WIDTH
        )

        game_modes = self._get_filtered_game_modes(
            report_data, time_range, period_abs_start, is_match_level
        )

        for gm in game_modes:
            local_start = gm['local_start']
            local_end = gm['local_end']

            x_start = scale_x + int(local_start * scale_factor)
            x_end = scale_x + int(local_end * scale_factor)

            if x_end <= x_start:
                x_end = x_start + 1

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

        draw.line(
            [(scale_x, scale_bottom_y), (scale_x + scale_width, scale_bottom_y)],
            fill=styles.GAME_MODE_GRID_COLOR,
            width=styles.GAME_MODE_LINE_WIDTH
        )

    def _draw_game_mode_scale_text(self, draw: ImageDraw, report_data: ReportData,
                                   geom: dict, time_range: float,
                                   is_match_level: bool, period_abs_start: float = 0):
        """Текст шкалы game_mode."""
        styles = self.styles

        scale_x = geom["x"]
        scale_width = geom["width"]
        scale_height = styles.GAME_MODE_SCALE_HEIGHT_PX

        scale_y = geom["y"]
        scale_bottom_y = scale_y + scale_height

        if time_range <= 0:
            return

        scale_factor = scale_width / time_range

        font_size_px = int(styles.GAME_MODE_FONT_SIZE_PT * (self.dpi / 72))
        try:
            font = ImageFont.truetype("arial.ttf", font_size_px)
        except OSError:
            try:
                font = ImageFont.truetype("tahoma.ttf", font_size_px)
            except OSError:
                font = ImageFont.load_default()

        game_modes = self._get_filtered_game_modes(
            report_data, time_range, period_abs_start, is_match_level
        )

        EDGE_MARGIN = 10
        TEXT_PADDING = 2

        for gm in game_modes:
            local_start = gm['local_start']
            local_end = gm['local_end']
            mode_name = gm['name']

            x_start = scale_x + int(local_start * scale_factor)
            x_end = scale_x + int(local_end * scale_factor)

            if x_end <= x_start:
                x_end = x_start + 1

            interval_width = x_end - x_start

            text_bbox = draw.textbbox((0, 0), mode_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            if text_width <= interval_width - 2 * TEXT_PADDING:
                text_x = x_start + (interval_width - text_width) // 2
                text_y = scale_y + (scale_height - text_height) // 2 - 2
                draw.text((text_x, text_y), mode_name, fill=styles.GAME_MODE_TEXT_COLOR, font=font)
            else:
                text_y = scale_bottom_y + 2

                is_left_edge = (x_start < scale_x + EDGE_MARGIN)
                is_right_edge = (x_end > scale_x + scale_width - EDGE_MARGIN)

                if is_left_edge:
                    text_x = x_start + TEXT_PADDING
                elif is_right_edge:
                    text_x = x_end - text_width - TEXT_PADDING
                else:
                    text_x = x_start + (interval_width - text_width) // 2

                draw.text((text_x, text_y), mode_name, fill=styles.GAME_MODE_TEXT_COLOR, font=font)

    def _get_filtered_game_modes(self, report_data: ReportData, time_range: float,
                                period_abs_start: float, is_match_level: bool) -> list:
        """Фильтрует game_modes."""
        result = []
        
        raw_modes = getattr(report_data.original_project.match, 'calculated_ranges', [])
        game_modes = [cr for cr in raw_modes if getattr(cr, 'label_type', '') == 'game_mode']
        
        if not game_modes:
            return result
        
        game_modes.sort(key=lambda x: x.start_time)
        
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
            
            if not is_match_level:
                period_end = period_abs_start + time_range
                if official_end <= period_abs_start or official_start >= period_end:
                    continue
                
                display_start = max(official_start, period_abs_start)
                display_end = min(official_end, period_end)
            else:
                display_start = official_start
                display_end = official_end
            
            local_start = display_start - period_abs_start
            local_end = display_end - period_abs_start
            
            local_start = max(0, local_start)
            local_end = min(time_range, local_end)
            
            if local_end > local_start:
                result.append({
                    'local_start': local_start,
                    'local_end': local_end,
                    'name': getattr(gm, 'name', '5 на 5')
                })
        
        return result

    def _draw_game_mode_overlays(self, draw: ImageDraw, report_data: ReportData,
                                geom: dict, time_range: float,
                                is_match_level: bool, period_abs_start: float = 0):
        """Полупрозрачные наложения для неравных составов."""
        styles = self.styles
        
        scale_x = geom["x"]
        scale_width = geom["width"]
        
        overlay_top = geom["y"]
        
        time_scale_height = styles.TIME_SCALE_HEIGHT_PX
        graphic_bottom = geom["y"] + geom["height"]
        overlay_bottom = graphic_bottom + time_scale_height
        
        if overlay_bottom <= overlay_top:
            return
        
        if time_range <= 0:
            return
        
        scale_factor = scale_width / time_range
        
        game_modes = self._get_filtered_game_modes(
            report_data, time_range, period_abs_start, is_match_level
        )
        
        if not game_modes:
            return
        
        for gm in game_modes:
            mode_name = gm.get('name', '5 на 5')
            
            if mode_name == "5 на 5":
                continue
            
            try:
                parts = mode_name.split(' на ')
                if len(parts) != 2:
                    continue
                f_team_count = int(parts[0])
                s_team_count = int(parts[1])
            except (ValueError, IndexError):
                continue
            
            if report_data.our_team_key == "f-team":
                our_count = f_team_count
                their_count = s_team_count
            else:
                our_count = s_team_count
                their_count = f_team_count
            
            color_hex = self._get_game_mode_overlay_color(our_count, their_count, styles)
            
            if color_hex is None:
                continue
            
            local_start = gm['local_start']
            local_end = gm['local_end']
            
            x_start = scale_x + int(local_start * scale_factor)
            x_end = scale_x + int(local_end * scale_factor)
            
            if x_end <= x_start:
                x_end = x_start + 1
            
            color_rgba = self._hex_to_rgba(color_hex, styles.GAME_MODE_OVERLAY_ALPHA)
            
            temp_img = Image.new('RGBA', (self.width_px, self.height_px), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.rectangle(
                [x_start, overlay_top, x_end, overlay_bottom],
                fill=color_rgba
            )
            
            draw._image.paste(temp_img, (0, 0), temp_img)

    def _get_game_mode_overlay_color(self, our_count: int, their_count: int, 
                                     styles: ReportStyles) -> Optional[str]:
        """Возвращает цвет для game_mode."""
        if our_count == their_count:
            if our_count == 4:
                return styles.COLOR_GM_EVEN_4ON4 if hasattr(styles, 'COLOR_GM_EVEN_4ON4') else "#DDA0DD"
            elif our_count == 3:
                return styles.COLOR_GM_EVEN_3ON3 if hasattr(styles, 'COLOR_GM_EVEN_3ON3') else "#9370DB"
            else:
                return None
        
        diff = our_count - their_count
        
        if diff > 0:
            if diff == 1:
                return styles.COLOR_GM_POWERPLAY_LIGHT if hasattr(styles, 'COLOR_GM_POWERPLAY_LIGHT') else "#90EE90"
            else:
                return styles.COLOR_GM_POWERPLAY_STRONG if hasattr(styles, 'COLOR_GM_POWERPLAY_STRONG') else "#228B22"
        else:
            if diff == -1:
                return styles.COLOR_GM_PENALTY_KILL_LIGHT if hasattr(styles, 'COLOR_GM_PENALTY_KILL_LIGHT') else "#FFE4B5"
            else:
                return styles.COLOR_GM_PENALTY_KILL_STRONG if hasattr(styles, 'COLOR_GM_PENALTY_KILL_STRONG') else "#FFA500"

    def _hex_to_rgba(self, hex_color: str, alpha: int) -> Tuple[int, int, int, int]:
        """Конвертирует hex в RGBA."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b, alpha)

    def _draw_penalties(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                        time_range: float, period_start: float):
        """Удаления игроков."""
        styles = self.styles
        
        graphic_width = geom["width"]
        graphic_x = geom["x"]
        graphic_y = geom["content_y"]
        
        if time_range <= 0:
            return
        
        scale_factor = graphic_width / time_range
        
        # Получаем row_height из геометрии таблицы
        # Для этого используем кэш или пересчитываем
        # Здесь упрощённый вариант — берём из расчёта
        row_height = self._calculate_table_geometry_v2(
            report_data, 
            TABLE_CONFIG_MATCH if self.mode == 'game_on_sheet' else TABLE_CONFIG_PERIOD
        )["row_height"]
        
        player_index_by_id = {
            player.player_id: idx 
            for idx, player in enumerate(report_data.players_list)
        }
        
        for penalty in report_data.penalties:
            if penalty.official_end <= period_start or penalty.official_start >= period_start + time_range:
                continue
            
            player_idx = player_index_by_id.get(penalty.player_id_fhm)
            if player_idx is None:
                continue
            
            local_start = max(penalty.official_start - period_start, 0)
            local_end = min(penalty.official_end - period_start, time_range)
            
            x_start = graphic_x + int(local_start * scale_factor)
            x_end = graphic_x + int(local_end * scale_factor)
            
            if x_end <= x_start:
                x_end = x_start + 2
            
            y_top = graphic_y + player_idx * row_height
            y_bottom = y_top + row_height
            
            draw.rectangle(
                [x_start, y_top, x_end, y_bottom],
                outline=styles.COLOR_PENALTY_BOX,
                width=styles.PENALTY_LINE_WIDTH
            )
            
            draw.line(
                [(x_start, y_top), (x_end, y_bottom)],
                fill=styles.COLOR_PENALTY_BOX,
                width=styles.PENALTY_LINE_WIDTH
            )
            draw.line(
                [(x_end, y_top), (x_start, y_bottom)],
                fill=styles.COLOR_PENALTY_BOX,
                width=styles.PENALTY_LINE_WIDTH
            )

    def _draw_faceoffs_scale(self, draw: ImageDraw, report_data: ReportData, geom: dict,
                            time_range: float, period_start: float):
        """Шкала вбрасываний."""
        styles = self.styles
        
        SCALE_HEIGHT = styles.FACEOFF_SCALE_HEIGHT_PX
        PEG_WIDTH = styles.FACEOFF_PEG_WIDTH
        BASE_WIDTH = styles.FACEOFF_PEG_BASE_WIDTH
        PEG_COLOR = styles.FACEOFF_PEG_COLOR
        LINE_COLOR = styles.FACEOFF_LINE_COLOR
        
        header_height = geom.get("header_height", 0)
        
        scale_x = geom["x"]
        scale_width = geom["width"]
        
        scale_bottom = geom["content_y"] - styles.TIME_SCALE_HEIGHT_PX
        scale_y = scale_bottom - SCALE_HEIGHT
        
        header_top = geom["content_y"] - header_height
        if scale_y < header_top:
            scale_y = header_top
            SCALE_HEIGHT = scale_bottom - scale_y
        
        if SCALE_HEIGHT > 0:
            draw.rectangle([scale_x, scale_y, scale_x + scale_width, scale_bottom],
                        outline=styles.COLOR_GRID,
                        width=1)
        
        if time_range <= 0 or SCALE_HEIGHT <= 0:
            return

        scale_factor = scale_width / time_range
        
        graphic_bottom = geom["y"] + geom["height"]
        line_bottom_y = graphic_bottom + styles.TIME_SCALE_HEIGHT_PX
        
        for faceoff in report_data.faceoffs:
            if not (period_start <= faceoff.official_time < period_start + time_range):
                continue
            
            local_time = faceoff.official_time - period_start
            x_pos = scale_x + int(local_time * scale_factor)
            
            peg_top = scale_y + 3
            peg_bottom = scale_bottom - 2
            draw.line([(x_pos, peg_top), (x_pos, peg_bottom)], 
                    fill=PEG_COLOR, 
                    width=PEG_WIDTH)
            
            base_y = peg_top
            draw.line([(x_pos - BASE_WIDTH // 2, base_y), 
                    (x_pos + BASE_WIDTH // 2, base_y)], 
                    fill=PEG_COLOR,
                    width=PEG_WIDTH)
            
            self._draw_dashed_line(draw, x_pos, scale_bottom, x_pos, line_bottom_y,
                                LINE_COLOR, styles.FACEOFF_LINE_DASH, 
                                styles.FACEOFF_LINE_WIDTH)