import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import urllib3
from pathlib import Path

# Отключаем предупреждения InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Путь к файлу базы данных игроков
PLAYERS_DB_PATH = Path("Data/players_db.json")

# Словарь месяцев для парсинга даты рождения
MONTHS_RU = {
    "январь": "01",
    "февраль": "02",
    "март": "03",
    "апрель": "04",
    "май": "05",
    "июнь": "06",
    "июль": "07",
    "август": "08",
    "сентябрь": "09",
    "октябрь": "10",
    "ноябрь": "11",
    "декабрь": "12",
}


def normalize_spaces(text):
    """
    Нормализует пробелы в строке: заменяет множественные пробелы на один,
    убирает пробелы в начале и конце.
    """
    if text is None:
        return ""
    return " ".join(text.split())


def format_name(full_name):
    """
    Нормализует полное имя 'Фамилия Имя Отчество'.
    Возвращает имя в формате 'Фамилия Имя Отчество' (с удалением лишних пробелов).
    """
    return normalize_spaces(full_name)


def parse_birthdate(raw_text):
    """
    Преобразует строку 'Дата рождения: 20 Январь 2014' в формат '2014-01-20'.
    Возвращает None, если не удалось распознать.
    """
    if not raw_text:
        return None
    match = re.search(r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})", raw_text)
    if not match:
        return None
    day, month_name, year = match.groups()
    month_num = MONTHS_RU.get(month_name.lower())
    if not month_num:
        return None
    return f"{year}-{month_num}-{int(day):02d}"


