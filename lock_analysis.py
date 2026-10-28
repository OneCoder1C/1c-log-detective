from datetime import datetime

from techlog import parse_lock_event
from exception_groups import normalize_exception


def analyze_lock_incident(
    lock_events: list[str],
    exception_events: list[str],
) -> dict:
    """Собирает сведения о блокировках и исключениях."""

    locks = []

    for raw_event in lock_events:
        lock = parse_lock_event(raw_event)

        if lock is not None:
            locks.append(lock)

    exceptions = []

    for raw_event in exception_events:
        category = normalize_exception(raw_event)

        if category != "Не удалось заблокировать запись":
            continue

        exceptions.append(
            {
                "category": category,
                "description": raw_event,
            }
        )

    return {
        "lock_events_count": len(locks),
        "lock_exceptions_count": len(exceptions),
        "locks": locks,
        "exceptions": exceptions,
    }


def parse_event_time(timestamp: str) -> float | None:
    """Преобразует время ТЖ в секунды от начала часа."""

    time_part = timestamp.split("-", 1)[0]

    try:
        parsed = datetime.strptime(time_part, "%M:%S.%f")
    except ValueError:
        return None

    return parsed.minute * 60 + parsed.second + parsed.microsecond / 1_000_000


def find_lock_candidates(
    lock_events: list[dict],
    exception_time: str,
    exception_thread: str,
    window_ms: int = 1000,
) -> list[dict]:
    """Ищет блокировки того же потока, произошедшие до исключения."""

    target_time = parse_event_time(exception_time)

    if target_time is None:
        return []

    candidates = []

    for lock in lock_events:
        if lock.get("thread") != exception_thread:
            continue

        lock_time = parse_event_time(lock.get("timestamp", ""))

        if lock_time is None:
            continue

        # Положительная разница означает, что блокировка была раньше.
        difference_ms = (target_time - lock_time) * 1000

        # Не учитываем блокировки, случившиеся после исключения.
        if difference_ms < 0:
            continue

        if difference_ms <= window_ms:
            candidate = lock.copy()
            candidate["time_difference_ms"] = round(difference_ms, 3)
            candidates.append(candidate)

    return sorted(
        candidates,
        key=lambda item: item["time_difference_ms"],
    )


def summarize_lock_candidates(candidates: list[dict]) -> dict:
    """Формирует сводку и объясняет основания совпадения."""

    if not candidates:
        return {
            "candidate_count": 0,
            "summary": "В заданном временном окне кандидаты не найдены.",
            "candidates": [],
        }

    for candidate in candidates:
        candidate["match_strength"] = "Слабое совпадение"
        candidate["match_basis"] = [
            "Совпадает поток",
            "Событие произошло до исключения",
            "Событие попало во временное окно",
        ]
        candidate["match_reason"] = (
            "Совпали поток и временное окно. "
            "Соответствие ресурса исключению не установлено. "
            "Причинная связь не подтверждена."
        )

    return {
        "candidate_count": len(candidates),
        "summary": (
            "Найдены события того же потока в допустимом "
            "временном окне. Соответствие ресурсов не установлено; "
            "причинная связь не подтверждена."
        ),
        "candidates": candidates,
    }
