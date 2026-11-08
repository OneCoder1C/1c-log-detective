import re

from techlog import extract_fields, parse_lock_event
from exception_groups import (
    extract_exception_resource,
    extract_guid,
    get_exception_detail,
    normalize_exception,
)
from sql_analysis import extract_sql, extract_sql_tables, extract_rows, get_sql_type

SUPPORTED_EVENT_TYPES = {
    "EXCP",
    "TLOCK",
    "TTIMEOUT",
    "SDBL",
    "DBV8DBEng",
}


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


def _timestamp_to_microseconds(timestamp: str) -> int | None:
    """Преобразует время события ТЖ в микросекунды от начала суток."""

    match = re.match(
        r"^(\d{2}):(\d{2})\.(\d{6})-\d+$",
        timestamp,
    )

    if not match:
        return None

    hours, minutes, microseconds = map(int, match.groups())

    return (hours * 3600 + minutes * 60) * 1_000_000 + microseconds


def _normalize_table_name(table: str) -> str:
    """Нормализует имя таблицы SQL."""

    return table.lstrip("_").lower()


def _extract_select_fields(sql: str) -> set[str]:
    """Извлекает и нормализует поля из всех ветвей SELECT, включая UNION ALL."""

    result = set()

    # Каждый SELECT в UNION ALL обрабатываем отдельно.
    branches = re.split(r"\bUNION(?:\s+ALL)?\b", sql, flags=re.IGNORECASE)

    for branch in branches:
        match = re.search(
            r"\bSELECT\b(.*?)\bFROM\b",
            branch,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            continue

        for expression in match.group(1).split(","):
            expression = expression.strip()

            if not expression:
                continue

            # Пропускаем шестнадцатеричные константы.
            if re.fullmatch(r"0x[0-9a-f]+", expression, re.IGNORECASE):
                continue

            # Убираем псевдоним поля: Field Alias.
            expression = expression.split()[0]

            # Убираем алиас таблицы: T1._Fld84491 -> _Fld84491.
            field = expression.split(".")[-1].strip()

            # Нормализуем имя поля.
            field = field.lstrip("_").lower()

            # Физическое поле IDRRef соответствует логическому ID.
            if field == "idrref":
                field = "id"

            if field:
                result.add(field)

    return result


def find_sql_event_pairs(
    events,
    max_interval_us: int = 10_000,
) -> list[dict]:
    """Находит вероятные пары SQL-событий DBV8DBEng и SDBL."""

    db_events = []
    sdbl_events = []

    for index, event in enumerate(events):
        if event.event_type not in {"DBV8DBEng", "SDBL"}:
            continue

        sql = extract_sql(event.raw_text)
        if not sql:
            continue

        sql_type = get_sql_type(sql)
        tables = {_normalize_table_name(table) for table in extract_sql_tables(sql)}
        select_fields = _extract_select_fields(sql) if sql_type == "SELECT" else set()

        if sql_type == "OTHER" or not tables:
            continue

        fields = get_correlation_fields(event)
        timestamp_us = _timestamp_to_microseconds(event.timestamp)

        if not fields["process"] or not fields["thread"] or timestamp_us is None:
            continue

        item = {
            "index": index,
            "timestamp": event.timestamp,
            "process": fields["process"],
            "thread": fields["thread"],
            "user": fields["user"],
            "sql_type": sql_type,
            "tables": tables,
            "timestamp_us": timestamp_us,
            "select_fields": select_fields,
        }

        if event.event_type == "DBV8DBEng":
            db_events.append(item)
        else:
            sdbl_events.append(item)

    candidates = []

    for db_event in db_events:
        for sdbl_event in sdbl_events:
            if (
                db_event["process"] != sdbl_event["process"]
                or db_event["thread"] != sdbl_event["thread"]
            ):
                continue

            if (
                db_event["user"]
                and sdbl_event["user"]
                and db_event["user"] != sdbl_event["user"]
            ):
                continue

            if db_event["sql_type"] != sdbl_event["sql_type"]:
                continue

            if db_event["sql_type"] == "SELECT":
                if not db_event["select_fields"] or not sdbl_event["select_fields"]:
                    continue

                if db_event["select_fields"] != sdbl_event["select_fields"]:
                    continue

            if db_event["tables"] != sdbl_event["tables"]:
                continue

            interval_us = abs(db_event["timestamp_us"] - sdbl_event["timestamp_us"])

            if interval_us > max_interval_us:
                continue

            candidates.append(
                {
                    "db_index": db_event["index"],
                    "sdbl_index": sdbl_event["index"],
                    "db_timestamp": db_event["timestamp"],
                    "sdbl_timestamp": sdbl_event["timestamp"],
                    "process": db_event["process"],
                    "thread": db_event["thread"],
                    "sql_type": db_event["sql_type"],
                    "tables": sorted(db_event["tables"]),
                    "interval_us": interval_us,
                    "correlation_strength": "weak",
                    "correlation_reason": (
                        "Совпадают процесс, поток, тип SQL и таблицы; "
                        "события зарегистрированы с небольшим интервалом."
                    ),
                }
            )

    candidates.sort(key=lambda pair: pair["interval_us"])

    result = []
    used_db = set()
    used_sdbl = set()

    for pair in candidates:
        if pair["db_index"] in used_db or pair["sdbl_index"] in used_sdbl:
            continue

        used_db.add(pair["db_index"])
        used_sdbl.add(pair["sdbl_index"])
        result.append(pair)

    return result


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


def find_background_session(events: list, error_index: int, anchor: dict):
    """Находит фоновый сеанс, активный в момент исключения."""

    indexed_events = []

    for index, item in enumerate(events):
        if isinstance(item, tuple) and len(item) == 2:
            event, event_index = item
        else:
            event, event_index = item, index

        indexed_events.append((event, event_index))

    starts = []

    for event, event_index in indexed_events:
        if event_index >= error_index:
            continue

        if event.event_type != "SESN":
            continue

        fields = extract_fields(event.raw_text)

        if fields.get("Func") != "Start":
            continue

        if fields.get("Appl") != "BackgroundJob":
            continue

        if (
            fields.get("process") != anchor["process"]
            or fields.get("OSThread") != anchor["thread"]
        ):
            continue

        session_id = _safe_text(fields.get("ID"))

        if session_id:
            starts.append((event, event_index, fields))

    # Сначала проверяем ближайший к исключению Start.
    for start_event, start_index, start_fields in reversed(starts):
        session_id = _safe_text(start_fields.get("ID"))

        for finish_event, finish_index in indexed_events:
            if finish_index <= error_index:
                continue

            if finish_event.event_type != "SESN":
                continue

            fields = extract_fields(finish_event.raw_text)

            if (
                fields.get("Func") == "Finish"
                and fields.get("ID") == session_id
                and fields.get("process") == anchor["process"]
                and fields.get("OSThread") == anchor["thread"]
                and fields.get("Nmb") == start_fields.get("Nmb")
                and fields.get("Appl") == start_fields.get("Appl")
            ):
                return {
                    "id": session_id,
                    "nmb": start_fields.get("Nmb", ""),
                    "appl": start_fields.get("Appl", ""),
                    "start_index": start_index,
                    "finish_index": finish_index,
                    "start_timestamp": start_event.timestamp,
                    "finish_timestamp": finish_event.timestamp,
                }

    return None


def build_incident_chain(
    events: list,
    error_index: int,
    window: int = 20,
    session_events: list | None = None,
    error_global_index: int | None = None,
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

    background_session = find_background_session(
        session_events if session_events is not None else events,
        error_global_index if error_global_index is not None else error_index,
        anchor,
    )

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
            "raw_text": event.raw_text,
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

        sql = extract_sql(event.raw_text)

        if sql and sql.strip().lower() in {
            "schema set local 1;",
            "schema get local",
        }:
            continue

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
                "raw_text": event.raw_text,
                "user": fields["user"],
                "process": fields["process"],
                "thread": fields["thread"],
                "context": fields["context"],
                "user_relation": "same",
                "is_error": False,
                "correlation_reason": (
                    "Совпадают пользователь и процесс; "
                    "событие зарегистрировано в другом потоке."
                ),
                "correlation_strength": "weak",
            }

            item.update(extract_event_details(event))
            related_events.append(item)

    related_before = [item for item in related_events if item["index"] < error_index]

    related_after = [item for item in related_events if item["index"] > error_index]

    return {
        "user": anchor["user"],
        "process": anchor["process"],
        "thread": anchor["thread"],
        "background_session": background_session,
        "context": anchor["context"],
        "error_index": error_index,
        "events": chain,
        "diagnostic_links": build_diagnostic_links(chain),
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


def build_diagnostic_links(chain: list[dict]) -> list[dict]:
    """Находит диагностические связи с подтверждённым совпадением ресурса."""

    diagnostic_links = []

    for lock_event in chain:
        if lock_event["event_type"] != "TLOCK":
            continue

        lock = lock_event.get("lock")

        if not lock:
            continue

        regions = lock.get("regions", "")

        if not regions:
            continue

        lock_resources = {
            value.lstrip("_").split(".", maxsplit=1)[0].casefold()
            for value in re.findall(
                r"\b_?[A-Za-z][A-Za-z0-9_]*",
                regions,
            )
        }

        if not lock_resources:
            continue

        candidates = []

        for operation in chain:
            if operation["event_type"] != "DBV8DBEng":
                continue

            if operation["index"] >= lock_event["index"]:
                continue

            if (
                operation["process"] != lock_event["process"]
                or operation["thread"] != lock_event["thread"]
            ):
                continue

            if (
                operation["user"]
                and lock_event["user"]
                and operation["user"] != lock_event["user"]
            ):
                continue

            fields = extract_fields(operation["raw_text"])
            func = fields.get("Func", "")

            match = re.search(
                r"xlockTables\s*\(\s*(_?[A-Za-z][A-Za-z0-9_]*)",
                func,
                re.IGNORECASE,
            )

            if not match:
                continue

            resource = match.group(1).lstrip("_").casefold()

            if resource not in lock_resources:
                continue

            candidates.append((operation, resource))

        if not candidates:
            continue

        operation, resource = max(
            candidates,
            key=lambda item: item[0]["index"],
        )

        diagnostic_links.append(
            {
                "from_index": operation["index"],
                "to_index": lock_event["index"],
                "link_type": "LOCK_OPERATION",
                "resource": resource,
                "confidence": "high",
                "causal": False,
                "explanation": (
                    f"Вызов xlockTables для ресурса {resource} "
                    "совпадает с ресурсом в событии TLOCK. "
                    "Это подтверждает связь операции с захватом "
                    "блокировки, но не доказывает причину исключения."
                ),
            }
        )

    return diagnostic_links


def analyze_incident_evidence(chain: dict) -> dict:
    """Выделяет диагностические признаки и сопутствующий контекст."""

    before = chain["before"]
    after = chain["after"]

    related_before = chain.get("related_before", [])
    related_after = chain.get("related_after", [])

    event_types = ("TLOCK", "TTIMEOUT", "SDBL", "DBV8DBEng")

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
    # Поиск повторяющейся последовательности перед DATAZONEOBJECTLOCKS.
    error_index = chain.get("error_index")
    chain_events = chain.get("events", [])

    error_event = None

    if error_index is not None:
        error_event = next(
            (event for event in chain_events if event.get("index") == error_index),
            None,
        )

    if error_event is None:
        error_event = next(
            (event for event in chain_events if event.get("is_error")),
            None,
        )

    datazone_pattern_found = False

    if (
        error_event is not None
        and error_event.get("exception_resource") == "DATAZONEOBJECTLOCKS"
    ):
        extension_events = []
        schema_storage_events = []
        generation_events = []
        local_schema_events = []

        for event in before:
            sql = event.get("sql", "")

            if not sql:
                continue

            if re.search(r"\b_?ExtensionsInfo(?:NGS)?\b", sql, re.IGNORECASE):
                extension_events.append(event)

            if re.search(r"\bSchemaStorage\b", sql, re.IGNORECASE):
                schema_storage_events.append(event)

            if re.search(r"\bGET\s+NGENERATIONS\b", sql, re.IGNORECASE):
                generation_events.append(event)

            if re.search(r"\bschema\s+get\s+local\b", sql, re.IGNORECASE):
                local_schema_events.append(event)

        if all(
            (
                extension_events,
                schema_storage_events,
                generation_events,
                local_schema_events,
            )
        ):
            matched_events = (
                extension_events
                + schema_storage_events
                + generation_events
                + local_schema_events
                + [error_event]
            )

            # Убираем возможные дубли и сохраняем хронологию.
            matched_events = sorted(
                {event["index"]: event for event in matched_events}.values(),
                key=lambda event: event["index"],
            )

            datazone_pattern_found = True

            findings.append(
                {
                    "code": "DATAZONEOBJECTLOCKS_LOCK_FAILURE",
                    "title": (
                        "Перед исключением обнаружена последовательность "
                        "операций получения локальной схемы"
                    ),
                    "count": len(matched_events),
                    "confidence": "Наблюдаемая закономерность",
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

    if datazone_pattern_found:
        probable_cause = (
            "Перед исключением обнаружена последовательность SQL-операций, "
            "связанных с получением локальной схемы: ExtensionsInfo, "
            "SchemaStorage, GET NGENERATIONS и schema get local. "
            "Возможна проблема в процессе получения локальной схемы, "
            "но причинная связь с отказом блокировки DATAZONEOBJECTLOCKS "
            "не подтверждена."
        )
        cause_confidence = "Низкая"
    else:
        probable_cause = "Причина не установлена по имеющимся событиям."
        cause_confidence = "Недостаточно данных"

    return {
        "findings": findings,
        "related_findings": related_findings,
        "related_events_count": len(related_events),
        "has_lock_events_before": bool(before_events["TLOCK"]),
        "has_sql_events_before": bool(before_events["SDBL"]),
        "has_dbv8dbeng_events_before": bool(before_events["DBV8DBEng"]),
        "has_events_after": bool(after),
        "probable_cause": probable_cause,
        "confidence": cause_confidence,
    }
