import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from modules.reports.season_report_data import SeasonReportDataCollector
from modules.reports.season_report_generator import PlayerSeasonReportGenerator

def main():
    folder = 'hkt'
    print(f"Сканируем: {folder}")
    collector = SeasonReportDataCollector(folder)
    players = collector.get_players_list()
    print(f"Игроков: {len(players)}")
    print(f"Сезон: {collector.season_name}")

    if not players:
        print("Нет игроков для отчёта.")
        return

    # Берём игрока для теста (Арнаут Иван — нападающий)
    player = None
    for p in players:
        if p.player_number == "77":
            player = p
            break
    if not player:
        player = players[0]
    print(f"Генерация для: {player.player_full_name} ({player.player_number}), матчей: {len(player.matches)}")

    generator = PlayerSeasonReportGenerator()
    img = generator.generate(player, collector.season_name, collector.player_db)

    output = "test_report_2_output.png"
    img.save(output)
    print(f"Сохранено: {output}")

if __name__ == "__main__":
    main()
