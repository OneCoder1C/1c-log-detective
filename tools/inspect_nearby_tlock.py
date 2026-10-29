from pathlib import Path

from techlog import iter_techlog_events, parse_event


LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")
TARGET = "DATAZONEOBJECTLOCKS"
TARGET_TIMES = {"03:27", "03:28"}
MAX_EXAMPLES = 15


def main():
    if not LOG_FILE.exists():
        print(f"Файл не найден: {LOG_FILE}")
        return

    found = 0
    counts = {"TLOCK": 0, "EXCP": 0}

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None:
                continue

            minute_second = event.timestamp[:5]

            if minute_second not in TARGET_TIMES:
                continue

            if event.event_type == "TLOCK":
                counts["TLOCK"] += 1

                if found < MAX_EXAMPLES:
                    print("\n--- TLOCK ---")
                    print(f"Время: {event.timestamp}")
                    print(raw_event[:1200])
                    found += 1

            elif event.event_type == "EXCP" and TARGET in event.description:
                counts["EXCP"] += 1

    print("\n--- Итог ---")
    print(f"TLOCK в выбранных минутах: {counts['TLOCK']}")
    print(f"Исключения {TARGET}: {counts['EXCP']}")
    print(f"Выведено событий TLOCK: {found}")


if __name__ == "__main__":
    main()
