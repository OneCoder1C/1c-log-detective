import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathlib import Path
from time import perf_counter

from techlog import read_techlog_file

log_file = max(
    Path("1c_logs").rglob("*.log"),
    key=lambda path: path.stat().st_size,
)

print("Файл:", log_file.name)
print(f"Размер: {log_file.stat().st_size / (1024 * 1024):.1f} МБ")

start = perf_counter()
events = read_techlog_file(log_file)
elapsed = perf_counter() - start

print("Всего событий:", len(events))
print(f"Время чтения и разбора: {elapsed:.2f} сек.")
print(f"Скорость: {len(events) / elapsed:.0f} событий/сек.")
