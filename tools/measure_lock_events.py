import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from time import perf_counter

from techlog import iter_techlog_events, parse_event, is_event_start

log_file = max(
    Path("1c_logs").rglob("*.log"),
    key=lambda path: path.stat().st_size,
)

start = perf_counter()
total_events = 0
lock_count = 0

with log_file.open(
    "r",
    encoding="utf-8",
    errors="replace",
) as file:
    for raw_text in iter_techlog_events(file):
        first_line = raw_text.split("\n", 1)[0]

        if not is_event_start(first_line):
            continue

        total_events += 1

        parts = first_line.split(",", maxsplit=2)
        if len(parts) > 1 and parts[1] == "TLOCK":
            event = parse_event(raw_text)
            if event is not None:
                lock_count += 1

elapsed = perf_counter() - start

print("Файл:", log_file.name)
print("Всего событий:", total_events)
print("Событий TLOCK:", lock_count)
print(f"Время обработки: {elapsed:.2f} сек.")
