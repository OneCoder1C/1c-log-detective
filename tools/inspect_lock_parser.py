from pathlib import Path
from pprint import pprint

from techlog import iter_techlog_events, parse_lock_event


LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")
MAX_EVENTS = 3


def main():
    if not LOG_FILE.exists():
        print(f"Файл не найден: {LOG_FILE}")
        return

    found = 0

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            if "Reference69.REFLOCK" not in raw_event:
                continue

            lock = parse_lock_event(raw_event)

            if lock is None:
                continue

            # Не выводим полный контекст из рабочего журнала.
            lock["context"] = lock["context"][:200]

            print("\n--- Разобранный TLOCK ---")
            pprint(lock, sort_dicts=False)
            found += 1

            if found >= MAX_EVENTS:
                break

    print(f"\nВсего разобрано событий: {found}")


if __name__ == "__main__":
    main()
