import os
import tempfile
import psutil

from streaming_performance import StreamingPerformanceAnalyzer
from collections import Counter

from techlog import iter_techlog_events, parse_event


def analyze_techlog_file(file_path: str) -> dict:
    """Потоково собирает общую статистику технологического журнала."""

    by_type = Counter()
    by_level = Counter()

    total_events = 0
    lock_events_count = 0
    lock_exceptions_count = 0

    database_file = tempfile.NamedTemporaryFile(
        suffix=".db",
        delete=False,
    )
    database_path = database_file.name
    database_file.close()

    performance_analyzer = None

    try:
        performance_analyzer = StreamingPerformanceAnalyzer(database_path)

        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            for raw_text in iter_techlog_events(file):
                event = parse_event(raw_text)

                if event is None:
                    continue

                performance_analyzer.add_event(event)

                total_events += 1
                by_type[event.event_type] += 1
                by_level[event.level] += 1

                if event.event_type == "TLOCK":
                    lock_events_count += 1

                elif event.event_type == "EXCP":
                    if "Не удалось заблокировать запись" in event.description:
                        lock_exceptions_count += 1

        process = psutil.Process(os.getpid())

        print("\nПАМЯТЬ ПОСЛЕ ЧТЕНИЯ ЖУРНАЛА")
        print(f"RSS: {process.memory_info().rss / 1024 / 1024:.2f} МБ")
        print(f"TLOCK обработано: {lock_events_count}")
        print(f"EXCP блокировок обработано: {lock_exceptions_count}")

        performance_analyzer._create_duration_index()
        performance_analyzer._create_sql_index()
        performance_analyzer._create_table_index()
        performance = performance_analyzer.get_performance()
        sql_performance = performance_analyzer.get_sql_performance()
        slow_sql = performance_analyzer.get_slow_sql()
        sql_tables = performance_analyzer.get_sql_tables()

        return {
            "total_events": total_events,
            "by_type": dict(by_type),
            "by_level": dict(by_level),
            "lock_events_count": lock_events_count,
            "lock_exceptions_count": lock_exceptions_count,
            "performance": performance,
            "sql_performance": sql_performance,
            "slow_sql": slow_sql,
            "sql_tables": sql_tables,
        }

    finally:
        if performance_analyzer is not None:
            performance_analyzer.close()

        if os.path.exists(database_path):
            os.remove(database_path)
