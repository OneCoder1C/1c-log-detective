from collections.abc import Iterable

from techlog import TechLogEvent, extract_fields
from exception_groups import normalize_exception


def build_incident_timeline(
    events: Iterable[TechLogEvent],
    error_index: int | None = None,
    window: int = 20,
) -> dict:
    """Формирует хронологию событий вокруг исключения.

    window — количество событий до и после выбранной ошибки.
    Индексация начинается с нуля.
    """
    all_events = list(events)

    if not all_events:
        return {
            "error": "События не найдены.",
            "timeline": [],
        }

    if error_index is None:
        candidates = [
            index
            for index, event in enumerate(all_events)
            if event.event_type == "EXCP"
        ]
        if not candidates:
            return {
                "error": "В журнале не найдено исключений EXCP.",
                "timeline": [],
            }
        error_index = candidates[-1]

    if error_index < 0 or error_index >= len(all_events):
        raise IndexError("Индекс ошибки выходит за границы списка событий.")

    start = max(0, error_index - window)
    end = min(len(all_events), error_index + window + 1)
    timeline = []

    for index in range(start, end):
        event = all_events[index]
        fields = extract_fields(event.raw_text)

        item = {
            "index": index,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "level": event.level,
            "description": event.description,
            "process": fields.get("process", ""),
            "thread": fields.get("OSThread", ""),
            "user": fields.get("Usr", ""),
            "context": fields.get("Context", ""),
            "is_target_error": index == error_index,
        }

        if event.event_type == "EXCP":
            item["exception_category"] = normalize_exception(event.description)

        timeline.append(item)

    target = all_events[error_index]

    target_info = {
        "index": error_index,
        "timestamp": target.timestamp,
        "event_type": target.event_type,
        "description": target.description,
    }

    if target.event_type == "EXCP":
        target_info["exception_category"] = normalize_exception(target.description)

    return {
        "error": None,
        "target": target_info,
        "events_before": error_index - start,
        "events_after": end - error_index - 1,
        "timeline": timeline,
    }


def format_incident_timeline(incident: dict) -> str:
    """Преобразует хронологию инцидента в читаемый текстовый отчёт."""
    if incident.get("error"):
        return incident["error"]

    target = incident["target"]
    lines = [
        "РАЗБОР ИНЦИДЕНТА 1С",
        "=" * 60,
        f"Время ошибки: {target['timestamp']}",
        f"Тип события: {target['event_type']}",
        f"Категория: {target.get('exception_category', 'Не определена')}",
        f"Описание: {target['description']}",
        "",
        "ХРОНОЛОГИЯ",
        "-" * 60,
    ]

    for event in incident["timeline"]:
        marker = " >>> ОШИБКА" if event["is_target_error"] else ""
        lines.append(
            f"{event['timestamp']} | "
            f"{event['event_type']} | "
            f"{event['level']}{marker}"
        )

        if event["description"]:
            lines.append(f"    {event['description']}")

        if event["user"]:
            lines.append(f"    Пользователь: {event['user']}")

        if event["thread"]:
            lines.append(f"    Поток: {event['thread']}")

        if event["context"]:
            lines.append(f"    Контекст: {event['context']}")

    lines.extend(
        [
            "",
            "Примечание: соседство событий во времени не доказывает",
            "причинно-следственную связь. Проверьте контекст инцидента.",
        ]
    )
    return "\n".join(lines)


def analyze_incident_file(log_file, window=20):
    """Находит последнее исключение и формирует хронологию инцидента."""
    from collections import deque

    from techlog import iter_techlog_events, parse_event

    recent_events = deque(maxlen=window + 1)
    last_incident = None
    events_after_error = 0

    with open(log_file, "r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None:
                continue

            if last_incident is not None:
                if events_after_error < window:
                    last_incident["timeline"].append(event)
                    events_after_error += 1

            if event.event_type == "EXCP":
                last_incident = {
                    "target": event,
                    "timeline": list(recent_events) + [event],
                }
                events_after_error = 0

            recent_events.append(event)

    if last_incident is None:
        return "В журнале не найдено исключений EXCP."

    return format_incident_timeline(
        build_incident_timeline(
            last_incident["timeline"],
            error_index=len(last_incident["timeline"]) - events_after_error - 1,
            window=window,
        )
    )
