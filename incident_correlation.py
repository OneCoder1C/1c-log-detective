from techlog import extract_fields, parse_lock_event
from exception_groups import (
    extract_exception_resource,
    extract_guid,
    get_exception_detail,
    normalize_exception,
)
from sql_analysis import extract_sql, extract_sql_tables, extract_rows, get_sql_type

SUPPORTED_EVENT_TYPES = {"EXCP", "TLOCK", "SDBL", "DBV8DBEng"}


def _safe_text(value) -> str:
    """Возвращает строковое значение или пустую строку."""
    return value.strip() if isinstance(value, str) else ""


def get_correlation_fields(event) -> dict:
    """Извлекает поля, необходимые для корреляции событий."""

    fields = extract_fields(event.raw_text)

    return {
        "user": _safe_text(fields.get("Usr")),
        "process": _safe_text(fields.get("process")),
        "thread": _safe_text(fields.get("OSThread")),
        "context": _safe_text(fields.get("Context")),
    }


def is_same_process_thread(anchor: dict, candidate: dict) -> bool:
    """Проверяет совпадение процесса и потока."""
    return (
        bool(anchor["process"])
        and bool(anchor["thread"])
        and candidate["process"] == anchor["process"]
        and candidate["thread"] == anchor["thread"]
    )


def is_same_execution(anchor: dict, candidate: dict) -> bool:
    """Проверяет принадлежность событий одному исполнению."""

    if not is_same_process_thread(anchor, candidate):
        return False

    # Если оба пользователя известны, они должны совпадать.
    if anchor["user"] and candidate["user"]:
        return anchor["user"] == candidate["user"]

    # Если хотя бы один пользователь неизвестен,
    # совпадение процесса и потока позволяет оставить событие
    # как контекстное, но не подтверждает пользователя.
    return True


def build_incident_chain(
    events: list,
    error_index: int,
    window: int = 20,
) -> dict:
    """Строит цепочку событий вокруг EXCP с учётом границ инцидентов."""

    if not 0 <= error_index < len(events):
        raise IndexError("Индекс события находится за пределами списка.")

    if not isinstance(window, int) or isinstance(window, bool):
        raise TypeError("Размер окна должен быть целым числом.")

    if window < 0:
        raise ValueError("Размер окна не может быть отрицательным.")
    error_event = events[error_index]

    if error_event.event_type != "EXCP":
        raise ValueError("Центральное событие должно иметь тип EXCP.")

    anchor = get_correlation_fields(error_event)

    # Определяем левую границу с учётом предыдущего исключения.
    start_index = max(0, error_index - window)

    for index in range(error_index - 1, start_index - 1, -1):
        event = events[index]
        fields = get_correlation_fields(event)

        if event.event_type == "EXCP" and is_same_process_thread(anchor, fields):
            start_index = error_index
            break

    # Определяем правую границу: ближайшее следующее
    # исключение в том же процессе и потоке.
    end_index = min(len(events), error_index + window + 1)

    for index in range(error_index + 1, end_index):
        event = events[index]
        fields = get_correlation_fields(event)

        if event.event_type == "EXCP" and is_same_process_thread(anchor, fields):
            end_index = index
            break

    selected_indices = []

    for index in range(start_index, end_index):
        if index == error_index:
            selected_indices.append(index)
            continue

        event = events[index]

        if event.event_type not in SUPPORTED_EVENT_TYPES:
            continue

        fields = get_correlation_fields(event)

        if is_same_execution(anchor, fields):
            selected_indices.append(index)

    chain = []

    for index in selected_indices:
        event = events[index]
        fields = get_correlation_fields(event)

        user_relation = (
            "same" if anchor["user"] and anchor["user"] == fields["user"] else "unknown"
        )
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
            "user_relation": user_relation,
            "is_error": index == error_index,
        }

        item.update(extract_event_details(event))
        chain.append(item)
    # Дополнительные события того же пользователя и процесса,
    # но из других потоков.
    related_events = []
    for index in range(
        max(0, error_index - window),
        min(len(events), error_index + window + 1),
    ):
        if index == error_index:
            continue

        event = events[index]

        if event.event_type not in SUPPORTED_EVENT_TYPES:
            continue

        fields = get_correlation_fields(event)

        same_process = (
            bool(anchor["process"]) and fields["process"] == anchor["process"]
        )

        same_known_user = bool(anchor["user"]) and fields["user"] == anchor["user"]

        different_thread = (
            bool(fields["thread"]) and fields["thread"] != anchor["thread"]
        )

        if same_process and same_known_user and different_thread:
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
                "user_relation": "same",
                "is_error": False,
            }

            item.update(extract_event_details(event))
            related_events.append(item)

    related_before = [item for item in related_events if item["index"] < error_index]

    related_after = [item for item in related_events if item["index"] > error_index]

    return {
        "user": anchor["user"],
        "process": anchor["process"],
        "thread": anchor["thread"],
        "context": anchor["context"],
        "error_index": error_index,
        "events": chain,
        "before": [item for item in chain if item["index"] < error_index],
        "after": [item for item in chain if item["index"] > error_index],
        "related_events": related_events,
        "related_before": related_before,
        "related_after": related_after,
    }


def extract_event_details(event) -> dict:
    """Извлекает специализированные данные события."""

    details = {}

    if event.event_type == "EXCP":
        description = event.description or ""
        details["exception_category"] = normalize_exception(description)
        details["exception_detail"] = get_exception_detail(description)
        details["exception_guid"] = extract_guid(description)
        details["exception_resource"] = extract_exception_resource(description)

    elif event.event_type == "TLOCK":
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


def analyze_incident_evidence(chain: dict) -> dict:
    """Выделяет диагностические признаки и сопутствующий контекст."""

    before = chain["before"]
    after = chain["after"]

    related_before = chain.get("related_before", [])
    related_after = chain.get("related_after", [])

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

    related_events = related_before + related_after

    related_findings = []

    for event_type in event_types:
        matched_events = [
            event for event in related_events if event["event_type"] == event_type
        ]

        if matched_events:
            related_findings.append(
                {
                    "event_type": event_type,
                    "count": len(matched_events),
                    "events": matched_events,
                }
            )

    return {
        "findings": findings,
        "related_findings": related_findings,
        "related_events_count": len(related_events),
        "has_lock_events_before": bool(before_events["TLOCK"]),
        "has_sql_events_before": bool(before_events["SDBL"]),
        "has_dbv8dbeng_events_before": bool(before_events["DBV8DBEng"]),
        "has_events_after": bool(after),
    }
