from collections.abc import Iterable

from techlog import TechLogEvent, extract_fields
from incident_correlation import (
    analyze_incident_evidence,
    build_incident_chain,
    extract_event_details,
)


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
            "raw_text": event.raw_text,
            "process": fields.get("process", ""),
            "thread": fields.get("OSThread", ""),
            "user": fields.get("Usr", ""),
            "context": fields.get("Context", ""),
            "is_target_error": index == error_index,
        }

        if event.event_type == "EXCP":
            item.update(extract_event_details(event))

        timeline.append(item)

    target = all_events[error_index]

    target_info = {
        "index": error_index,
        "timestamp": target.timestamp,
        "event_type": target.event_type,
        "description": target.description,
        "raw_text": target.raw_text,
    }

    if target.event_type == "EXCP":
        target_info.update(extract_event_details(target))

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

    for label, key in (
        ("Деталь исключения", "exception_detail"),
        ("GUID", "exception_guid"),
        ("Ресурс", "exception_resource"),
    ):
        value = target.get(key)
        if value:
            lines.append(f"{label}: {value}")

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


def analyze_incident_file_correlated(log_file, window=20):
    """Потоково находит EXCP и строит отдельную цепочку для каждого инцидента."""

    from collections import deque
    from pathlib import Path

    from techlog import (
        iter_techlog_events,
        iter_techlog_file_lines,
        parse_event,
    )

    log_path = Path(log_file)

    if log_path.is_file():
        log_files = [log_path]
    elif log_path.is_dir():
        log_files = sorted(
            log_path.rglob("*.log"),
            key=lambda path: path.name,
        )

        if not log_files:
            raise FileNotFoundError(f"В папке не найдены файлы .log: {log_path}")
    else:
        raise FileNotFoundError(f"Путь не найден: {log_path}")

    recent_events = deque(maxlen=window)
    incidents = []
    current_incident = None
    events_after_error = 0
    global_index = 0
    session_events = []

    for raw_event in iter_techlog_events(iter_techlog_file_lines(log_files)):
        event = parse_event(raw_event)

        if event is None:
            continue

        current_index = global_index
        global_index += 1

        if event.event_type == "SESN":
            session_events.append((event, current_index))

        if current_incident is not None and events_after_error < window:
            current_incident["events"].append(event)
            current_incident["indices"].append(current_index)
            events_after_error += 1

        if event.event_type == "EXCP":
            if current_incident is not None:
                incidents.append(current_incident)

            previous = list(recent_events)

            current_incident = {
                "events": [item[0] for item in previous] + [event],
                "indices": [item[1] for item in previous] + [current_index],
                "error_index": len(previous),
            }

            events_after_error = 0

        recent_events.append((event, current_index))

    if current_incident is not None:
        incidents.append(current_incident)

    if not incidents:
        return {
            "error": "В журнале не найдено исключений EXCP.",
            "chain": None,
            "evidence": None,
            "incidents": [],
        }

    analyzed_incidents = []

    for item in incidents:
        chain = build_incident_chain(
            item["events"],
            error_index=item["error_index"],
            window=window,
            session_events=session_events,
            error_global_index=item["indices"][item["error_index"]],
        )

        # Преобразуем локальные индексы в глобальные.
        index_map = dict(enumerate(item["indices"]))

        for event in chain["events"] + chain["related_events"]:
            event["index"] = index_map[event["index"]]

        chain["error_index"] = index_map[chain["error_index"]]

        evidence = analyze_incident_evidence(chain)

        analyzed_incidents.append(
            {
                "chain": chain,
                "evidence": evidence,
            }
        )

    last = analyzed_incidents[-1]

    return {
        "error": None,
        "chain": last["chain"],
        "evidence": last["evidence"],
        "incidents": analyzed_incidents,
    }


def format_correlated_incident(incident: dict) -> str:
    """Формирует отчёт с основной цепочкой и сопутствующими событиями."""

    if incident.get("error"):
        return incident["error"]

    chain = incident["chain"]
    evidence = incident["evidence"]

    target = next(
        event
        for event in chain["events"]
        if event["event_type"] == "EXCP" and event["index"] == chain["error_index"]
    )

    lines = [
        "РАЗБОР ИНЦИДЕНТА 1С",
        "=" * 60,
        f"Время ошибки: {target['timestamp']}",
        f"Тип события: {target['event_type']}",
        f"Пользователь: {chain['user'] or 'Не определён'}",
        f"Процесс: {chain['process'] or 'Не определён'}",
        f"Поток: {chain['thread'] or 'Не определён'}",
        f"Контекст: {chain['context'] or 'Не определён'}",
        f"Описание: {target['description']}",
    ]

    for label, key in (
        ("Категория исключения", "exception_category"),
        ("Деталь исключения", "exception_detail"),
        ("GUID", "exception_guid"),
        ("Ресурс", "exception_resource"),
    ):
        value = target.get(key)
        if value:
            lines.append(f"{label}: {value}")

    lines.extend(
        [
            "",
            "ОСНОВНЫЕ ДИАГНОСТИЧЕСКИЕ ПРИЗНАКИ",
            "-" * 60,
        ]
    )

    for finding in evidence["findings"]:
        lines.append(
            f"{finding['title']} "
            f"(событий: {finding['count']}, "
            f"оценка: {finding['confidence']})"
        )

    lines.extend(
        [
            "",
            "СОПУТСТВУЮЩИЕ СОБЫТИЯ ДРУГИХ ПОТОКОВ",
            "-" * 60,
        ]
    )

    if evidence["related_findings"]:
        for finding in evidence["related_findings"]:
            lines.append(f"{finding['event_type']}: {finding['count']} событий")

            for event in finding["events"]:
                lines.append(
                    f"    {event['timestamp']} | "
                    f"Поток: {event['thread']} | "
                    f"{event.get('sql_type', event['event_type'])}"
                )
    else:
        lines.append("Сопутствующие события не обнаружены.")

    lines.extend(
        [
            "",
            "Примечание: временная близость событий не доказывает",
            "причинно-следственную связь. Сопутствующие события",
            "показаны отдельно и не входят в основную цепочку.",
        ]
    )

    return "\n".join(lines)
