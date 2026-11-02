import os
import threading
import time
from pprint import pprint
from contextlib import redirect_stdout

import psutil

from unified_analysis import analyze_techlog_file


LOG_FILE = r"1c_logs\1cv8c_16208\26110121.log"
REPORT_FILE = "analysis_result.txt"


def main():
    process = psutil.Process(os.getpid())

    peak_memory = 0
    stop_monitoring = threading.Event()

    def monitor_memory():
        nonlocal peak_memory

        while not stop_monitoring.is_set():
            try:
                memory_mb = process.memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, memory_mb)
            except psutil.Error:
                pass

            stop_monitoring.wait(0.2)

    monitor = threading.Thread(target=monitor_memory)
    monitor.start()

    started = time.perf_counter()

    try:
        result = analyze_techlog_file(LOG_FILE)
    finally:
        elapsed = time.perf_counter() - started
        stop_monitoring.set()
        monitor.join()

    final_memory = process.memory_info().rss / 1024 / 1024

    with open(REPORT_FILE, "w", encoding="utf-8") as report:
        with redirect_stdout(report):
            print("========== РЕЗУЛЬТАТ АНАЛИЗА ==========")

            print(f"Всего событий: {result['total_events']:,}")
            print(f"TLOCK: {result['lock_events_count']:,}")
            print(f"EXCP блокировок: {result['lock_exceptions_count']:,}")

            print(f"\nВремя выполнения: {elapsed:.2f} сек.")
            print(f"Пиковая память: {peak_memory:.2f} МБ")
            print(f"Память после анализа: {final_memory:.2f} МБ")

            print("\n========== СОБЫТИЯ ПО ТИПАМ ==========")
            pprint(result["by_type"])

            print("\n========== ПРОИЗВОДИТЕЛЬНОСТЬ ==========")
            pprint(result["performance"])

            print("\n========== СТАТИСТИКА SQL ==========")
            pprint(result["sql_performance"])

            print("\n========== ТОП-10 МЕДЛЕННЫХ SQL ==========")
            pprint(result["slow_sql"][:10])

            print("\n========== ТОП-10 ТАБЛИЦ ==========")
            pprint(dict(list(result["sql_tables"].items())[:10]))

    print(f"Отчёт сохранён: {os.path.abspath(REPORT_FILE)}")
    print(f"Всего событий: {result['total_events']:,}")
    print(f"Время: {elapsed:.2f} сек.")
    print(f"Пиковая память: {peak_memory:.2f} МБ")
    print(f"Память после анализа: {final_memory:.2f} МБ")


if __name__ == "__main__":
    main()
