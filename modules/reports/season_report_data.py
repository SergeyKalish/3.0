"""
Модуль сбора и агрегации данных для Отчёта №2 «Сводная статистика игрока».
"""
import os
import json
import glob
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from model.project import Project
from modules.reports.report_data import ReportData, SORT_BY_EXIT_TIME, OUR_TEAM_NAME
from utils.helpers import load_project_from_file, convert_global_to_official_time


# =============================================================================
# ФИЛЬТР ОКОНЧЕННЫХ МАТЧЕЙ
# =============================================================================

def is_match_completed(project: Project) -> bool:
    """
    Проверяет, является ли матч оконченным.
    Условия:
    1. player_shifts_official_timer существует и не пуст.
    2. Хотя бы у одного игрока нашей команды есть смена,
       пересекающаяся с интервалом официального времени [3420, 3600] сек
       (последние 3 минуты матча при стандарте 3×20 мин).
    """
    psot = project.match.player_shifts_official_timer
    if not psot:
        return False

    teams = project.match.teams
    our_team_key = None
    for key, name in teams.items():
        if name == OUR_TEAM_NAME:
            our_team_key = key
            break
    if not our_team_key:
        return False

    rosters = project.match.rosters.get(our_team_key, [])
    our_player_ids = {p.get('id_fhm') for p in rosters if p.get('id_fhm')}

    for player_id in our_player_ids:
        psi = psot.get(player_id)
        if not psi:
            continue
        for shift in psi.shifts:
            # Смена пересекается с [3420, 3600]?
            if shift.start_time <= 3600.0 and shift.end_time >= 3420.0:
                return True
    return False


# =============================================================================
# РАСЧЁТНЫЕ ФУНКЦИИ (по одному матчу)
# =============================================================================

def calculate_player_goals(report_data: ReportData, player_id: str) -> int:
    """Голы, забитые игроком."""
    return sum(
        1 for goal in report_data.goals
        if goal.context.get('player_id_fhm', '') == player_id
    )


def calculate_player_assists(report_data: ReportData, player_id: str) -> int:
    """Передачи игрока (1-я и 2-я)."""
    assists = 0
    for goal in report_data.goals:
        if goal.context.get('f-pass_id_fhm', '') == player_id:
            assists += 1
        if goal.context.get('s-pass_id_fhm', '') == player_id:
            assists += 1
    return assists


def calculate_player_plus_minus(report_data: ReportData, player_id: str) -> int:
    """+/- только в равных составах."""
    plus_minus = 0
    shifts = report_data.shifts_by_player_id.get(player_id, [])
    if not shifts:
        return 0

    raw_modes = getattr(report_data.original_project.match, 'calculated_ranges', [])
    game_modes = [cr for cr in raw_modes if getattr(cr, 'label_type', '') == 'game_mode']

    def _is_even(mode_name: str) -> bool:
        if ' на ' not in mode_name:
            return False
        try:
            parts = mode_name.split(' на ')
            return int(parts[0].strip()) == int(parts[1].strip())
        except (ValueError, IndexError):
            return False

    for goal in report_data.goals:
        goal_time = goal.official_time
        even = False
        for gm in game_modes:
            try:
                o_start = convert_global_to_official_time(
                    gm.start_time, report_data.original_project.match.calculated_ranges
                )
                o_end = convert_global_to_official_time(
                    gm.end_time, report_data.original_project.match.calculated_ranges
                )
            except Exception:
                continue
            if o_start is None or o_end is None:
                continue
            if o_start < goal_time <= o_end:
                even = _is_even(getattr(gm, 'name', '5 на 5'))
                break

        if not even:
            continue

        on_ice = any(
            shift.official_start < goal.official_time <= shift.official_end
            for shift in shifts
        )
        if on_ice:
            team = goal.context.get('team', '')
            plus_minus += 1 if team == report_data.our_team_key else -1

    return plus_minus


