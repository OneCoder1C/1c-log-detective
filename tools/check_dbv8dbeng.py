import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathlib import Path

from techlog import iter_techlog_events, parse_event
from sql_analysis import extract_sql, get_sql_type

log_dir = Path("1c_logs")
log_files = list(log_dir.rglob("*.log"))

if not log_files:
    print("Файлы .log не найдены")
    raise SystemExit(1)

log_file = max(log_files, key=lambda path: path.stat().st_size)

total = 0
with_sql = 0
recognized = 0
examples = []

with log_file.open("r", encoding="utf-8", errors="replace") as file:
    for raw_event in iter_techlog_events(file):
        event = parse_event(raw_event)

        if event is None or event.event_type != "DBV8DBEng":
            continue

        total += 1
        sql = extract_sql(event.raw_text)

        if sql is not None:
            with_sql += 1

            if get_sql_type(sql) != "OTHER":
                recognized += 1

            if len(examples) < 3:
                examples.append((get_sql_type(sql), sql[:200].replace("\n", " ")))

print(f"Событий DBV8DBEng: {total}")
print(f"Событий с извлечённым SQL: {with_sql}")
print(f"Распознанных SQL-команд: {recognized}")

for sql_type, sql in examples:
    print(f"{sql_type}: {sql}")