def parse_player_page(player_id, fallback=None):
    """
    Парсит страницу игрока на fhmoscow.com и возвращает словарь с данными.

    Args:
        player_id (str): ID игрока (например, "8962").
        fallback (dict, optional): Fallback-данные из .hkt (number, role).

    Returns:
        dict or None: {
            "name": "Фамилия Имя Отчество",
            "height": "150",
            "weight": "44",
            "hand": "левый",
            "birthdate": "2014-01-20",
            "number": "77",
            "role": "Нападающий"
        } или None в случае ошибки.
    """
    url = f"https://fhmoscow.com/player/{player_id}"
    try:
        response = requests.get(url, verify=False, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Ошибка загрузки страницы игрока {player_id}: {e}")
        return None

    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    # Проверяем, существует ли страница (иногда 200, но "страница не найдена")
    name_elem = soup.find("h1", class_="name")
    if not name_elem:
        print(f"[WARN] На странице игрока {player_id} не найдено имя. Возможно, страница пустая.")
        return None

    full_name = normalize_spaces(name_elem.get_text(strip=True))
    name = format_name(full_name)

    # Рост
    height = None
    height_div = soup.find("div", class_="params height")
    if height_div:
        h2 = height_div.find("h2", class_="h2 no-margin-bottom color-white")
        if h2:
            height = normalize_spaces(h2.get_text(strip=True))

    # Вес
    weight = None
    weight_div = soup.find("div", class_="params weight")
    if weight_div:
        h2 = weight_div.find("h2", class_="h2 no-margin-bottom color-white")
        if h2:
            weight = normalize_spaces(h2.get_text(strip=True))

    # Хват
    hand = None
    grip_div = soup.find("div", class_="params grip")
    if grip_div:
        h2 = grip_div.find("h2", class_="h2 no-margin-bottom color-white")
        if h2:
            hand = normalize_spaces(h2.get_text(strip=True)).lower()

    # Дата рождения
    birthdate = None
    birth_elem = soup.find("p", class_="birthday-player")
    if birth_elem:
        birthdate_raw = normalize_spaces(birth_elem.get_text(strip=True))
        birthdate = parse_birthdate(birthdate_raw)

    # Игровой номер
    number = None
    number_div = soup.find("div", class_="number")
    if number_div:
        h3 = number_div.find("h3", class_="h3 no-margin-bottom color-white")
        if h3:
            number = normalize_spaces(h3.get_text(strip=True))

    # Игровое амплуа (позиция)
    role = None
    pos_elem = soup.find("p", class_="position")
    if pos_elem:
        role = normalize_spaces(pos_elem.get_text(strip=True))

    # Fallback из .hkt, если на странице чего-то не хватает
    if fallback:
        if not number and fallback.get("number"):
            number = fallback["number"]
        if not role and fallback.get("role"):
            role = fallback["role"]

    return {
        "name": name,
        "height": height,
        "weight": weight,
        "hand": hand,
        "birthdate": birthdate,
        "number": number,
        "role": role,
    }


def load_db():
    """
    Загружает существующую базу игроков из JSON.
    Если файл не существует, возвращает пустой словарь.
    """
    if PLAYERS_DB_PATH.exists():
        try:
            with open(PLAYERS_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Ошибка чтения {PLAYERS_DB_PATH}: {e}. Начинаем с пустой базы.")
    return {}


def save_db(db):
    """
    Сохраняет базу игроков в JSON-файл.
    """
    PLAYERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(PLAYERS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"[ERROR] Ошибка сохранения базы в {PLAYERS_DB_PATH}: {e}")
        return False


# Название нашей команды (константа)
OUR_TEAM_NAME = "Созвездие 2014"


def extract_player_ids_from_hkt(folder):
    """
    Рекурсивно сканирует папку на наличие .hkt файлов и собирает
    уникальные id_fhm только из состава нашей команды (Созвездие 2014).
    Также собирает fallback-данные (number, role) из .hkt.

    Args:
        folder (str): Путь к папке (например, "hkt" или "Data/save").

    Returns:
        tuple: (set ID, dict fallback) где fallback = {id: {"number": ..., "role": ...}}
    """
    ids = set()
    fallback = {}
    root_path = Path(folder)
    if not root_path.exists():
        print(f"[WARN] Папка {folder} не существует.")
        return ids, fallback

    for file_path in root_path.rglob("*.hkt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        match = data.get("match", {})
        teams = match.get("teams", {})
        rosters = match.get("rosters", {})

        # Определяем, под каким ключом (f-team или s-team) наша команда
        for team_key in ("f-team", "s-team"):
            if teams.get(team_key) == OUR_TEAM_NAME:
                for player in rosters.get(team_key, []):
                    pid = player.get("id_fhm")
                    if pid and pid != "N/A":
                        pid_str = str(pid)
                        ids.add(pid_str)
                        # Сохраняем fallback-данные (последние встреченные)
                        if pid_str not in fallback:
                            fallback[pid_str] = {}
                        num = player.get("number")
                        if num and num != "N/A":
                            fallback[pid_str]["number"] = str(num)
                        r = player.get("role")
                        if r and r != "N/A":
                            fallback[pid_str]["role"] = str(r)
                break  # Нашли нашу команду в этом матче — дальше не ищем

    return ids, fallback


def add_or_update_player(db, player_id, player_data):
    """
    Добавляет или обновляет данные игрока в базе.
    """
    if player_data is None:
        return False
    db[str(player_id)] = player_data
    return True


def main():
    """
    Основная функция с интерактивным меню.
    """
    print("=" * 60)
    print(" Парсер базы данных игроков (локальный кэш)")
    print(f" Файл базы: {PLAYERS_DB_PATH}")
    print("=" * 60)

    db = load_db()
    print(f"[INFO] Загружено {len(db)} записей из существующей базы.")

    while True:
        print("\nМеню:")
        print("  1 — Добавить / обновить игрока по ID или URL")
        print("  2 — Автоскан .hkt файлов и массовое обновление")
        print("  3 — Показать текущую базу (количество записей)")
        print("  4 — Выход")
        choice = input("\nВыберите действие: ").strip()

        if choice == "1":
            user_input = input("Введите ID игрока или URL (например, 8962 или https://fhmoscow.com/player/8962): ").strip()
            if not user_input:
                continue
            match = re.search(r"/player/(\d+)", user_input)
            if match:
                player_id = match.group(1)
            else:
                player_id = re.sub(r"\D", "", user_input)

            if not player_id:
                print("[ERROR] Не удалось определить ID игрока.")
                continue

            print(f"[INFO] Загружаем данные для игрока {player_id}...")
            data = parse_player_page(player_id)
            if data:
                add_or_update_player(db, player_id, data)
                if save_db(db):
                    print(f"[OK] Игрок {player_id} ({data['name']}) успешно сохранён.")
                else:
                    print("[ERROR] Не удалось сохранить базу.")
            else:
                print(f"[FAIL] Не удалось получить данные для игрока {player_id}.")

        elif choice == "2":
            folder = input("Введите путь к папке с .hкт файлами (Enter для 'hkt'): ").strip()
            if not folder:
                folder = "hkt"

            player_ids, fallback_data = extract_player_ids_from_hkt(folder)
            if not player_ids:
                print("[WARN] Не найдено ни одного ID игрока в .hkt файлах.")
                continue

            print(f"[INFO] Найдено {len(player_ids)} уникальных ID. Начинаем обработку...")
            added = 0
            updated = 0
            skipped = 0

            for idx, pid in enumerate(sorted(player_ids), 1):
                exists = pid in db
                print(f"[{idx}/{len(player_ids)}] Обработка {pid}...", end=" ")
                fb = fallback_data.get(pid)
                data = parse_player_page(pid, fallback=fb)
                if data:
                    add_or_update_player(db, pid, data)
                    if exists:
                        updated += 1
                        print(f"обновлено ({data['name']})")
                    else:
                        added += 1
                        print(f"добавлено ({data['name']})")
                else:
                    skipped += 1
                    print("пропущено (ошибка)")

                # Небольшая задержка, чтобы не нагружать сервер
                time.sleep(0.3)

            if save_db(db):
                print(f"\n[OK] База сохранена. Добавлено: {added}, Обновлено: {updated}, Пропущено: {skipped}.")
            else:
                print("\n[ERROR] Ошибка сохранения базы.")

        elif choice == "3":
            print(f"[INFO] В базе {len(db)} записей.")
            for pid, info in sorted(db.items(), key=lambda x: x[1].get("name", "")):
                name = info.get("name", "N/A")
                num = info.get("number", "—")
                role = info.get("role", "—")
                h = info.get("height", "—")
                w = info.get("weight", "—")
                hand = info.get("hand", "—")
                bd = info.get("birthdate", "—")
                print(f"  {pid}: #{num} {name} ({role}) | Рост: {h} | Вес: {w} | Хват: {hand} | ДР: {bd}")

        elif choice == "4":
            print("[INFO] Работа завершена.")
            break
        else:
            print("[ERROR] Некорректный ввод. Пожалуйста, выберите 1, 2, 3 или 4.")


if __name__ == "__main__":
    main()
