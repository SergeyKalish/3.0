"""
Генератор PNG для Отчёта №2 «Сводная статистика игрока».
Формат: А4, портрет, 300 DPI.
"""
import os
from typing import List, Tuple, Dict
from PIL import Image, ImageDraw, ImageFont
from modules.reports.season_report_data import PlayerSeasonSummary, SeasonMatchRow


# =============================================================================
# КОНСТАНТЫ ЛИСТА
# =============================================================================
DPI = 300


def mm_to_px(mm: float) -> int:
    return int((mm / 25.4) * DPI)


WIDTH_PX = mm_to_px(210)
HEIGHT_PX = mm_to_px(297)

MARGIN_TOP = 80
MARGIN_BOTTOM = 80
MARGIN_LEFT = 80
MARGIN_RIGHT = 80

CONTENT_X = MARGIN_LEFT
CONTENT_W = WIDTH_PX - MARGIN_LEFT - MARGIN_RIGHT
CENTER_X = WIDTH_PX // 2

# =============================================================================
# СТИЛИ
# =============================================================================
FONT_FAMILY_PRIMARY = "arial.ttf"
FONT_FAMILY_FALLBACK = "tahoma.ttf"

HEADER_PHOTO_SIZE_PX = 320
HEADER_NAME_FONT_SIZE_PT = 26
HEADER_INFO_FONT_SIZE_PT = 11
HEADER_INFO_LINE_SPACING_PX = 26

TABLE_FONT_SIZE_PT = 8
TABLE_HEADER_FONT_SIZE_PT = 7
TABLE_MIN_FONT_SIZE_PT = 6
TABLE_CELL_PADDING_X = 4
TABLE_CELL_PADDING_Y = 2
TABLE_HEADER_HEIGHT_RATIO = 1.5
TABLE_GRID_COLOR = "#9B9B9B"
TABLE_OUTLINE_COLOR = "#000000"
TABLE_HEADER_BG = "#EEEEEE"
TABLE_ALTERNATING_ROW_BG = "#E6E8EB"
TABLE_TEXT_COLOR = "#000000"
TABLE_HEADER_TEXT_COLOR = "#0241FF"

TOTAL_ROW_BG = "#D0D0D0"

LEGEND_FONT_SIZE_PT = 8
LEGEND_TITLE_FONT_SIZE_PT = 10

TABLE_HIDE_ZERO_VALUES = True


# =============================================================================
# КОЛОНКИ ТАБЛИЦЫ
# =============================================================================
# (key, header_text, width_px, align)
TABLE_COLUMNS = [
    ("tour", "№ тура", 110, "center"),
    ("logo", "", 100, "center"),
    ("opponent", "Соперник", 480, "left"),
    ("dg", "Д/Г", 90, "center"),
    ("vp", "В/П", 90, "center"),
    ("sm", "СМ", 90, "center"),
    ("srsm", "СрСм", 100, "center"),
    ("vrm", "ВрМ", 110, "center"),
    ("b", "Б", 100, "center"),
    ("m", "М", 100, "center"),
    ("g", "Г", 80, "center"),
    ("p", "П", 80, "center"),
    ("o", "О", 80, "center"),
    ("pm", "+/-", 90, "center"),
    ("sh", "Ш", 90, "center"),
    ("gf", "On-Ice\nGF", 110, "center"),
    ("ga", "On-Ice\nGA", 110, "center"),
]

TABLE_COL_KEYS = [c[0] for c in TABLE_COLUMNS]
TABLE_COL_WIDTHS = [c[2] for c in TABLE_COLUMNS]
TABLE_COL_ALIGNS = [c[3] for c in TABLE_COLUMNS]
TABLE_TOTAL_WIDTH = sum(TABLE_COL_WIDTHS)
TABLE_X = MARGIN_LEFT + (CONTENT_W - TABLE_TOTAL_WIDTH) // 2


