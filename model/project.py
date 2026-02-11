# model/project.py
import json
import uuid
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field # <-- Убедитесь, что dataclass и field импортированы

# --- Новые классы для модели данных (п. 2.3, 2.4, 2.2) ---

class GenericLabel:
    """
    Представляет временную метку, установленную Оператором в произвольной точке видео.
    (п. 2.3 ТЗ 4.0)
    """
    def __init__(self, label_type: str, global_time: float, id: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        self.id: str = id or str(uuid.uuid4())
        self.label_type: str = label_type
        self.global_time: float = global_time
        self.context: Optional[Dict[str, Any]] = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь для сериализации в JSON."""
        return {
            "id": self.id,
            "label_type": self.label_type,
            "global_time": self.global_time,
            # Сериализуем context только если он не пуст
            "context": self.context if self.context else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenericLabel':
        """Создаёт объект из словаря."""
        return cls(
            id=data.get("id", str(uuid.uuid4())), # Генерируем id, если не найден
            label_type=data["label_type"],
            global_time=data["global_time"],
            context=data.get("context") # Может быть None или словарём
        )

class CalculatedRange:
    """
    Модель рассчитанного временного диапазона.
    Создаётся модулем SMART на основе накопленных GenericLabel.
    """
    def __init__(self, name: str, label_type: str, start_time: float, end_time: float, source_label_ids: List[str], id: Optional[str] = None, context: Optional[Dict[str, Any]] = None): # <-- Добавлен параметр context
        self.id: str = id or str(uuid.uuid4())
        self.name: str = name
        self.label_type: str = label_type
        self.start_time: float = start_time
        self.end_time: float = end_time
        self.source_label_ids: List[str] = source_label_ids
        self.context: Optional[Dict[str, Any]] = context or {} # <-- Сохраняем context
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь для сериализации в JSON."""
        return {
            "id": self.id,
            "name": self.name,
            "label_type": self.label_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "source_label_ids": self.source_label_ids,
            "context": self.context if self.context else None # <-- Сериализуем context
        }
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalculatedRange':
        """Создаёт объект из словаря."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            label_type=data["label_type"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            source_label_ids=data.get("source_label_ids", []),
            context=data.get("context") # <-- Десериализуем context
        )

# ... (до определения Match) ...

@dataclass
class PlayerShift:
    """
    Модель одной смены игрока.
    """
    number: int  # Номер смены (1, 2, 3...)
    start_time: float  # Время начала смены (глобальное)
    end_time: float    # Время окончания смены (глобальное)

@dataclass
class PlayerShiftInfo:
    """
    Модель информации о сменах одного игрока.
    """
    id_fhm: str  # Уникальный идентификатор игрока
    name: str    # Имя игрока
    shifts: List[PlayerShift] = field(default_factory=list) # Список смен игрока

class Match:
    def __init__(
        self,
        generic_labels: Optional[List[GenericLabel]] = None,
        calculated_ranges: Optional[List[CalculatedRange]] = None,
        player_shifts: Optional[Dict[str, PlayerShiftInfo]] = None,
        player_shifts_official_timer: Optional[Dict[str, PlayerShiftInfo]] = None,
        match_id: Optional[str] = None,
        teams: Optional[Dict[str, Any]] = None,
        rosters: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        # -------------------------------
    ):
        self.generic_labels: List[GenericLabel] = generic_labels or []
        self.calculated_ranges: List[CalculatedRange] = calculated_ranges or []
        # --- НОВЫЕ ПОЛЯ (после calculated_ranges) ---
        # --- ИСПРАВЛЕНО: НОВЫЕ ПОЛЯ (после calculated_ranges) ---
        self.player_shifts: Dict[str, PlayerShiftInfo] = player_shifts or {}
        self.player_shifts_official_timer: Dict[str, PlayerShiftInfo] = player_shifts_official_timer or {} # <-- Теперь корректно
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
        # --- КОНЕЦ НОВЫХ ПОЛЕЙ ---
        # --- Новые поля ---
        self.match_id: Optional[str] = match_id
        self.teams: Dict[str, Any] = teams or {}
        self.rosters: Dict[str, List[Dict[str, Any]]] = rosters or {}
        self.events: List[Dict[str, Any]] = events or []
        # -----------------


    def to_dict(self) -> Dict[str, Any]:
        return {
            "generic_labels": [label.to_dict() for label in self.generic_labels],
            "calculated_ranges": [range_obj.to_dict() for range_obj in self.calculated_ranges],
            # --- НОВОЕ ПОЛЕ (после calculated_ranges) ---
            "player_shifts": {
                pid: {
                    "id_fhm": psi.id_fhm,
                    "name": psi.name,
                    "shifts": [shift.__dict__ for shift in psi.shifts]
                } for pid, psi in self.player_shifts.items()
            },
            "player_shifts_official_timer": { # <-- Новое поле
                pid: {
                    "id_fhm": psi.id_fhm,
                    "name": psi.name,
                    "shifts": [shift.__dict__ for shift in psi.shifts]
                } for pid, psi in self.player_shifts_official_timer.items()
            },
            # --- КОНЕЦ НОВОГО ПОЛЯ ---
            # --- Новые поля ---
            "match_id": self.match_id,
            "teams": self.teams,
            "rosters": self.rosters,
            "events": self.events,
            # -----------------
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Match':
        generic_labels_data = data.get("generic_labels", [])
        calculated_ranges_data = data.get("calculated_ranges", [])

        # --- НОВОЕ ПОЛЕ: Десериализация player_shifts ---
        raw_player_shifts = data.get("player_shifts", {})
        deserialized_player_shifts = {}
        for pid, psi_data in raw_player_shifts.items():
            shifts_list = [PlayerShift(**shift_data) for shift_data in psi_data.get("shifts", [])]
            deserialized_player_shifts[pid] = PlayerShiftInfo(
                id_fhm=psi_data["id_fhm"],
                name=psi_data["name"],
                shifts=shifts_list
            )
        # --- КОНЕЦ НОВОГО ПОЛЯ ---

        # --- НОВОЕ ПОЛЕ: Десериализация player_shifts_official_timer ---
        raw_player_shifts_ot = data.get("player_shifts_official_timer", {}) # <-- Новое поле
        deserialized_player_shifts_ot = {}
        for pid, psi_data in raw_player_shifts_ot.items():
            shifts_list = [PlayerShift(**shift_data) for shift_data in psi_data.get("shifts", [])]
            deserialized_player_shifts_ot[pid] = PlayerShiftInfo(
                id_fhm=psi_data["id_fhm"],
                name=psi_data["name"],
                shifts=shifts_list
            )
        # --- КОНЕЦ НОВОГО ПОЛЯ ---

        # --- Новые поля ---
        raw_match_data = data # <-- Предполагаем, что match_id, teams и т.д. находятся на верхнем уровне

        return cls(
            generic_labels=[GenericLabel.from_dict(d) for d in generic_labels_data],
            calculated_ranges=[CalculatedRange.from_dict(d) for d in calculated_ranges_data],
            # --- НОВЫЕ ПОЛЯ ---
            player_shifts=deserialized_player_shifts,
            player_shifts_official_timer=deserialized_player_shifts_ot, # <-- Передача нового поля
            # --- КОНЕЦ НОВЫХ ПОЛЕЙ ---
            # --- Новые поля из протокола ---
            match_id=raw_match_data.get("match_id"),
            teams=raw_match_data.get("teams", {}),
            rosters=raw_match_data.get("rosters", {}),
            events=raw_match_data.get("events", []),
            # -------------------------------
        )

class Project:
    """
    Объект проекта для версии 4.0, сериализуемый в JSON-файл с расширением .hkt.
    Содержит версию, путь к видео и данные матча.
    (п. 2.1 ТЗ 4.0)
    """
    def __init__(self, version: str = "4.0"):
        self.version: str = version
        self.video_path: Optional[str] = None
        self.match: Match = Match() # Добавляем поле match

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь для сериализации в JSON."""
        return {
            "version": self.version,
            "video_path": self.video_path,
            "match": self.match.to_dict() # Сериализуем match
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Создаёт объект из словаря."""
        version = data.get("version", "4.0")
        project = cls(version=version)
        project.video_path = data.get("video_path")
        # Десериализуем match, если он присутствует в данных
        if "match" in data:
            project.match = Match.from_dict(data["match"])
        # Иначе останется пустой Match по умолчанию
        return project

    def save_to_file(self, file_path: str):
        """Сохраняет проект в JSON-файл."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str) -> 'Project':
        """Загружает проект из JSON-файла."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

