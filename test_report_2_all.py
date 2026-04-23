import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from modules.reports.season_report_data import SeasonReportDataCollector
from modules.reports.season_report_generator import PlayerSeasonReportGenerator

def main():
    folder = 'hkt'
    out_dir = 'test_report_2_outputs'
    os.makedirs(out_dir, exist_ok=True)

    print(f"Сканируем: {folder}")
    collector = SeasonReportDataCollector(folder)
    players = collector.get_players_list()
    print(f"Игроков: {len(players)}")

    generator = PlayerSeasonReportGenerator()
    errors = []

    for p in players:
        surname = (p.player_full_name or p.player_name).split()[0]
        filename = f"{p.player_number}_{surname}__stats.png"
        filepath = os.path.join(out_dir, filename)
        try:
            img = generator.generate(p, collector.season_name, collector.player_db)
            img.save(filepath)
            print(f"OK: {filename} ({len(p.matches)} матчей)")
        except Exception as e:
            print(f"ERROR: {filename} -> {e}")
            errors.append((filename, str(e)))

    print(f"\nГотово. Ошибок: {len(errors)}")
    if errors:
        for f, e in errors:
            print(f"  {f}: {e}")

if __name__ == "__main__":
    main()
