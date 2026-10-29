import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathlib import Path

from techlog import iter_techlog_events, parse_event

LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")
TARGET = "DATAZONEOBJECTLOCKS"
BEFORE = 5
AFTER = 5
MAX_INCIDENTS = 3


def main():
    if not LOG_FILE.exists():
        print(f"Файл не найден: {LOG_FILE}")
        return

    previous_events = []
    remaining_after = 0
    incidents = 0

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None:
                continue

            is_target = event.event_type == "EXCP" and TARGET in event.description

            if is_target:
                if incidents >= MAX_INCIDENTS:
                    break

                incidents += 1
                print(f"\n{'=' * 50}")
                print(f"Инцидент №{incidents}")
                print(f"Время: {event.timestamp}")
                print(f"Описание: {event.description[:250]}")
                print("--- Предшествующие события ---")

                for old_event in previous_events[-BEFORE:]:
                    print_event(old_event)

                print("--- Событие исключения ---")
                print_event(raw_event)

                remaining_after = AFTER
                previous_events = []
                continue

            if remaining_after > 0:
                print_event(raw_event)
                remaining_after -= 1

            previous_events.append(raw_event)
            if len(previous_events) > BEFORE:
                previous_events.pop(0)

    print(f"\nНайдено инцидентов: {incidents}")


def print_event(raw_text):
    event = parse_event(raw_text)
    if event is None:
        return

    first_line = raw_text.splitlines()[0]
    print(f"\nТип: {event.event_type}")
    print(f"Время: {event.timestamp}")
    print(f"Заголовок: {first_line[:350]}")


if __name__ == "__main__":
    main()
