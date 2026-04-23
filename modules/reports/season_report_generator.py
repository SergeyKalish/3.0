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
# ЗОНЫ ЛИСТА
# =============================================================================
HEADER_ZONE_HEIGHT = int(HEIGHT_PX * 0.12)    # 12%
FOOTER_ZONE_HEIGHT = int(HEIGHT_PX * 0.08)    # 8%

HEADER_ZONE_TOP = MARGIN_TOP
HEADER_ZONE_BOTTOM = HEADER_ZONE_TOP + HEADER_ZONE_HEIGHT

FOOTER_ZONE_BOTTOM = HEIGHT_PX - MARGIN_BOTTOM
FOOTER_ZONE_TOP = FOOTER_ZONE_BOTTOM - FOOTER_ZONE_HEIGHT

TABLE_ZONE_TOP = HEADER_ZONE_BOTTOM
TABLE_ZONE_BOTTOM = FOOTER_ZONE_TOP
TABLE_ZONE_HEIGHT = TABLE_ZONE_BOTTOM - TABLE_ZONE_TOP

MAX_TABLE_ROWS = 34 + 1 + 1  # матчи + итог + заголовок
ROW_HEIGHT = TABLE_ZONE_HEIGHT // MAX_TABLE_ROWS

# =============================================================================
# СТИЛИ
# =============================================================================
FONT_FAMILY_PRIMARY = "arial.ttf"
FONT_FAMILY_FALLBACK = "tahoma.ttf"

COLOR_OUR_TEAM = "#1410F3"
COLOR_PHOTO_OUTLINE = "#888888"

HEADER_PHOTO_SIZE_PX = 370
HEADER_NAME_FONT_SIZE_PT = 26
HEADER_INFO_FONT_SIZE_PT = 12
HEADER_INFO_LINE_SPACING_PX = 55

TABLE_FONT_SIZE_PT = 8
TABLE_HEADER_FONT_SIZE_PT = 7
TABLE_MIN_FONT_SIZE_PT = 6
TABLE_CELL_PADDING_X = 4
TABLE_CELL_PADDING_Y = 2
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
_BASE_TABLE_COLUMNS = [
    ("row_num", "№\nп/п", 90, "center"),
    ("tour", "№\nтура", 100, "center"),
    ("logo", "", 90, "center"),
    ("opponent", "Соперник", 440, "left"),
    ("dg", "Д/Г", 80, "center"),
    ("vp", "В/П", 80, "center"),
    ("sm", "СМ", 80, "center"),
    ("srsm", "СрСм", 90, "center"),
    ("vrm", "ВрМ", 120, "center"),
    ("b", "Б", 120, "center"),
    ("m", "М", 120, "center"),
    ("g", "Г", 70, "center"),
    ("p", "П", 70, "center"),
    ("o", "О", 70, "center"),
    ("pm", "+/-", 80, "center"),
    ("sh", "Ш", 80, "center"),
    ("gf", "On-Ice\nGF", 100, "center"),
    ("ga", "On-Ice\nGA", 100, "center"),
    ("total_diff", "Total\n+/-", 100, "center"),
]

_base_total = sum(c[2] for c in _BASE_TABLE_COLUMNS)
_extra = CONTENT_W - _base_total

TABLE_COLUMNS = []
_running_extra = 0
for i, (key, header, w, align) in enumerate(_BASE_TABLE_COLUMNS):
    if i < len(_BASE_TABLE_COLUMNS) - 1:
        add = round(_extra * w / _base_total)
    else:
        add = _extra - _running_extra
    new_w = w + add
    TABLE_COLUMNS.append((key, header, new_w, align))
    _running_extra += add

TABLE_COL_KEYS = [c[0] for c in TABLE_COLUMNS]
TABLE_COL_WIDTHS = [c[2] for c in TABLE_COLUMNS]
TABLE_COL_ALIGNS = [c[3] for c in TABLE_COLUMNS]
TABLE_TOTAL_WIDTH = sum(TABLE_COL_WIDTHS)
TABLE_X = MARGIN_LEFT + (CONTENT_W - TABLE_TOTAL_WIDTH) // 2


