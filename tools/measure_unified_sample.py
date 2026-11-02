import os
import sys
import time
import threading
from collections import Counter

import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from techlog import iter_techlog_events, parse_event
from streaming_performance import StreamingPerformanceAnalyzer


LOG_FILE = r"1c_logs\1cv8c_16208\26110121.log"
MAX_EVENTS = 500_000

process = psutil.Process(os.getpid())
peak_memory = 0
stop_monitoring = threading.Event()


def monitor_memory():
    global peak_memory

    while not stop_monitoring.is_set():
        try:
            memory_mb = process.memory_info().rss / 1024 / 1024
            peak_memory = max(peak_memory, memory_mb)
        except psutil.Error:
            pass

        stop_monitoring.wait(0.1)


def main():
    global peak_memory

    by_type = Counter()
    total_events = 0

    monitor = threading.Thread(target=monitor_memory)
    monitor.start()

    started = time.perf_counter()

    try:
        with StreamingPerformanceAnalyzer() as analyzer:
            with open(
                LOG_FILE,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:

                for raw_text in iter_techlog_events(file):
                    event = parse_event(raw_text)

                    if event is None:
                        continue

                    analyzer.add_event(event)

                    total_events += 1
                    by_type[event.event_type] += 1

                    if total_events >= MAX_EVENTS:
                        break

            analyzer._create_duration_index()
            analyzer._create_sql_index()
            analyzer._create_table_index()

            performance = analyzer.get_performance()
            sql_performance = analyzer.get_sql_performance()

        elapsed = time.perf_counter() - started

    finally:
        stop_monitoring.set()
        monitor.join()

    print("\n========== КОНТРОЛЬНЫЙ АНАЛИЗ ==========")
    print(f"Событий обработано: {total_events:,}")
    print(f"Время выполнения: {elapsed:.2f} сек.")
    print(f"Пиковая RAM: {peak_memory:.2f} МБ")
    print(f"RAM после анализа: {process.memory_info().rss / 1024 / 1024:.2f} МБ")

    print("\nСобытия по типам:")
    for event_type, count in by_type.most_common():
        print(f"{event_type}: {count:,}")

    print("\nПроизводительность:")
    for event_type, stats in performance["by_event_type"].items():
        print(
            f"{event_type}: "
            f"count={stats['count']:,}, "
            f"P95={stats['p95_duration_us']} мкс"
        )

    print("\nSQL:")
    for sql_type, stats in sql_performance.items():
        print(
            f"{sql_type}: "
            f"count={stats['count']:,}, "
            f"P95={stats['p95_duration_us']} мкс"
        )


if __name__ == "__main__":
    main()
