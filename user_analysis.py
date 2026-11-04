from collections import Counter
from pathlib import Path

from techlog import extract_fields, iter_techlog_events, parse_event

from sql_analysis import extract_sql, extract_sql_tables, get_sql_type

SUPPORTED_EVENT_TYPES = {
    "EXCP",
    "TLOCK",
    "SDBL",
    "DBV8DBENG",
    "SESN",
}


def get_event_user(event) -> str:
    """Возвращает пользователя из события технологического журнала."""
    return extract_fields(event.raw_text).get("Usr", "").strip()


def analyze_user_events(
    log_file: str | Path,
    user: str | None = None,
    event_types: set[str] | None = None,
) -> dict:
    """Потоково анализирует события и строит историю выбранного пользователя."""

    selected_types = (
        {item.upper() for item in event_types}
        if event_types is not None
        else SUPPORTED_EVENT_TYPES
    )

    if not selected_types.issubset(SUPPORTED_EVENT_TYPES):
        raise ValueError(
            f"Поддерживаются только: {', '.join(sorted(SUPPORTED_EVENT_TYPES))}."
        )

    by_type = Counter()
    users = Counter()
    events = []
    total_events = 0
    matched_events = 0
    exceptions = 0

    with Path(log_file).open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as file:
        for raw_text in iter_techlog_events(file):
            event = parse_event(raw_text)

            if event is None or event.event_type.upper() not in selected_types:
                continue

            fields = extract_fields(raw_text)
            event_user = fields.get("Usr", "").strip()

            if event_user:
                users[event_user] += 1

            if user is not None and event_user != user:
                continue

            total_events += 1
            by_type[event.event_type] += 1
            matched_events += 1

            if event.event_type == "EXCP":
                exceptions += 1

            sql_text = extract_sql(raw_text)
            sql_type = get_sql_type(sql_text) if sql_text else None
            sql_tables = extract_sql_tables(sql_text) if sql_text else []

            events.append(
                {
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "level": event.level,
                    "user": event_user,
                    "process": fields.get("process", ""),
                    "thread": fields.get("OSThread", ""),
                    "context": fields.get("Context", "").strip(),
                    "func": fields.get("Func", ""),
                    "description": fields.get("Descr", ""),
                    "sql": fields.get("Sql", ""),
                    "sdbl": fields.get("Sdbl", ""),
                    "locks": fields.get("Locks", ""),
                    "regions": fields.get("Regions", ""),
                    "duration_us": event.duration_us,
                    "sql_type": sql_type,
                    "sql_tables": sql_tables,
                }
            )

    operations = build_operation_summary(events)
    events_without_context = sum(1 for event in events if not event["context"].strip())

    return {
        "user": user,
        "total_events": total_events,
        "matched_events": matched_events,
        "by_type": dict(by_type),
        "exceptions": exceptions,
        "users": dict(users),
        "events": events,
        "operations": operations,
        "events_without_context": events_without_context,
    }


def build_operation_summary(events: list[dict]) -> list[dict]:
    """Группирует события по контексту 1С."""

    operations = {}

    for event in events:
        context_lines = event["context"].splitlines()
        context = next(
            (line.strip() for line in context_lines if line.strip()),
            None,
        )
        # События без контекста не объединяем в одну операцию.
        if not context:
            continue

        if context not in operations:
            operations[context] = {
                "context": context,
                "total_events": 0,
                "sql_types": Counter(),
                "tables": Counter(),
                "locks": 0,
                "exceptions": 0,
                "max_event_duration_us": 0,
            }

        operation = operations[context]
        operation["total_events"] += 1

        if event["sql_type"]:
            operation["sql_types"][event["sql_type"]] += 1

        operation["tables"].update(event["sql_tables"])

        if event["event_type"] == "TLOCK":
            operation["locks"] += 1

        if event["event_type"] == "EXCP":
            operation["exceptions"] += 1

        duration = event["duration_us"]

        if duration is not None:
            operation["max_event_duration_us"] = max(
                operation["max_event_duration_us"],
                duration,
            )

    result = []

    for operation in operations.values():
        operation["sql_types"] = dict(operation["sql_types"])
        operation["tables"] = dict(operation["tables"])
        result.append(operation)

    return sorted(
        result,
        key=lambda item: item["total_events"],
        reverse=True,
    )


