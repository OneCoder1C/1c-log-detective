from collections.abc import Iterator
from dataclasses import dataclass
import re


@dataclass
class TechLogEvent:
    """Одно событие технологического журнала 1С."""

    timestamp: str
    event_type: str
    level: str
    raw_text: str
    description: str
    duration_us: int | None = None


def is_event_start(line: str) -> bool:
    """Проверяет, похожа ли строка на начало события 1С."""
    parts = line.split(",", maxsplit=3)

    if len(parts) < 3:
        return False

    timestamp = parts[0]
    event_type = parts[1]
    event_number = parts[2]

    valid_event_type = event_type.isupper() or event_type == "DBV8DBEng"

    return (
        ":" in timestamp
        and "." in timestamp
        and valid_event_type
        and event_number.isdigit()
    )


def extract_fields(raw_text: str) -> dict[str, str]:
    """Извлекает простые поля key=value из текста события ТЖ."""
    fields: dict[str, str] = {}

    pattern = re.compile(
        r"""(?:^|,)([A-Za-z][A-Za-z0-9_]*)=
        (?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)'|([^,\r\n]*))""",
        re.MULTILINE | re.VERBOSE,
    )

    for match in pattern.finditer(raw_text):
        key = match.group(1)
        value = next(
            (item for item in match.groups()[1:] if item is not None),
            "",
        )
        fields[key] = value.strip()

    return fields


def parse_lock_event(raw_text: str) -> dict | None:
    """Извлекает структурированные данные из события TLOCK."""
    event = parse_event(raw_text)

    if event is None or event.event_type != "TLOCK":
        return None

    fields = extract_fields(raw_text)
    locks = fields.get("Locks", "")

    mode_match = re.search(
        r"\b(Shared|Exclusive)\b",
        locks,
        re.IGNORECASE,
    )

    resource_id_match = re.search(
        r"\bID=([^\s,]+)",
        locks,
    )

    resource_fields = dict(
        re.findall(
            r"\b(Fld\d+)=((?:\"[^\"]*\")|(?:'[^']*')|[^\s,]+)",
            locks,
        )
    )

    resource_fields = {
        key: value.strip("\"'") for key, value in resource_fields.items()
    }

    return {
        "timestamp": event.timestamp,
        "level": event.level,
        "process": fields.get("process", ""),
        "thread": fields.get("OSThread", ""),
        "user": fields.get("Usr", ""),
        "database": fields.get("DataBase", ""),
        "regions": fields.get("Regions", ""),
        "lock_mode": (mode_match.group(1).upper() if mode_match else "UNKNOWN"),
        "resource_id": (resource_id_match.group(1) if resource_id_match else ""),
        "resource_fields": resource_fields,
        "context": fields.get("Context", ""),
    }


def split_events(lines: list[str]) -> list[str]:
    """Собирает многострочные записи журнала в отдельные события."""
    events = []
    current_lines = []

    for line in lines:
        line = line.rstrip("\r\n")

        if not line:
            continue

        if is_event_start(line):
            if current_lines:
                events.append("\n".join(current_lines))

            current_lines = [line]

        elif current_lines:
            current_lines.append(line)

    if current_lines:
        events.append("\n".join(current_lines))

    return events


def iter_techlog_events(lines) -> Iterator[str]:
    """Последовательно собирает многострочные события журнала."""
    current_lines = []

    for line in lines:
        line = line.rstrip("\r\n")

        if not line:
            continue

        if is_event_start(line):
            if current_lines:
                yield "\n".join(current_lines)

            current_lines = [line]

        elif current_lines:
            current_lines.append(line)

    if current_lines:
        yield "\n".join(current_lines)


def parse_event(raw_text: str) -> TechLogEvent | None:
    """Извлекает основные поля из события технологического журнала 1С."""
    first_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""

    if not is_event_start(first_line):
        return None

    parts = first_line.split(",", maxsplit=3)

    timestamp = parts[0]
    duration_match = re.search(r"-(\d+)$", timestamp)
    duration_us = int(duration_match.group(1)) if duration_match else None

    event_type = parts[1]
    properties_text = parts[3] if len(parts) > 3 else ""

    level_match = re.search(r"(?:^|,)level=([^,\s]+)", properties_text)

    level = level_match.group(1) if level_match else "UNKNOWN"

    description_match = re.search(
        r"(?:^|,)Descr=(['\"])(.*?)(?<!\\)\1(?=,|\r?\n|$)",
        raw_text,
        re.DOTALL,
    )

    description = description_match.group(2) if description_match else ""

    return TechLogEvent(
        timestamp=timestamp,
        event_type=event_type,
        level=level,
        raw_text=raw_text,
        description=description,
        duration_us=duration_us,
    )


from collections import Counter


def summarize_events(events) -> dict:
    """Считает количество событий по типам и уровням важности."""
    by_type = Counter()
    by_level = Counter()
    total = 0

    for event in events:
        total += 1
        by_type[event.event_type] += 1
        by_level[event.level] += 1

    return {
        "total": total,
        "by_type": dict(by_type),
        "by_level": dict(by_level),
    }


def summarize_event_stream(events) -> dict:
    """Считает количество событий по типам и уровням без хранения списка."""
    by_type = Counter()
    by_level = Counter()
    total = 0

    for event in events:
        total += 1
        by_type[event.event_type] += 1
        by_level[event.level] += 1

    return {
        "total": total,
        "by_type": dict(by_type),
        "by_level": dict(by_level),
    }


from pathlib import Path


def read_techlog_file(file_path: str | Path) -> list[TechLogEvent]:
    """Читает файл технологического журнала и разбирает события."""
    path = Path(file_path)
    events = []

    with path.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is not None:
                events.append(event)

    return events


from pathlib import Path


def save_report(report_text: str, output_path: str | Path) -> None:
    """Сохраняет текстовый отчёт в файл."""
    path = Path(output_path)
    path.write_text(report_text, encoding="utf-8")
