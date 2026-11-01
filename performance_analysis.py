from collections import defaultdict
from collections.abc import Iterable
from math import ceil

from sql_analysis import (
    extract_sql,
    extract_sql_tables,
    get_sql_type,
    normalize_sql,
)

from techlog import TechLogEvent


def analyze_performance(events: Iterable[TechLogEvent]) -> dict:
    """Собирает общую статистику длительности событий ТЖ."""

    stats = defaultdict(
        lambda: {
            "count": 0,
            "total_duration_us": 0,
            "max_duration_us": 0,
            "slow_count": 0,
        }
    )
    durations = defaultdict(list)
    total_events = 0

    for event in events:
        if event.duration_us is None:
            continue

        data = stats[event.event_type]
        durations[event.event_type].append(event.duration_us)
        data["count"] += 1
        data["total_duration_us"] += event.duration_us
        data["max_duration_us"] = max(
            data["max_duration_us"],
            event.duration_us,
        )

        if event.duration_us >= 10_000:
            data["slow_count"] += 1

        total_events += 1

    for data in stats.values():
        data["avg_duration_us"] = data["total_duration_us"] / data["count"]

    for event_type, data in stats.items():
        sorted_durations = sorted(durations[event_type])
        p95_index = ceil(len(sorted_durations) * 0.95) - 1
        data["p95_duration_us"] = sorted_durations[p95_index]

    return {
        "total_events": total_events,
        "by_event_type": dict(stats),
    }


def analyze_slow_events(
    events: Iterable[TechLogEvent],
    limit: int = 20,
) -> list[dict]:
    """Анализирует медленные события ТЖ, не связанные с SQL."""

    if limit < 0:
        raise ValueError("limit не может быть отрицательным")

    stats = defaultdict(
        lambda: {
            "count": 0,
            "total_duration_us": 0,
            "max_duration_us": 0,
            "durations": [],
        }
    )

    for event in events:
        if event.event_type in {"SDBL", "DBV8DBEng"}:
            continue

        if event.duration_us is None or event.duration_us < 10_000:
            continue

        data = stats[event.event_type]

        data["count"] += 1
        data["total_duration_us"] += event.duration_us
        data["max_duration_us"] = max(
            data["max_duration_us"],
            event.duration_us,
        )
        data["durations"].append(event.duration_us)

    result = []

    for event_type, data in stats.items():
        sorted_durations = sorted(data["durations"])
        p95_index = ceil(len(sorted_durations) * 0.95) - 1

        data["avg_duration_us"] = data["total_duration_us"] / data["count"]
        data["p95_duration_us"] = sorted_durations[p95_index]
        data["event_type"] = event_type

        del data["durations"]

        result.append(data)

    result.sort(
        key=lambda item: item["total_duration_us"],
        reverse=True,
    )

    return result[:limit]


def analyze_sql_performance(events: Iterable[TechLogEvent]) -> dict:
    """Собирает статистику длительности SQL-событий по типам команд."""

    stats = defaultdict(
        lambda: {
            "count": 0,
            "total_duration_us": 0,
            "max_duration_us": 0,
            "slow_count": 0,
        }
    )
    durations = defaultdict(list)

    for event in events:
        if event.event_type not in {"SDBL", "DBV8DBEng"}:
            continue

        if event.duration_us is None:
            continue

        sql = extract_sql(event.raw_text)

        if not sql or event.duration_us is None:
            continue

        sql_type = get_sql_type(sql)

        if sql_type == "OTHER":
            continue

        data = stats[sql_type]

        durations[sql_type].append(event.duration_us)

        data["count"] += 1
        data["total_duration_us"] += event.duration_us
        data["max_duration_us"] = max(
            data["max_duration_us"],
            event.duration_us,
        )

        if event.duration_us >= 10_000:
            data["slow_count"] += 1
    for sql_type, data in stats.items():
        data["avg_duration_us"] = data["total_duration_us"] / data["count"]

        sorted_durations = sorted(durations[sql_type])
        p95_index = ceil(len(sorted_durations) * 0.95) - 1
        data["p95_duration_us"] = sorted_durations[p95_index]

    return dict(stats)


def analyze_slow_sql(
    events: Iterable[TechLogEvent],
    limit: int = 20,
) -> list[dict]:
    """Находит SQL-запросы с наибольшей суммарной длительностью."""

    if limit < 0:
        raise ValueError("limit не может быть отрицательным")

    stats = defaultdict(
        lambda: {
            "count": 0,
            "total_duration_us": 0,
            "max_duration_us": 0,
            "slow_count": 0,
        }
    )
    durations = defaultdict(list)

    for event in events:
        if event.event_type not in {"SDBL", "DBV8DBEng"}:
            continue

        if event.duration_us is None:
            continue

        sql = extract_sql(event.raw_text)

        if not sql:
            continue

        sql_type = get_sql_type(sql)

        if sql_type == "OTHER":
            continue

        normalized_sql = normalize_sql(sql)
        data = stats[normalized_sql]

        data["sql_type"] = sql_type
        data["count"] += 1
        data["total_duration_us"] += event.duration_us
        data["max_duration_us"] = max(
            data["max_duration_us"],
            event.duration_us,
        )
        durations[normalized_sql].append(event.duration_us)

        if event.duration_us >= 10_000:
            data["slow_count"] += 1

    result = []

    for normalized_sql, data in stats.items():
        sorted_durations = sorted(durations[normalized_sql])
        p95_index = ceil(len(sorted_durations) * 0.95) - 1

        data["avg_duration_us"] = data["total_duration_us"] / data["count"]
        data["p95_duration_us"] = sorted_durations[p95_index]
        data["normalized_sql"] = normalized_sql

        result.append(data)

    result.sort(
        key=lambda item: item["total_duration_us"],
        reverse=True,
    )

    return result[:limit]


def analyze_sql_tables(events: Iterable[TechLogEvent]) -> list[dict]:
    """Собирает статистику SQL-обращений по таблицам."""

    stats = defaultdict(
        lambda: {
            "count": 0,
            "total_duration_us": 0,
            "max_duration_us": 0,
            "slow_count": 0,
            "durations": [],
        }
    )

    for event in events:
        if event.event_type not in {"SDBL", "DBV8DBEng"}:
            continue

        if event.duration_us is None:
            continue

        sql = extract_sql(event.raw_text)

        if not sql:
            continue

        sql_type = get_sql_type(sql)

        if sql_type == "OTHER":
            continue

        tables = extract_sql_tables(sql)

        for table in tables:
            data = stats[table]

            data["count"] += 1
            data["total_duration_us"] += event.duration_us
            data["durations"].append(event.duration_us)
            data["max_duration_us"] = max(
                data["max_duration_us"],
                event.duration_us,
            )

            if event.duration_us >= 10_000:
                data["slow_count"] += 1

    result = []

    for table, data in stats.items():
        data["avg_duration_us"] = data["total_duration_us"] / data["count"]

        sorted_durations = sorted(data["durations"])
        p95_index = ceil(len(sorted_durations) * 0.95) - 1
        data["p95_duration_us"] = sorted_durations[p95_index]

        del data["durations"]

        data["table"] = table
        result.append(data)

    result.sort(
        key=lambda item: item["total_duration_us"],
        reverse=True,
    )

    return result
