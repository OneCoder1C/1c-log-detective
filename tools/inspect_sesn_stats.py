import os
import sys
from collections import Counter

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from techlog import iter_techlog_events, parse_event


LOG_FILE = r"1c_logs\1cv8c_16208\26110121.log"

durations = Counter()
longest_events = []

with open(
    LOG_FILE,
    "r",
    encoding="utf-8",
    errors="replace",
) as file:

    for raw_text in iter_techlog_events(file):
        event = parse_event(raw_text)

        if event is None or event.event_type != "SESN":
            continue

        if event.duration_us is not None:
            durations[event.duration_us] += 1

            longest_events.append((event.duration_us, raw_text))

print(f"SESN с длительностью: {sum(durations.values())}")

print("\n10 самых продолжительных SESN:")

for duration, raw_text in sorted(
    longest_events,
    key=lambda item: item[0],
    reverse=True,
)[:10]:
    print(f"\nДлительность: {duration:,} мкс")
    print(raw_text[:2000])
