from pathlib import Path

from techlog import iter_techlog_events, is_event_start


log_file = max(
    Path("1c_logs").rglob("*.log"),
    key=lambda path: path.stat().st_size,
)

shown = 0

with log_file.open(
    "r",
    encoding="utf-8",
    errors="replace",
) as file:
    for raw_event in iter_techlog_events(file):
        first_line = raw_event.split("\n", 1)[0]

        if not is_event_start(first_line):
            continue

        parts = first_line.split(",", maxsplit=2)

        if len(parts) < 2 or parts[1] != "SDBL":
            continue

        print("-" * 60)
        print(raw_event[:1500])
        shown += 1

        if shown >= 5:
            break

print(f"\nПоказано SQL-событий: {shown}")
