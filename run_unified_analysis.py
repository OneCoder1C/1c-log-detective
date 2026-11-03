import argparse
import os
import threading
import time
from contextlib import redirect_stdout
from pathlib import Path
from pprint import pprint

import psutil

from unified_analysis import analyze_techlog_file


def main():
    parser = argparse.ArgumentParser(description="Анализ технологического журнала 1С")
    parser.add_argument(
        "log_file",
        help="Путь к технологическому журналу 1С",
    )
    parser.add_argument(
        "report_file",
        nargs="?",
        default="analysis_result.txt",
        help="Путь к итоговому отчёту",
    )

    args = parser.parse_args()

    log_file = Path(args.log_file)
    report_file = Path(args.report_file)

    if not log_file.is_file():
        parser.error(f"Файл журнала не найден: {log_file}")

    report_file.parent.mkdir(parents=True, exist_ok=True)

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
        result = analyze_techlog_file(str(log_file))
    finally:
        elapsed = time.perf_counter() - started
        stop_monitoring.set()
        monitor.join()

    final_memory = process.memory_info().rss / 1024 / 1024

    with report_file.open("w", encoding="utf-8") as report:
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

    print(f"Отчёт сохранён: {report_file.resolve()}")
    print(f"Всего событий: {result['total_events']:,}")
    print(f"Время: {elapsed:.2f} сек.")
    print(f"Пиковая память: {peak_memory:.2f} МБ")
    print(f"Память после анализа: {final_memory:.2f} МБ")


if __name__ == "__main__":
    main()
