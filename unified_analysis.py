from collections import Counter

from techlog import iter_techlog_events, parse_event, parse_lock_event


def analyze_techlog_file(file_path: str) -> dict:
    """Потоково собирает общую статистику технологического журнала."""

    by_type = Counter()
    by_level = Counter()

    total_events = 0
    lock_events = []
    lock_exceptions = []

    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        for raw_text in iter_techlog_events(file):
            event = parse_event(raw_text)

            if event is None:
                continue

            total_events += 1
            by_type[event.event_type] += 1
            by_level[event.level] += 1

            if event.event_type == "TLOCK":
                lock = parse_lock_event(raw_text)

                if lock is not None:
                    lock_events.append(lock)

            elif event.event_type == "EXCP":
                if "Не удалось заблокировать запись" in event.description:
                    lock_exceptions.append(raw_text)

    return {
        "total_events": total_events,
        "by_type": dict(by_type),
        "by_level": dict(by_level),
        "lock_events": lock_events,
        "lock_exceptions": lock_exceptions,
    }
