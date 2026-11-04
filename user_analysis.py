from collections import Counter
from pathlib import Path

from techlog import extract_fields, iter_techlog_events, parse_event

SUPPORTED_EVENT_TYPES = {"EXCP", "TLOCK", "SDBL"}


def get_event_user(event) -> str:
    """Возвращает пользователя из события технологического журнала."""
    return extract_fields(event.raw_text).get("Usr", "").strip()


def analyze_user_events(
    log_file: str | Path,
    user: str | None = None,
    event_types: set[str] | None = None,
) -> dict:
    """Потоково анализирует события выбранного пользователя."""

    selected_types = (
        {item.upper() for item in event_types}
        if event_types is not None
        else SUPPORTED_EVENT_TYPES
    )

    if not selected_types.issubset(SUPPORTED_EVENT_TYPES):
        raise ValueError("Поддерживаются только EXCP, TLOCK и SDBL.")

    by_type = Counter()
    users = Counter()
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

            if event is None or event.event_type not in selected_types:
                continue

            event_user = get_event_user(event)

            if event_user:
                users[event_user] += 1

            if user is not None and event_user != user:
                continue

            total_events += 1
            by_type[event.event_type] += 1

            if event.event_type == "EXCP":
                exceptions += 1

            matched_events += 1

    return {
        "user": user,
        "total_events": total_events,
        "matched_events": matched_events,
        "by_type": dict(by_type),
        "exceptions": exceptions,
        "users": dict(users),
    }


def format_user_analysis(result: dict) -> str:
    """Формирует текстовый отчёт по пользователям."""

    lines = [
        "АНАЛИЗ СОБЫТИЙ ПОЛЬЗОВАТЕЛЕЙ 1С",
        "=" * 60,
    ]

    if result["user"] is not None:
        lines.append(f"Пользователь: {result['user']}")
    else:
        lines.append("Пользователь: все")

    lines.extend(
        [
            f"Всего событий: {result['total_events']}",
            f"Исключений EXCP: {result['exceptions']}",
            "",
            "СОБЫТИЯ ПО ТИПАМ",
            "-" * 60,
        ]
    )

    for event_type, count in sorted(result["by_type"].items()):
        lines.append(f"{event_type}: {count}")

    if result["user"] is None:
        lines.extend(
            [
                "",
                "ПОЛЬЗОВАТЕЛИ",
                "-" * 60,
            ]
        )

        for name, count in sorted(
            result["users"].items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            lines.append(f"{name}: {count}")

    return "\n".join(lines)
