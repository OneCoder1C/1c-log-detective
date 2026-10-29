import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathlib import Path
from time import perf_counter, sleep
from threading import Thread
import psutil

from techlog import read_techlog_file

log_file = max(
    Path("1c_logs").rglob("*.log"),
    key=lambda path: path.stat().st_size,
)

process = psutil.Process()
peak_memory = process.memory_info().rss / (1024 * 1024)
monitoring = True


def monitor_memory():
    global peak_memory

    while monitoring:
        memory = process.memory_info().rss / (1024 * 1024)
        peak_memory = max(peak_memory, memory)
        sleep(0.05)


monitor = Thread(target=monitor_memory, daemon=True)
monitor.start()

start = perf_counter()
events = read_techlog_file(log_file)
elapsed = perf_counter() - start

monitoring = False
monitor.join()

memory_after = process.memory_info().rss / (1024 * 1024)

print("Файл:", log_file.name)
print("Размер файла:", f"{log_file.stat().st_size / (1024 ** 3):.2f} ГБ")
print("Количество событий:", len(events))
print(f"Время обработки: {elapsed:.2f} сек.")
print(f"Память после обработки: {memory_after:.1f} МБ")
print(f"Пиковая память: {peak_memory:.1f} МБ")
