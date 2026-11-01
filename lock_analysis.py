import re

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


def calculate_exception_intervals(timestamps: list[str]) -> dict:
    """Рассчитывает интервалы между последовательными исключениями."""

    timed_values = []

    for timestamp in timestamps:
        seconds = parse_event_time(timestamp)

        if seconds is not None:
            timed_values.append(seconds)

    intervals_ms = []
    hour_offset = 0
    previous_seconds = None
    previous_elapsed_seconds = None

    for current_seconds in timed_values:
        # Определяем переход через границу часа.
        if previous_seconds is not None and previous_seconds - current_seconds > 1800:
            hour_offset += 3600

        elapsed_seconds = current_seconds + hour_offset

        if previous_elapsed_seconds is not None:
            interval_ms = (elapsed_seconds - previous_elapsed_seconds) * 1000

            if interval_ms >= 0:
                intervals_ms.append(interval_ms)

        previous_seconds = current_seconds
        previous_elapsed_seconds = elapsed_seconds

    interval_ranges = {
        "up_to_10_ms": sum(value < 10 for value in intervals_ms),
        "10_to_100_ms": sum(10 <= value < 100 for value in intervals_ms),
        "100_to_1000_ms": sum(100 <= value < 1000 for value in intervals_ms),
        "1_to_10_seconds": sum(1000 <= value < 10000 for value in intervals_ms),
        "over_10_seconds": sum(value >= 10000 for value in intervals_ms),
    }

    if not intervals_ms:
        return {
            "interval_count": 0,
            "min_ms": None,
            "max_ms": None,
            "average_ms": None,
            "up_to_100_ms": 0,
            "up_to_1000_ms": 0,
            "interval_ranges": interval_ranges,
        }

    return {
        "interval_count": len(intervals_ms),
        "min_ms": min(intervals_ms),
        "max_ms": max(intervals_ms),
        "average_ms": sum(intervals_ms) / len(intervals_ms),
        "up_to_100_ms": sum(value <= 100 for value in intervals_ms),
        "up_to_1000_ms": sum(value <= 1000 for value in intervals_ms),
        "interval_ranges": interval_ranges,
    }


def find_exception_series(
    timestamps: list[str],
    max_gap_ms: int = 1000,
    min_events: int = 3,
) -> list[dict]:
    """Находит серии исключений с небольшими интервалами между событиями."""

    timed_events = []

    hour_offset = 0
    previous_seconds = None

    for timestamp in timestamps:
        current_seconds = parse_event_time(timestamp)

        if current_seconds is None:
            continue

        if previous_seconds is not None and previous_seconds - current_seconds > 1800:
            hour_offset += 3600

        elapsed_seconds = current_seconds + hour_offset

        timed_events.append(
            {
                "timestamp": timestamp,
                "elapsed_seconds": elapsed_seconds,
            }
        )

        previous_seconds = current_seconds

    series = []
    current_series = []

    for event in timed_events:
        if not current_series:
            current_series.append(event)
            continue

        gap_ms = (
            event["elapsed_seconds"] - current_series[-1]["elapsed_seconds"]
        ) * 1000

        if 0 <= gap_ms <= max_gap_ms:
            current_series.append(event)
        else:
            if len(current_series) >= min_events:
                series.append(_build_exception_series(current_series))

            current_series = [event]

    if len(current_series) >= min_events:
        series.append(_build_exception_series(current_series))

    return series


def _build_exception_series(events: list[dict]) -> dict:
    """Формирует сводку по одной серии исключений."""

    gaps_ms = [
        (events[index]["elapsed_seconds"] - events[index - 1]["elapsed_seconds"]) * 1000
        for index in range(1, len(events))
    ]

    return {
        "event_count": len(events),
        "start_timestamp": events[0]["timestamp"],
        "end_timestamp": events[-1]["timestamp"],
        "duration_ms": round(
            (events[-1]["elapsed_seconds"] - events[0]["elapsed_seconds"]) * 1000,
            3,
        ),
        "max_gap_ms": round(max(gaps_ms), 3),
    }


def find_lock_candidates(
    lock_events: list[dict],
    exception_time: str,
    exception_thread: str,
    window_ms: int = 1000,
    exception_description: str = "",
) -> list[dict]:
    """Ищет блокировки того же потока, произошедшие до исключения."""

    target_time = parse_event_time(exception_time)

    if target_time is None:
        return []

    object_match = re.search(
        r"""не выполнено\s+['"]([^'"]+)['"]""",
        exception_description,
        re.IGNORECASE,
    )
    exception_resource = object_match.group(1).strip() if object_match else ""

    candidates = []

    for lock in lock_events:
        if lock.get("thread") != exception_thread:
            continue

        lock_time = parse_event_time(lock.get("timestamp", ""))

        if lock_time is None:
            continue

        # Не учитываем блокировки, случившиеся после исключения.
        difference_seconds = (target_time - lock_time) % 3600
        difference_ms = difference_seconds * 1000

        if difference_ms > window_ms:
            continue

        candidate = lock.copy()
        candidate["time_difference_ms"] = round(difference_ms, 3)

        lock_regions = candidate.get("regions", "")
        candidate["exception_resource"] = exception_resource
        candidate["resource_match"] = (
            bool(exception_resource)
            and exception_resource.casefold() in lock_regions.casefold()
        )

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

        if candidate.get("resource_match") is True:
            candidate["match_strength"] = "Более сильное совпадение"
            candidate["match_basis"].append("Совпадает ресурс")
            candidate["match_reason"] = (
                "Совпали поток, время и ресурс. " "Причинная связь не подтверждена."
            )
        else:
            candidate["match_reason"] = (
                "Совпали поток и временное окно. "
                "Соответствие ресурса исключению не установлено. "
                "Причинная связь не подтверждена."
            )

    return {
        "candidate_count": len(candidates),
        "summary": (
            "Найдены возможные связанные события. "
            "Совпадение ресурсов учитывается при оценке, "
            "но причинная связь не подтверждена."
        ),
        "candidates": candidates,
    }