def calculate_player_penalties(report_data: ReportData, player_id: str) -> int:
    """Штрафные минуты игрока."""
    minutes = 0
    for penalty in report_data.penalties:
        if penalty.player_id_fhm != player_id:
            continue
        vtype = (penalty.violation_type or "").lower()
        if "двойной малый" in vtype or "двойное удаление" in vtype:
            minutes += 4
        elif "крупное" in vtype or "матч" in vtype:
            minutes += 5
        elif "удаление" in vtype or "10" in vtype:
            minutes += 10
        elif "игрушечный" in vtype or "лишение" in vtype:
            minutes += 0
        else:
            minutes += 2
    return minutes


def calculate_special_team_time(report_data: ReportData, player_id: str, key: str) -> int:
    """Время в большинстве ('powerplay') или меньшинстве ('penalty_kill') в секундах."""
    shifts = report_data.shifts_by_player_id.get(player_id, [])
    if not shifts:
        return 0

    raw_modes = getattr(report_data.original_project.match, 'calculated_ranges', [])
    game_modes = [cr for cr in raw_modes if getattr(cr, 'label_type', '') == 'game_mode']
    if not game_modes:
        return 0

    our_team_key = report_data.our_team_key

    def _is_special(mode_name: str, mode_type: str) -> bool:
        if ' на ' not in mode_name:
            return False
        try:
            parts = mode_name.split(' на ')
            f_cnt = int(parts[0].strip())
            s_cnt = int(parts[1].strip())
        except (ValueError, IndexError):
            return False
        our_cnt = f_cnt if our_team_key == 'f-team' else s_cnt
        their_cnt = s_cnt if our_team_key == 'f-team' else f_cnt
        if mode_type == 'powerplay':
            return our_cnt > their_cnt
        return our_cnt < their_cnt

    intervals = []
    for gm in game_modes:
        name = getattr(gm, 'name', '5 на 5')
        if not _is_special(name, key):
            continue
        try:
            o_s = convert_global_to_official_time(
                gm.start_time, report_data.original_project.match.calculated_ranges
            )
            o_e = convert_global_to_official_time(
                gm.end_time, report_data.original_project.match.calculated_ranges
            )
        except Exception:
            continue
        if o_s is None or o_e is None:
            continue
        intervals.append((o_s, o_e))

    total = 0
    for shift in shifts:
        for i_s, i_e in intervals:
            s = max(shift.official_start, i_s)
            e = min(shift.official_end, i_e)
            if e > s:
                total += int(e - s)
    return total


def calculate_on_ice_gf_ga(report_data: ReportData, player_id: str) -> Tuple[int, int]:
    """On-Ice Goals For / Against — все голы при нахождении на льду, любые составы."""
    gf = ga = 0
    shifts = report_data.shifts_by_player_id.get(player_id, [])
    if not shifts:
        return 0, 0

    for goal in report_data.goals:
        gt = goal.official_time
        on_ice = any(shift.official_start < gt <= shift.official_end for shift in shifts)
        if on_ice:
            if goal.context.get('team', '') == report_data.our_team_key:
                gf += 1
            else:
                ga += 1
    return gf, ga


# =============================================================================
# МОДЕЛИ ДАННЫХ
# =============================================================================

@dataclass
class SeasonMatchRow:
    """Одна строка таблицы = один матч для одного игрока."""
    tour_number: str
    opponent_logo_path: str
    opponent_name: str
    home_away: str          # "Д" / "Г"
    result: str             # "В" / "П"
    shifts_count: int
    avg_shift: str          # '45"'
    total_time: str         # '12:34'
    powerplay: str          # '1:23'
    penalty_kill: str       # '0:45'
    goals: int
    assists: int
    points: int
    plus_minus: int
    penalties: int
    on_ice_gf: int
    on_ice_ga: int