# =============================================================================
# ЛЕГЕНДА
# =============================================================================
LEGEND_ITEMS = [
    ("№ тура", "Номер тура"),
    ("Соперник", "Название команды соперника"),
    ("Д/Г", "Домашняя / Гостевая игра"),
    ("В/П", "Победа / Поражение"),
    ("СМ", "Количество смен в матче"),
    ("СрСм", "Среднее время смены (сек)"),
    ("ВрМ", "Время на льду в матче (ММ:СС)"),
    ("Б", "Время в большинстве (ММ:СС)"),
    ("М", "Время в меньшинстве (ММ:СС)"),
    ("Г", "Голы"),
    ("П", "Передачи"),
    ("О", "Очки (Г + П)"),
    ("+/-", "Плюс/минус (равные составы)"),
    ("Ш", "Штрафные минуты"),
    ("On-Ice GF", "Голы команды на льду (любые ситуации)"),
    ("On-Ice GA", "Голы соперника на льду (любые ситуации)"),
]


# =============================================================================
# ГЕНЕРАТОР
# =============================================================================
class PlayerSeasonReportGenerator:
    def __init__(self):
        self._font_cache: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}

    def _get_font(self, size_pt: float, bold: bool = False) -> ImageFont.FreeTypeFont:
        cache_key = (round(size_pt * 10), bold)
        if cache_key not in self._font_cache:
            size_px = int(size_pt * (DPI / 72))
            font = None
            for family in [FONT_FAMILY_PRIMARY, FONT_FAMILY_FALLBACK]:
                try:
                    font = ImageFont.truetype(family, size_px)
                    break
                except OSError:
                    continue
            if font is None:
                font = ImageFont.load_default()
            self._font_cache[cache_key] = font
        return self._font_cache[cache_key]

    def _measure_text(self, text: str, size_pt: float, bold: bool = False) -> Tuple[int, int]:
        if not text:
            return 0, 0
        font = self._get_font(size_pt, bold)
        tmp = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(tmp)
        bbox = draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # -------------------------------------------------------------------------
    # ПУБЛИЧНЫЙ МЕТОД
    # -------------------------------------------------------------------------
    def generate(self, summary: PlayerSeasonSummary, season_name: str,
                 player_db: Dict[str, dict]) -> Image.Image:
        img = Image.new("RGB", (WIDTH_PX, HEIGHT_PX), "#FFFFFF")
        draw = ImageDraw.Draw(img)

        # === ШАПКА ===
        header_bottom = self._draw_header(img, draw, summary, season_name, player_db)

        # === ТАБЛИЦА ===
        table_bottom = self._draw_table(img, draw, summary, header_bottom)

        # === ЛЕГЕНДА ===
        self._draw_legend(draw, table_bottom)

        return img

    # -------------------------------------------------------------------------
    # ШАПКА
    # -------------------------------------------------------------------------
    def _draw_header(self, img: Image.Image, draw: ImageDraw,
                     summary: PlayerSeasonSummary, season_name: str,
                     player_db: Dict[str, dict]) -> int:
        current_y = MARGIN_TOP

        # --- ФОТО ---
        photo_path = self._find_photo(summary.player_id, summary.player_number, player_db)
        photo_x = CENTER_X - HEADER_PHOTO_SIZE_PX // 2
        if photo_path and os.path.exists(photo_path):
            try:
                photo = Image.open(photo_path)
                photo = photo.resize((HEADER_PHOTO_SIZE_PX, HEADER_PHOTO_SIZE_PX), Image.Resampling.LANCZOS)
                if photo.mode == 'RGBA':
                    img.paste(photo, (photo_x, current_y), photo)
                else:
                    img.paste(photo, (photo_x, current_y))
            except Exception:
                self._draw_photo_placeholder(draw, photo_x, current_y)
        else:
            self._draw_photo_placeholder(draw, photo_x, current_y)

        current_y += HEADER_PHOTO_SIZE_PX + 15

        # --- ФИО ---
        name_text = summary.player_full_name or summary.player_name
        font_name = self._get_font(HEADER_NAME_FONT_SIZE_PT, bold=True)
        tw, th = self._measure_text(name_text, HEADER_NAME_FONT_SIZE_PT, bold=True)
        draw.text((CENTER_X - tw // 2, current_y), name_text, fill="#000000", font=font_name)
        current_y += th + 20

        # --- ИНФО-БЛОК (две колонки) ---
        db = player_db.get(summary.player_id, {})
        bd = db.get('birthdate', '')
        if bd:
            try:
                parts = bd.split('-')
                bd = f"{parts[2]}.{parts[1]}.{parts[0]}"
            except Exception:
                pass

        left_lines = ["Команда: Созвездие 2014"]
        right_lines = [
            f"Рост: {db.get('height', '—')} см",
            f"Вес: {db.get('weight', '—')} кг",
            f"Хват: {db.get('hand', '—') or '—'}",
            f"Дата рождения: {bd or '—'}",
        ]

        font_info = self._get_font(HEADER_INFO_FONT_SIZE_PT)
        col_w = 500
        gap = 40
        block_w = col_w * 2 + gap
        left_x = CENTER_X - block_w // 2
        right_x = left_x + col_w + gap

        for i, line in enumerate(left_lines):
            draw.text((left_x, current_y + i * HEADER_INFO_LINE_SPACING_PX), line, fill="#000000", font=font_info)
        for i, line in enumerate(right_lines):
            draw.text((right_x, current_y + i * HEADER_INFO_LINE_SPACING_PX), line, fill="#000000", font=font_info)

        current_y += max(len(left_lines), len(right_lines)) * HEADER_INFO_LINE_SPACING_PX + 15

        # --- СЕЗОН (отдельная строка по центру, с уменьшением шрифта при необходимости) ---
        season_text = f"Сезон: {season_name}"
        season_font_size = HEADER_INFO_FONT_SIZE_PT
        min_font = 8.0
        while season_font_size >= min_font:
            stw, sth = self._measure_text(season_text, season_font_size)
            if stw <= CONTENT_W:
                break
            season_font_size -= 0.5
        season_font = self._get_font(season_font_size)
        draw.text((CENTER_X - int(stw) // 2, current_y), season_text, fill="#555555", font=season_font)
        current_y += int(sth) + 20

        return current_y

    def _draw_photo_placeholder(self, draw: ImageDraw, x: int, y: int):
        draw.rectangle([x, y, x + HEADER_PHOTO_SIZE_PX, y + HEADER_PHOTO_SIZE_PX],
                       outline="#AAAAAA", width=2)
        # Крест-накрест
        draw.line([(x, y), (x + HEADER_PHOTO_SIZE_PX, y + HEADER_PHOTO_SIZE_PX)],
                  fill="#CCCCCC", width=2)
        draw.line([(x + HEADER_PHOTO_SIZE_PX, y), (x, y + HEADER_PHOTO_SIZE_PX)],
                  fill="#CCCCCC", width=2)

    def _find_photo(self, player_id: str, number: str, player_db: Dict[str, dict]) -> str:
        photo_dir = os.path.join('Data', 'player_photos')
        if not os.path.isdir(photo_dir):
            return ""
        entry = player_db.get(player_id)
        if entry:
            parts = entry.get('name', '').split()
            if len(parts) >= 2:
                expected = f"{player_id}-{parts[0]}-{parts[1]}-№{number}.jpg"
                path = os.path.join(photo_dir, expected)
                if os.path.exists(path):
                    return path
        import glob as glob_mod
        pattern = os.path.join(photo_dir, f"{player_id}-*-№{number}.jpg")
        matches = glob_mod.glob(pattern)
        return matches[0] if matches else ""

    # -------------------------------------------------------------------------
    # ТАБЛИЦА
    # -------------------------------------------------------------------------
    def _draw_table(self, img: Image.Image, draw: ImageDraw,
                    summary: PlayerSeasonSummary, start_y: int) -> int:
        num_matches = len(summary.matches)
        total_data_rows = num_matches + 1  # +1 итоговая строка

        # Динамический расчёт высоты строк
        space_after_header = HEIGHT_PX - start_y - MARGIN_BOTTOM
        legend_height = int(space_after_header * 0.22)
        available_table_height = space_after_header - legend_height - 20  # 20 px зазор

        header_height = int(40 * TABLE_HEADER_HEIGHT_RATIO)
        row_height = (available_table_height - header_height) // max(total_data_rows, 1)
        if row_height < 28:
            row_height = 28

        table_height = header_height + row_height * total_data_rows
        table_y = start_y

        x_offsets = []
        cx = TABLE_X
        for w in TABLE_COL_WIDTHS:
            x_offsets.append(cx)
            cx += w

        # --- ЗАГОЛОВОК ---
        for i, (key, header_text, width, align) in enumerate(TABLE_COLUMNS):
            x = x_offsets[i]
            self._draw_table_cell(draw, x, table_y, width, header_height,
                                  header_text, TABLE_HEADER_FONT_SIZE_PT,
                                  bg=TABLE_HEADER_BG, text_color=TABLE_HEADER_TEXT_COLOR,
                                  align=align, is_header=True)

        # --- СТРОКИ МАТЧЕЙ ---
        for row_idx, match in enumerate(summary.matches):
            y = table_y + header_height + row_idx * row_height
            bg = TABLE_ALTERNATING_ROW_BG if (row_idx % 2 == 1) else "#FFFFFF"
            self._draw_match_row(img, draw, match, x_offsets, y, row_height, bg)

        # --- ИТОГОВАЯ СТРОКА ---
        total_y = table_y + header_height + num_matches * row_height
        self._draw_totals_row(draw, summary, x_offsets, total_y, row_height)

        # --- ВНЕШНЯЯ РАМКА ---
        draw.rectangle([TABLE_X, table_y, TABLE_X + TABLE_TOTAL_WIDTH, table_y + table_height],
                       outline=TABLE_OUTLINE_COLOR, width=2)

        return total_y + row_height + 10

    def _draw_match_row(self, img: Image.Image, draw: ImageDraw, match: SeasonMatchRow,
                        x_offsets: List[int], y: int, h: int, bg: str):
        values = [
            match.tour_number,
            "",  # logo — рисуем отдельно
            match.opponent_name,
            match.home_away,
            match.result,
            self._fmt_int(match.shifts_count),
            match.avg_shift,
            match.total_time,
            match.powerplay,
            match.penalty_kill,
            self._fmt_int(match.goals),
            self._fmt_int(match.assists),
            self._fmt_int(match.points),
            self._fmt_pm(match.plus_minus),
            self._fmt_int(match.penalties),
            self._fmt_int(match.on_ice_gf),
            self._fmt_int(match.on_ice_ga),
        ]

        for i, val in enumerate(values):
            x = x_offsets[i]
            w = TABLE_COL_WIDTHS[i]
            align = TABLE_COL_ALIGNS[i]

            if TABLE_COLUMNS[i][0] == "logo":
                # Рисуем логотип соперника
                self._draw_opponent_logo(img, draw, match.opponent_logo_path, x, y, w, h)
            else:
                self._draw_table_cell(draw, x, y, w, h, val, TABLE_FONT_SIZE_PT,
                                      bg=bg, align=align)

    def _draw_totals_row(self, draw: ImageDraw, summary: PlayerSeasonSummary,
                         x_offsets: List[int], y: int, h: int):
        def _fmt_time(sec: int) -> str:
            return f"{sec // 60}:{sec % 60:02d}"

        wins = summary.total_wins()
        losses = summary.total_losses()
        avg_sec = summary.avg_shift_seconds()

        values = [
            "ИТОГО",
            "",
            "",
            "",
            f"{wins}/{losses}",
            str(summary.total_shifts()),
            f'{avg_sec}"',
            _fmt_time(summary.total_time_seconds()),
            _fmt_time(summary.total_pp_seconds()),
            _fmt_time(summary.total_pk_seconds()),
            str(summary.total_goals()),
            str(summary.total_assists()),
            str(summary.total_points()),
            self._fmt_pm(summary.total_plus_minus()),
            str(summary.total_penalties()),
            str(summary.total_on_ice_gf()),
            str(summary.total_on_ice_ga()),
        ]

        for i, val in enumerate(values):
            x = x_offsets[i]
            w = TABLE_COL_WIDTHS[i]
            align = TABLE_COL_ALIGNS[i]
            self._draw_table_cell(draw, x, y, w, h, val, TABLE_FONT_SIZE_PT,
                                  bg=TOTAL_ROW_BG, align=align, bold=True)

    def _draw_table_cell(self, draw: ImageDraw, x: int, y: int, w: int, h: int,
                         text: str, font_size: float, bg: str = "#FFFFFF",
                         text_color: str = TABLE_TEXT_COLOR, align: str = "left",
                         is_header: bool = False, bold: bool = False):
        # Фон
        draw.rectangle([x, y, x + w, y + h], fill=bg, outline=TABLE_GRID_COLOR, width=1)

        if not text:
            return

        font = self._get_font(font_size, bold=bold)

        # Для многострочного текста (заголовки с \n)
        lines = str(text).split('\n')
        line_heights = []
        line_widths = []
        for line in lines:
            lw, lh = self._measure_text(line, font_size, bold=bold)
            line_widths.append(lw)
            line_heights.append(lh)

        total_text_h = sum(line_heights) + (len(lines) - 1) * 2
        max_text_w = max(line_widths) if line_widths else 0

        # Y: центрируем блок по высоте
        text_y = y + (h - total_text_h) // 2

        for line, lw, lh in zip(lines, line_widths, line_heights):
            if align == "center":
                line_x = x + (w - lw) // 2
            elif align == "right":
                line_x = x + w - lw - TABLE_CELL_PADDING_X
            else:
                line_x = x + TABLE_CELL_PADDING_X
            draw.text((line_x, text_y), line, fill=text_color, font=font)
            text_y += lh + 2

    def _draw_opponent_logo(self, img: Image.Image, draw: ImageDraw, logo_path: str,
                            x: int, y: int, w: int, h: int):
        # Фон ячейки
        draw.rectangle([x, y, x + w, y + h], fill="#FFFFFF", outline=TABLE_GRID_COLOR, width=1)
        if not logo_path or not os.path.exists(logo_path):
            return
        try:
            logo = Image.open(logo_path)
            # Масштабируем с сохранением пропорций, вписываем в ячейку с padding
            max_w = w - 8
            max_h = h - 8
            logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            lw, lh = logo.size
            lx = x + (w - lw) // 2
            ly = y + (h - lh) // 2
            if logo.mode == 'RGBA':
                img.paste(logo, (lx, ly), logo)
            else:
                img.paste(logo, (lx, ly))
        except Exception:
            pass

    def _fmt_int(self, val: int) -> str:
        if TABLE_HIDE_ZERO_VALUES and val == 0:
            return ""
        return str(val)

    def _fmt_pm(self, val: int) -> str:
        if TABLE_HIDE_ZERO_VALUES and val == 0:
            return ""
        return f"{val:+d}"

    # -------------------------------------------------------------------------
    # ЛЕГЕНДА
    # -------------------------------------------------------------------------
    def _draw_legend(self, draw: ImageDraw, start_y: int):
        font_title = self._get_font(LEGEND_TITLE_FONT_SIZE_PT, bold=True)
        font_text = self._get_font(LEGEND_FONT_SIZE_PT)

        title = "Обозначения таблицы:"
        tw, th = self._measure_text(title, LEGEND_TITLE_FONT_SIZE_PT, bold=True)
        draw.text((TABLE_X, start_y), title, fill="#000000", font=font_title)
        y = start_y + th + 10

        # Две колонки
        col_w = (TABLE_TOTAL_WIDTH - 20) // 2
        mid_x = TABLE_X + col_w + 20
        items_per_col = (len(LEGEND_ITEMS) + 1) // 2
        line_h = 28

        for i, (abbr, desc) in enumerate(LEGEND_ITEMS):
            if i < items_per_col:
                ix, iy = TABLE_X, y + i * line_h
            else:
                ix, iy = mid_x, y + (i - items_per_col) * line_h

            abbr_text = f"{abbr}:"
            draw.text((ix, iy), abbr_text, fill="#1640F8", font=font_text)
            abbr_w, _ = self._measure_text(abbr_text, LEGEND_FONT_SIZE_PT)
            draw.text((ix + abbr_w + 5, iy), desc, fill="#333333", font=font_text)
