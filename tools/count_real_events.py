import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from techlog import iter_techlog_events, parse_event


LOG_FILE = r"1c_logs\1cv8c_16208\26110121.log"


def main():
    total_events = 0
    by_type = Counter()

    started = time.perf_counter()

    print("Начинаем подсчёт событий...")

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

            total_events += 1
            by_type[event.event_type] += 1

            if total_events % 500_000 == 0:
                print(f"Обработано событий: {total_events:,}")

    elapsed = time.perf_counter() - started

    print("\n========== РЕЗУЛЬТАТ ==========")
    print(f"Всего событий: {total_events:,}")
    print(f"Время: {elapsed:.2f} сек.")

    print("\nПо типам:")
    for event_type, count in by_type.most_common():
        print(f"{event_type}: {count:,}")


if __name__ == "__main__":
    main()