def format_user_analysis(result: dict, detail: bool = False) -> str:
    """Формирует краткий или подробный отчёт по активности пользователя."""

    lines = [
        "АНАЛИЗ АКТИВНОСТИ ПОЛЬЗОВАТЕЛЯ 1С",
        "=" * 70,
        f"Пользователь: {result['user'] or 'все'}",
        f"Всего событий: {result['total_events']}",
        f"Исключений EXCP: {result['exceptions']}",
        "",
        "СОБЫТИЯ ПО ТИПАМ",
        "-" * 70,
    ]

    for event_type, count in sorted(result["by_type"].items()):
        lines.append(f"{event_type}: {count}")

    if result["user"] is None:
        lines.extend(["", "ПОЛЬЗОВАТЕЛИ", "-" * 70])

        for name, count in sorted(
            result["users"].items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            lines.append(f"{name}: {count}")

    lines.extend(["", "СВОДКА ПО КОНТЕКСТАМ", "-" * 70])

    lines.append(f"Событий без контекста: {result.get('events_without_context', 0)}")
    operations = result.get("operations", [])

    if not operations:
        lines.append("Контексты не обнаружены.")
    else:
        for index, operation in enumerate(operations[:30], start=1):
            lines.extend(
                [
                    "",
                    f"{index}. {operation['context']}",
                    f"   Событий: {operation['total_events']}",
                    f"   Блокировок TLOCK: {operation['locks']}",
                    f"   Исключений EXCP: {operation['exceptions']}",
                ]
            )

            if operation["sql_types"]:
                sql_summary = ", ".join(
                    f"{name}: {count}"
                    for name, count in sorted(operation["sql_types"].items())
                )
                lines.append(f"   SQL: {sql_summary}")

            if operation["tables"]:
                tables = sorted(
                    operation["tables"].items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10]

                table_summary = ", ".join(f"{name}: {count}" for name, count in tables)
                lines.append(f"   Таблицы: {table_summary}")

            if operation["max_event_duration_us"]:
                lines.append(
                    "   Максимальная длительность отдельного события: "
                    f"{operation['max_event_duration_us']} мкс"
                )

    if len(operations) > 30:
        lines.extend(["", f"Показаны первые 30 из {len(operations)} контекстов."])

    exception_events = [
        event
        for event in result.get("events", [])
        if event["event_type"] == "EXCP"
        and event["level"].upper() in {"ERROR", "CRITICAL"}
    ]

    warning_events = [
        event
        for event in result.get("events", [])
        if event["event_type"] == "EXCP" and event["level"].upper() == "WARNING"
    ]

    lines.extend(["", "ОШИБКИ И ИСКЛЮЧЕНИЯ", "-" * 70])

    if not exception_events:
        lines.append("Ошибок и критических исключений не обнаружено.")
    else:
        for event in exception_events:
            lines.extend(
                [
                    "",
                    f"Время: {event['timestamp']}",
                    f"Уровень: {event['level']}",
                    f"Описание: {event['description'] or 'не указано'}",
                    f"Контекст: {event['context'] or 'не указан'}",
                    f"Поток: {event['thread'] or 'не указан'}",
                    f"Процесс: {event['process'] or 'не указан'}",
                ]
            )

    lines.extend(["", "ПРЕДУПРЕЖДЕНИЯ", "-" * 70])

    if not warning_events:
        lines.append("Предупреждений не обнаружено.")
    else:
        for event in warning_events:
            description = event["description"] or ""

            if (
                "DATAZONEOBJECTLOCKS" in description
                or "Не удалось заблокировать запись" in description
            ):
                category = "Предупреждение блокировки данных"
            else:
                category = "Другое предупреждение"

            lines.extend(
                [
                    "",
                    f"Категория: {category}",
                    f"Время: {event['timestamp']}",
                    f"Описание: {description or 'не указано'}",
                    "Причина: не установлена.",
                    f"Контекст: {event['context'] or 'не указан'}",
                    f"Поток: {event['thread'] or 'не указан'}",
                    f"Процесс: {event['process'] or 'не указан'}",
                ]
            )

    if detail and result.get("events"):
        lines.extend(["", "ПОДРОБНАЯ ИСТОРИЯ СОБЫТИЙ", "-" * 70])

        for event in result["events"]:
            lines.append(
                f"\n{event['timestamp']} | " f"{event['event_type']} | {event['level']}"
            )

            if event["context"]:
                lines.append(f"Контекст: {event['context']}")

            if event["func"]:
                lines.append(f"Функция: {event['func']}")

            if event["description"]:
                lines.append(f"Описание: {event['description']}")

            if event["sql"]:
                lines.append(f"SQL: {event['sql']}")

            if event["sdbl"]:
                lines.append(f"SDBL: {event['sdbl']}")

            if event["locks"]:
                lines.append(f"Блокировки: {event['locks']}")

            if event["regions"]:
                lines.append(f"Области блокировок: {event['regions']}")

            if event["duration_us"] is not None:
                lines.append(f"Длительность: {event['duration_us']} мкс")

    return "\n".join(lines)