# =============================================================================
# ЛЕГЕНДА
# =============================================================================
LEGEND_ITEMS = [
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
    ("Total +/-", "Плюс/минус (любые ситуации)"),
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
        self._draw_header(img, draw, summary, season_name, player_db)

        # === ТАБЛИЦА ===
        self._draw_table(img, draw, summary, TABLE_ZONE_TOP, season_name)

        # === РАЗДЕЛИТЕЛЬНАЯ ЛИНИЯ ===
        draw.line(
            [(CONTENT_X, TABLE_ZONE_BOTTOM), (CONTENT_X + CONTENT_W, TABLE_ZONE_BOTTOM)],
            fill="#000000", width=2
        )

        # === ЛЕГЕНДА ===
        self._draw_legend(draw, FOOTER_ZONE_TOP)

        return img

    def _draw_debug_zones(self, draw: ImageDraw):
        """Временные красные линии для отладки границ зон и полей."""
        red = "#FF0000"
        # Поля (content area)
        draw.rectangle(
            [CONTENT_X, MARGIN_TOP, CONTENT_X + CONTENT_W, HEIGHT_PX - MARGIN_BOTTOM],
            outline=red, width=2
        )
        # Граница шапки
        draw.line([(CONTENT_X, HEADER_ZONE_BOTTOM), (CONTENT_X + CONTENT_W, HEADER_ZONE_BOTTOM)], fill=red, width=2)
        # Граница подвала
        draw.line([(CONTENT_X, FOOTER_ZONE_TOP), (CONTENT_X + CONTENT_W, FOOTER_ZONE_TOP)], fill=red, width=2)
        # Центральная вертикальная линия content area
        draw.line([(CENTER_X, MARGIN_TOP), (CENTER_X, HEIGHT_PX - MARGIN_BOTTOM)], fill=red, width=1)

    # -------------------------------------------------------------------------
    # ШАПКА
    # -------------------------------------------------------------------------
    def _draw_header(self, img: Image.Image, draw: ImageDraw,
                     summary: PlayerSeasonSummary, season_name: str,
                     player_db: Dict[str, dict]):
        db = player_db.get(summary.player_id, {})
        full_name = db.get('name', summary.player_full_name or summary.player_name)

        photo_size = HEADER_PHOTO_SIZE_PX
        photo_x = MARGIN_LEFT + 30
        photo_y = MARGIN_TOP + 30

        photo_path = self._find_photo(summary.player_id, summary.player_number, player_db)
        if photo_path and os.path.exists(photo_path):
            try:
                self._draw_circular_photo(img, photo_path, photo_x, photo_y, photo_size)
            except Exception:
                self._draw_photo_placeholder(draw, photo_x, photo_y, photo_size)
        else:
            self._draw_photo_placeholder(draw, photo_x, photo_y, photo_size)

        # Текстовый блок справа от фото
        text_x = photo_x + photo_size + 40
        text_y = photo_y
        text_max_w = CONTENT_X + CONTENT_W - text_x - 20

        # ФИО
        font_fio = self._get_font(HEADER_NAME_FONT_SIZE_PT, bold=True)
        fio_w, _ = self._measure_text(full_name, HEADER_NAME_FONT_SIZE_PT, bold=True)
        # Фиксированная высота строки на основе метрик шрифта (не зависит от содержимого текста)
        try:
            ascent, descent = font_fio.getmetrics()
            fio_h = ascent + descent
        except Exception:
            _, fio_h = self._measure_text("Ay", HEADER_NAME_FONT_SIZE_PT, bold=True)

        if fio_w <= text_max_w:
            draw.text((text_x, text_y), full_name, fill="#000000", font=font_fio)
            text_y += fio_h + 40
        else:
            parts = full_name.split(' ', 1)
            surname = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            draw.text((text_x, text_y), surname, fill="#000000", font=font_fio)
            if rest:
                draw.text((text_x, text_y + fio_h + 5), rest, fill="#000000", font=font_fio)
            text_y += fio_h * 2 + 15 + 40

        font_info = self._get_font(HEADER_INFO_FONT_SIZE_PT)
        line_h = HEADER_INFO_LINE_SPACING_PX

        bd = db.get('birthdate', '')
        if bd:
            try:
                parts = bd.split('-')
                bd = f"{parts[2]}.{parts[1]}.{parts[0]}"
            except Exception:
                pass

        lines = [
            f"Дата рождения: {bd or '—'}",
            f"Команда: «Созвездие 2014» | Игровой номер: {summary.player_number}",
            f"Амплуа: {summary.player_role}",
            f"Рост: {db.get('height', '—')} см | Вес: {db.get('weight', '—')} кг | Хват: {db.get('hand', '—') or '—'}",
        ]

        for line in lines:
            draw.text((text_x, text_y), line, fill="#000000", font=font_info)
            text_y += line_h

    def _draw_circular_photo(self, img: Image.Image, photo_path: str, x: int, y: int, size: int):
        photo = Image.open(photo_path).resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new('L', (size, size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, size, size), fill=255)
        photo_rgba = photo.convert('RGBA')
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(photo_rgba, (0, 0), mask)
        img.paste(output, (x, y), output)
        # Синий контур
        draw = ImageDraw.Draw(img)
        draw.ellipse([x, y, x + size, y + size], outline=COLOR_PHOTO_OUTLINE, width=5)

    def _draw_photo_placeholder(self, draw: ImageDraw, x: int, y: int, size: int):
        draw.ellipse([x, y, x + size, y + size], outline=COLOR_PHOTO_OUTLINE, width=5)
        # Внутренний серый кружок
        inner_margin = 20
        draw.ellipse([x + inner_margin, y + inner_margin,
                      x + size - inner_margin, y + size - inner_margin],
                     outline="#CCCCCC", width=2)

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
                    summary: PlayerSeasonSummary, table_zone_top: int, season_name: str):
        TOURNAMENT_NAME_HEIGHT = 50

        # --- НАЗВАНИЕ ТУРНИРА ---
        font_tournament = self._get_font(LEGEND_TITLE_FONT_SIZE_PT, bold=True)
        tw, th = self._measure_text(season_name, LEGEND_TITLE_FONT_SIZE_PT, bold=True)
        tx = TABLE_X + (TABLE_TOTAL_WIDTH - tw) // 2
        ty = table_zone_top + 10
        draw.text((tx, ty), season_name, fill="#000000", font=font_tournament)

        table_top = ty + th + 20
        num_matches = len(summary.matches)
        # Динамический расчёт высоты строки: при большом количестве матчей уменьшаем,
        # при малом — оставляем стандартную ROW_HEIGHT
        available_height = TABLE_ZONE_BOTTOM - table_top
        row_height = min(ROW_HEIGHT, available_height // (num_matches + 2))
        header_height = row_height

        x_offsets = []
        cx = TABLE_X
        for w in TABLE_COL_WIDTHS:
            x_offsets.append(cx)
            cx += w

        # --- ЗАГОЛОВОК ---
        for i, (key, header_text, width, align) in enumerate(TABLE_COLUMNS):
            if i == 2:
                # Объединённая ячейка для logo + opponent
                merged_width = TABLE_COL_WIDTHS[2] + TABLE_COL_WIDTHS[3]
                self._draw_table_cell(draw, x_offsets[2], table_top, merged_width, header_height,
                                      "Соперник", TABLE_HEADER_FONT_SIZE_PT,
                                      bg=TABLE_HEADER_BG, text_color=TABLE_HEADER_TEXT_COLOR,
                                      align="center", is_header=True)
            elif i == 3:
                continue
            else:
                x = x_offsets[i]
                self._draw_table_cell(draw, x, table_top, width, header_height,
                                      header_text, TABLE_HEADER_FONT_SIZE_PT,
                                      bg=TABLE_HEADER_BG, text_color=TABLE_HEADER_TEXT_COLOR,
                                      align=align, is_header=True)

        # --- СТРОКИ МАТЧЕЙ ---
        for row_idx, match in enumerate(summary.matches):
            y = table_top + header_height + row_idx * row_height
            bg = TABLE_ALTERNATING_ROW_BG if (row_idx % 2 == 1) else "#FFFFFF"
            self._draw_match_row(img, draw, match, row_idx, x_offsets, y, row_height, bg)

        # --- ИТОГОВАЯ СТРОКА ---
        total_y = table_top + header_height + num_matches * row_height
        self._draw_totals_row(draw, summary, x_offsets, total_y, row_height)

        # --- ВНЕШНЯЯ РАМКА ---
        table_height = header_height + (num_matches + 1) * row_height
        draw.rectangle([TABLE_X, table_top, TABLE_X + TABLE_TOTAL_WIDTH, table_top + table_height],
                       outline=TABLE_OUTLINE_COLOR, width=2)

    def _draw_match_row(self, img: Image.Image, draw: ImageDraw, match: SeasonMatchRow,
                        row_idx: int, x_offsets: List[int], y: int, h: int, bg: str):
        values = [
            str(row_idx + 1),           # № п/п
            match.tour_number,
            "",                         # logo
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
            self._fmt_pm(match.plus_minus, is_total=False),
            self._fmt_int(match.penalties),
            self._fmt_int(match.on_ice_gf),
            self._fmt_int(match.on_ice_ga),
            self._fmt_pm_total(match.on_ice_diff, is_total=False),
        ]

        for i, val in enumerate(values):
            x = x_offsets[i]
            w = TABLE_COL_WIDTHS[i]
            align = TABLE_COL_ALIGNS[i]

            if TABLE_COLUMNS[i][0] == "logo":
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
            "",                         # № п/п
            "",                         # № тура
            "",                         # logo
            "ИТОГО",                    # Соперник
            "",                         # Д/Г
            f"{wins}/{losses}",
            str(summary.total_shifts()),
            f'{avg_sec}"' if avg_sec else "",
            _fmt_time(summary.total_time_seconds()),
            _fmt_time(summary.total_pp_seconds()),
            _fmt_time(summary.total_pk_seconds()),
            str(summary.total_goals()),
            str(summary.total_assists()),
            str(summary.total_points()),
            self._fmt_pm(summary.total_plus_minus(), is_total=True),
            str(summary.total_penalties()),
            str(summary.total_on_ice_gf()),
            str(summary.total_on_ice_ga()),
            self._fmt_pm_total(summary.total_on_ice_diff(), is_total=True),
        ]

        for i, val in enumerate(values):
            x = x_offsets[i]
            w = TABLE_COL_WIDTHS[i]
            align = TABLE_COL_ALIGNS[i]
            if i == 3:
                align = "right"
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

        lines = str(text).split('\n')
        line_heights = []
        line_widths = []
        for line in lines:
            lw, lh = self._measure_text(line, font_size, bold=bold)
            line_widths.append(lw)
            line_heights.append(lh)

        total_text_h = sum(line_heights) + (len(lines) - 1) * 2
        max_text_w = max(line_widths) if line_widths else 0

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
        draw.rectangle([x, y, x + w, y + h], fill="#FFFFFF", outline=TABLE_GRID_COLOR, width=1)
        if not logo_path or not os.path.exists(logo_path):
            return
        try:
            logo = Image.open(logo_path)
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

    def _fmt_pm(self, val: int, is_total: bool = False) -> str:
        if val == 0:
            return "0" if is_total else ""
        return f"{val:+d}"

    def _fmt_pm_total(self, val: int, is_total: bool = False) -> str:
        if val == 0:
            return "0" if is_total else ""
        return f"{val:+d}"

    # -------------------------------------------------------------------------
    # ЛЕГЕНДА
    # -------------------------------------------------------------------------
    def _draw_legend(self, draw: ImageDraw, footer_zone_top: int):
        font_title = self._get_font(LEGEND_TITLE_FONT_SIZE_PT, bold=True)
        font_text = self._get_font(LEGEND_FONT_SIZE_PT)

        y = footer_zone_top + 10

        title = "Обозначения таблицы:"
        tw, th = self._measure_text(title, LEGEND_TITLE_FONT_SIZE_PT, bold=True)
        draw.text((CONTENT_X, y), title, fill="#000000", font=font_title)
        y += th + 10

        avail_w = CONTENT_W - 40
        col1_w = int(avail_w * 0.28)
        col2_w = int(avail_w * 0.28)
        col3_w = avail_w - col1_w - col2_w
        col_xs = [CONTENT_X, CONTENT_X + col1_w + 20, CONTENT_X + col1_w + 20 + col2_w + 20]
        col_ws = [col1_w, col2_w, col3_w]
        row_h = 40

        for col_idx in range(3):
            cy = y
            start_idx = col_idx * 5
            end_idx = start_idx + 5
            for item_idx in range(start_idx, end_idx):
                abbr, desc = LEGEND_ITEMS[item_idx]
                abbr_text = f"{abbr}:"

                ix = col_xs[col_idx]
                draw.text((ix, cy), abbr_text, fill="#1640F8", font=font_text)
                abbr_w, _ = self._measure_text(abbr_text, LEGEND_FONT_SIZE_PT)
                draw.text((ix + abbr_w + 5, cy), desc, fill="#333333", font=font_text)
                cy += row_h
