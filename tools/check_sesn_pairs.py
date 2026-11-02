import os
import sys
from collections import defaultdict

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from techlog import iter_techlog_events, parse_event, extract_fields


LOG_FILE = r"1c_logs\1cv8c_16208\26110121.log"

sessions = defaultdict(list)

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

        fields = extract_fields(raw_text)

        session_id = fields.get("ID", "")
        func = fields.get("Func", "")

        if session_id and func in {"Attach", "Finish"}:
            sessions[session_id].append(
                {
                    "func": func,
                    "duration": event.duration_us,
                    "timestamp": event.timestamp,
                    "nmb": fields.get("Nmb", ""),
                }
            )


paired = 0
unpaired = 0
different = 0

for session_id, events in sessions.items():
    funcs = {item["func"] for item in events}

    if "Attach" in funcs and "Finish" in funcs:
        paired += 1

        attach = next(item for item in events if item["func"] == "Attach")
        finish = next(item for item in events if item["func"] == "Finish")

        if attach["duration"] != finish["duration"]:
            different += 1
    else:
        unpaired += 1

print(f"Уникальных ID: {len(sessions)}")
print(f"ID с Attach и Finish: {paired}")
print(f"ID без полной пары: {unpaired}")
print(f"Пары с разной длительностью: {different}")
print("\nПримеры пар Attach / Finish:")

shown = 0

for session_id, events in sessions.items():
    attach_events = [item for item in events if item["func"] == "Attach"]
    finish_events = [item for item in events if item["func"] == "Finish"]

    if not attach_events or not finish_events:
        continue

    attach = attach_events[0]
    finish = finish_events[0]

    difference = abs(attach["duration"] - finish["duration"])

    print(f"\nID: {session_id}")
    print(f"Attach: {attach['duration']:,} мкс")
    print(f"Finish: {finish['duration']:,} мкс")
    print(f"Разница: {difference:,} мкс")

    shown += 1

    if shown >= 10:
        break
