from collections import Counter
from pathlib import Path

from techlog import iter_techlog_events, parse_event
from sql_analysis import extract_sql, normalize_sql, get_sql_type

log_dir = Path("1c_logs")
log_files = list(log_dir.rglob("*.log"))

if not log_files:
    print("Файлы .log не найдены")
    raise SystemExit(1)

log_file = max(log_files, key=lambda path: path.stat().st_size)

counts = {
    "SDBL": Counter(),
    "DBV8DBEng": Counter(),
}

with log_file.open("r", encoding="utf-8", errors="replace") as file:
    for raw_event in iter_techlog_events(file):
        event = parse_event(raw_event)

        if event is None or event.event_type not in counts:
            continue

        sql = extract_sql(event.raw_text)

        if sql is None or get_sql_type(sql) == "OTHER":
            continue

        counts[event.event_type][normalize_sql(sql)] += 1

sdbl = counts["SDBL"]
dbv8 = counts["DBV8DBEng"]

common = set(sdbl) & set(dbv8)

print(f"SDBL: {sum(sdbl.values())} команд, {len(sdbl)} уникальных запросов")
print(f"DBV8DBEng: {sum(dbv8.values())} команд, {len(dbv8)} уникальных запросов")
print(f"Общие нормализованные запросы: {len(common)}")
print()
print("Примеры запросов, встречающихся в обоих источниках:")

for sql in sorted(common, key=lambda query: sdbl[query] + dbv8[query], reverse=True)[
    :10
]:
    print(f"  SDBL: {sdbl[sql]}, DBV8DBEng: {dbv8[sql]}")
    print(f"    {sql[:180]}")
