from pathlib import Path

from techlog import iter_techlog_events, parse_event


LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")
TARGET_THREAD = "OSThread=20716"
TARGET_MINUTE = "03:28"


def main():
    if not LOG_FILE.exists():
        print(f"Файл не найден: {LOG_FILE}")
        return

    counts = {"TLOCK": 0, "EXCP": 0}

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None:
                continue

            if not event.timestamp.startswith(TARGET_MINUTE + "."):
                continue

            first_line = raw_event.splitlines()[0]

            if TARGET_THREAD not in first_line:
                continue

            if event.event_type not in {"TLOCK", "EXCP"}:
                continue

            counts[event.event_type] += 1

            print(f"\n--- {event.event_type} ---")
            print(f"Время: {event.timestamp}")
            print(f"Уровень: {event.level}")
            print(f"Описание: {event.description[:250]}")

            for line in raw_event.splitlines():
                if line.startswith(("Regions=", "Locks=", "Context=")):
                    print(line[:1000])

    print("\n--- Итог ---")
    print(f"TLOCK: {counts['TLOCK']}")
    print(f"EXCP: {counts['EXCP']}")


if __name__ == "__main__":
    main()