@dataclass
class PlayerSeasonSummary:
    """Сводка по игроку за сезон."""
    player_id: str
    player_number: str
    player_name: str          # "Арнаут И." (короткое)
    player_full_name: str     # "Арнаут Иван" (из rosters)
    player_role: str
    matches: List[SeasonMatchRow] = field(default_factory=list)

    # ---------- агрегаты ----------
    def total_wins(self) -> int:
        return sum(1 for m in self.matches if m.result == 'В')

    def total_losses(self) -> int:
        return sum(1 for m in self.matches if m.result == 'П')

    def total_shifts(self) -> int:
        return sum(m.shifts_count for m in self.matches)

    def total_time_seconds(self) -> int:
        total = 0
        for m in self.matches:
            parts = m.total_time.split(':')
            if len(parts) == 2:
                total += int(parts[0]) * 60 + int(parts[1])
        return total

    def avg_shift_seconds(self) -> int:
        shifts = self.total_shifts()
        sec = self.total_time_seconds()
        return int(sec / shifts) if shifts else 0

    def total_pp_seconds(self) -> int:
        total = 0
        for m in self.matches:
            parts = m.powerplay.split(':')
            if len(parts) == 2:
                total += int(parts[0]) * 60 + int(parts[1])
        return total

    def total_pk_seconds(self) -> int:
        total = 0
        for m in self.matches:
            parts = m.penalty_kill.split(':')
            if len(parts) == 2:
                total += int(parts[0]) * 60 + int(parts[1])
        return total

    def total_goals(self) -> int:
        return sum(m.goals for m in self.matches)

    def total_assists(self) -> int:
        return sum(m.assists for m in self.matches)

    def total_points(self) -> int:
        return sum(m.points for m in self.matches)

    def total_plus_minus(self) -> int:
        return sum(m.plus_minus for m in self.matches)

    def total_penalties(self) -> int:
        return sum(m.penalties for m in self.matches)

    def total_on_ice_gf(self) -> int:
        return sum(m.on_ice_gf for m in self.matches)

    def total_on_ice_ga(self) -> int:
        return sum(m.on_ice_ga for m in self.matches)


# =============================================================================
# СБОРЩИК ДАННЫХ
# =============================================================================

