from techlog import extract_fields, parse_lock_event
from sql_analysis import extract_sql, extract_sql_tables, extract_rows, get_sql_type

SUPPORTED_EVENT_TYPES = {"EXCP", "TLOCK", "SDBL", "DBV8DBEng"}


def get_correlation_fields(event) -> dict:
    """Извлекает поля, необходимые для корреляции событий."""

    fields = extract_fields(event.raw_text)

    return {
        "user": fields.get("Usr", "").strip(),
        "process": fields.get("process", "").strip(),
        "thread": fields.get("OSThread", "").strip(),
        "context": fields.get("Context", "").strip(),
    }


def is_same_execution(anchor: dict, candidate: dict) -> bool:
    """Проверяет, относятся ли события к одному процессу и потоку."""

    if not anchor["process"] or not anchor["thread"]:
        return False

    if candidate["process"] != anchor["process"]:
        return False

    if candidate["thread"] != anchor["thread"]:
        return False

    if not candidate["process"] or not candidate["thread"]:
        return False

    if anchor["user"] and candidate["user"]:
        if anchor["user"] != candidate["user"]:
            return False

    return True


def extract_event_details(event) -> dict:
    """Извлекает специализированные данные события."""

    details = {}

    if event.event_type == "TLOCK":
        lock = parse_lock_event(event.raw_text, event)

        if lock is not None:
            details["lock"] = lock

    elif event.event_type in {"SDBL", "DBV8DBEng"}:
        sql = extract_sql(event.raw_text)

        if sql:
            details["sql"] = sql
            details["sql_type"] = get_sql_type(sql)
            details["sql_tables"] = extract_sql_tables(sql)

        if event.event_type == "SDBL":
            details["rows"] = extract_rows(event.raw_text)

    return details


def build_incident_chain(
    events: list,
    error_index: int,
    window: int = 20,
) -> dict:
    """Строит цепочку событий вокруг EXCP."""

    if not 0 <= error_index < len(events):
        raise IndexError("Индекс события находится за пределами списка.")

    if window < 0:
        raise ValueError("Размер окна не может быть отрицательным.")

    error_event = events[error_index]

    if error_event.event_type != "EXCP":
        raise ValueError("Центральное событие должно иметь тип EXCP.")

    anchor = get_correlation_fields(error_event)

    start = max(0, error_index - window)
    end = min(len(events), error_index + window + 1)

    chain = []

    for index in range(start, end):
        event = events[index]

        if event.event_type not in SUPPORTED_EVENT_TYPES:
            continue

        fields = get_correlation_fields(event)

        if not is_same_execution(anchor, fields):
            continue

        item = {
            "index": index,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "level": event.level,
            "description": event.description,
            "user": fields["user"],
            "process": fields["process"],
            "thread": fields["thread"],
            "context": fields["context"],
            "is_error": index == error_index,
        }

        item.update(extract_event_details(event))
        chain.append(item)

    return {
        "user": anchor["user"],
        "process": anchor["process"],
        "thread": anchor["thread"],
        "context": anchor["context"],
        "error_index": error_index,
        "events": chain,
        "before": [item for item in chain if item["index"] < error_index],
        "after": [item for item in chain if item["index"] > error_index],
    }


def analyze_incident_evidence(chain: dict) -> dict:
    """Выделяет диагностические признаки вокруг исключения."""

    before = chain["before"]
    after = chain["after"]

    event_types = ("TLOCK", "SDBL", "DBV8DBEng")

    before_events = {
        event_type: [event for event in before if event["event_type"] == event_type]
        for event_type in event_types
    }

    after_events = {
        event_type: [event for event in after if event["event_type"] == event_type]
        for event_type in event_types
    }

    findings = []

    finding_definitions = [
        (
            "TLOCK_BEFORE_EXCP",
            "Перед исключением обнаружены события TLOCK",
            "TLOCK",
            before_events,
            "Признак",
        ),
        (
            "SDBL_BEFORE_EXCP",
            "Перед исключением обнаружены SQL-события SDBL",
            "SDBL",
            before_events,
            "Признак",
        ),
        (
            "DBV8DBENG_BEFORE_EXCP",
            "Перед исключением обнаружены SQL-события DBV8DBEng",
            "DBV8DBEng",
            before_events,
            "Признак",
        ),
        (
            "TLOCK_AFTER_EXCP",
            "После исключения обнаружены события TLOCK",
            "TLOCK",
            after_events,
            "Контекст",
        ),
        (
            "SDBL_AFTER_EXCP",
            "После исключения обнаружены SQL-события SDBL",
            "SDBL",
            after_events,
            "Контекст",
        ),
        (
            "DBV8DBENG_AFTER_EXCP",
            "После исключения обнаружены SQL-события DBV8DBEng",
            "DBV8DBEng",
            after_events,
            "Контекст",
        ),
    ]

    for code, title, event_type, source, confidence in finding_definitions:
        matched_events = source[event_type]

        if matched_events:
            findings.append(
                {
                    "code": code,
                    "title": title,
                    "count": len(matched_events),
                    "confidence": confidence,
                    "events": matched_events,
                }
            )

    if not findings:
        findings.append(
            {
                "code": "NO_ADDITIONAL_EVIDENCE",
                "title": "Дополнительные признаки не обнаружены",
                "count": 0,
                "confidence": "Недостаточно данных",
                "events": [],
            }
        )

    return {
        "findings": findings,
        "has_lock_events_before": bool(before_events["TLOCK"]),
        "has_sql_events_before": bool(before_events["SDBL"]),
        "has_dbv8dbeng_events_before": bool(before_events["DBV8DBEng"]),
        "has_events_after": bool(after),
    }
