import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathlib import Path
from collections import Counter

from techlog import iter_techlog_events, parse_event, extract_fields

LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")

TARGET_MINUTE = 41
TARGET_SECOND = 37
TARGET_FRACTION = 674309

WINDOW_BEFORE_SECONDS = 1
WINDOW_AFTER_SECONDS = 2


def timestamp_to_seconds(timestamp: str) -> float | None:
    """Преобразует время формата MM:SS.ffffff-N в секунды."""
    try:
        time_part = timestamp.split("-", 1)[0]
        minute_part, second_part = time_part.split(":", 1)
        return int(minute_part) * 60 + float(second_part)
    except (ValueError, AttributeError):
        return None


def main():
    if not LOG_FILE.exists():
        print(f"Файл не найден: {LOG_FILE}")
        return

    target_time = TARGET_MINUTE * 60 + TARGET_SECOND + TARGET_FRACTION / 1_000_000

    start_time = target_time - WINDOW_BEFORE_SECONDS
    end_time = target_time + WINDOW_AFTER_SECONDS

    counts = Counter()
    found = 0

    output_path = Path("inspection_output.txt")

    print("Ищу события в заданном временном интервале...")
    print("Чтение большого журнала может занять несколько минут.\n")

    with output_path.open("w", encoding="utf-8") as output_file:
        with LOG_FILE.open(
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:
            for raw_event in iter_techlog_events(file):
                event = parse_event(raw_event)

                if event is None:
                    continue

                event_time = timestamp_to_seconds(event.timestamp)

                if event_time is None:
                    continue

                if start_time <= event_time <= end_time:
                    found += 1
                    counts[event.event_type] += 1

                    fields = extract_fields(event.raw_text)

                    line = (
                        f"{event.timestamp} | "
                        f"{event.event_type} | "
                        f"Поток: {fields.get('OSThread', '?')} | "
                        f"Пользователь: {fields.get('Usr', '?')} | "
                        f"{event.description[:150]}"
                    )

                    print(line)
                    output_file.write(line + "\n")

    print("\n" + "=" * 60)
    print(f"Найдено событий: {found}")
    print("Количество событий по типам:")

    for event_type, count in counts.most_common():
        print(f"{event_type}: {count}")


if __name__ == "__main__":
    main()
