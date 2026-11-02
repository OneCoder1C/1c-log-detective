import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from techlog import iter_techlog_events, parse_event


LOG_FILE = r"1c_logs\1cv8c_16208\26110121.log"
TARGET_DURATION_US = 766080

found = 0

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

        if event.event_type == "SESN" and event.duration_us == TARGET_DURATION_US:
            found += 1

            print(f"\nНайдено событие SESN №{found}")
            print(f"Время: {event.timestamp}")
            print(f"Длительность: {event.duration_us} мкс")
            print(raw_text[:3000])

            if found >= 3:
                break

print(f"\nВсего найдено: {found}")