class SeasonReportDataCollector:
    def __init__(self, hkt_folder_path: str):
        self.hkt_folder_path = hkt_folder_path
        self.player_summaries: Dict[str, PlayerSeasonSummary] = {}
        self.season_name: str = ""
        self.player_db: Dict[str, dict] = self._load_player_db()
        self._collect_data()

    def _load_player_db(self) -> Dict[str, dict]:
        db_path = os.path.join('Data', 'players_db.json')
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки players_db.json: {e}")
        return {}

    def _collect_data(self):
        files = [f for f in os.listdir(self.hkt_folder_path) if f.lower().endswith('.hkt')]
        files.sort()

        for fname in files:
            fpath = os.path.join(self.hkt_folder_path, fname)
            try:
                project = load_project_from_file(fpath)
            except Exception as e:
                print(f"[SKIP] Ошибка загрузки {fname}: {e}")
                continue

            if not is_match_completed(project):
                print(f"[SKIP] Не окончен: {fname}")
                continue

            try:
                rd = ReportData(original_project=project, sort_order=SORT_BY_EXIT_TIME)
            except Exception as e:
                print(f"[SKIP] Ошибка ReportData {fname}: {e}")
                continue

            # Сезон берём из первого успешного файла
            if not self.season_name and project.match.tournament_name:
                self.season_name = project.match.tournament_name

            our_key = rd.our_team_key
            opp_key = 's-team' if our_key == 'f-team' else 'f-team'
            opp_name = str(rd.original_project.match.teams.get(opp_key, '')).replace(' 2014', '').replace('2014', '')
            opp_logo = rd.get_team_logo_path(opp_key)
            home_away = 'Д' if our_key == 'f-team' else 'Г'

            our_g, their_g = rd.get_final_score()
            result = 'В' if our_g > their_g else 'П'
            tour_num = str(project.match.tour_number or '')

            # --- собираем данные по каждому игроку матча ---
            for p_info in rd.players_list:
                pid = p_info.player_id

                # Имя из rosters (полное, не сокращённое)
                raw_name = ""
                for rp in project.match.rosters.get(our_key, []):
                    if rp.get('id_fhm') == pid:
                        raw_name = rp.get('name', '')
                        break

                if pid not in self.player_summaries:
                    self.player_summaries[pid] = PlayerSeasonSummary(
                        player_id=pid,
                        player_number=p_info.number,
                        player_name=p_info.full_name,
                        player_full_name=raw_name,
                        player_role=p_info.role,
                    )
                summary = self.player_summaries[pid]
                # обновляем полное имя, если раньше было пусто
                if not summary.player_full_name and raw_name:
                    summary.player_full_name = raw_name

                shifts = rd.shifts_by_player_id.get(pid, [])
                sc = len(shifts)
                tot_sec = sum(int(s.duration) for s in shifts)
                avg_sec = int(tot_sec / sc) if sc else 0

                pp_sec = calculate_special_team_time(rd, pid, 'powerplay')
                pk_sec = calculate_special_team_time(rd, pid, 'penalty_kill')

                def _fmt(sec: int) -> str:
                    return f"{sec // 60}:{sec % 60:02d}"

                goals = calculate_player_goals(rd, pid)
                assists = calculate_player_assists(rd, pid)
                plus_minus = calculate_player_plus_minus(rd, pid)
                penalties = calculate_player_penalties(rd, pid)
                on_ice_gf, on_ice_ga = calculate_on_ice_gf_ga(rd, pid)

                row = SeasonMatchRow(
                    tour_number=tour_num,
                    opponent_logo_path=opp_logo,
                    opponent_name=opp_name,
                    home_away=home_away,
                    result=result,
                    shifts_count=sc,
                    avg_shift=f'{avg_sec}"' if avg_sec else "",
                    total_time=_fmt(tot_sec) if tot_sec else "",
                    powerplay=_fmt(pp_sec) if pp_sec else "",
                    penalty_kill=_fmt(pk_sec) if pk_sec else "",
                    goals=goals,
                    assists=assists,
                    points=goals + assists,
                    plus_minus=plus_minus,
                    penalties=penalties,
                    on_ice_gf=on_ice_gf,
                    on_ice_ga=on_ice_ga,
                )
                summary.matches.append(row)

        # Сортируем матчи каждого игрока по туру DESC
        for summary in self.player_summaries.values():
            try:
                summary.matches.sort(
                    key=lambda m: int(m.tour_number) if str(m.tour_number).isdigit() else 0,
                    reverse=True
                )
            except Exception:
                pass

    def get_players_list(self) -> List[PlayerSeasonSummary]:
        """Возвращает список игроков: вратари первыми, затем по алфавиту."""
        players = list(self.player_summaries.values())
        players.sort(key=lambda p: (
            0 if p.player_role.lower().startswith('вратарь') else 1,
            p.player_name
        ))
        return players

    def find_player_photo(self, player_id: str, number: str) -> str:
        """Ищет фото игрока по согласованному шаблону имени."""
        photo_dir = os.path.join('Data', 'player_photos')
        if not os.path.isdir(photo_dir):
            return ""

        # Попытка 1: точное имя из players_db.json
        entry = self.player_db.get(player_id)
        if entry:
            full = entry.get('name', '')
            parts = full.split()
            if len(parts) >= 2:
                expected = f"{player_id}-{parts[0]}-{parts[1]}-№{number}.jpg"
                path = os.path.join(photo_dir, expected)
                if os.path.exists(path):
                    return path

        # Попытка 2: glob по id + номер
        pattern = os.path.join(photo_dir, f"{player_id}-*-№{number}.jpg")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]

        return ""
