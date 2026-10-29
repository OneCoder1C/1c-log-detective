import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import Counter
from techlog import extract_fields
from techlog import iter_techlog_events, parse_event, parse_lock_event
from exception_groups import normalize_exception, count_exception_groups
from lock_analysis import find_lock_candidates, summarize_lock_candidates

LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")
OUTPUT_FILE = Path("lock_analysis_report.txt")

# Ищем ошибки блокировки и ближайшие к ним события TLOCK.
WINDOW_MS = 1000
MAX_LOCKS_PER_EXCEPTION = 20


def main():
    if not LOG_FILE.exists():
        print(f"Файл не найден: {LOG_FILE}")
        return

    lock_events = []
    lock_exceptions = []
    event_types = Counter()
    exceptions_by_user = Counter()
    exceptions_by_thread = Counter()
    exceptions_by_minute = Counter()

    print("Читаю технологический журнал...")
    print("Большой файл может обрабатываться несколько минут.")

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None:
                continue

            event_types[event.event_type] += 1

            if event.event_type == "TLOCK":
                lock = parse_lock_event(raw_event)
                if lock is not None:
                    lock_events.append(lock)

            if event.event_type == "EXCP":
                category = normalize_exception(event.description)

                if category == "Не удалось заблокировать запись":

                    # Извлекаем поля исходного события EXCP.

                    raw_fields = extract_fields(raw_event)

                    fields = {
                        "timestamp": event.timestamp,
                        "thread": raw_fields.get("OSThread", ""),
                        "process": raw_fields.get("process", ""),
                        "user": raw_fields.get("Usr", ""),
                        "exception_type": raw_fields.get("Exception", ""),
                        "description": event.description,
                        "raw_fields": raw_fields,
                        "raw_text": raw_event,
                    }

                    lock_exceptions.append(fields)

                    exceptions_by_user[fields["user"] or "не указан"] += 1
                    exceptions_by_thread[fields["thread"] or "не указан"] += 1
                    timestamp = fields["timestamp"]
                    minute = timestamp.split(".", 1)[0]
                    exceptions_by_minute[minute] += 1

    report_lines = [
        "ОТЧЁТ ПО БЛОКИРОВКАМ 1С",
        "=" * 50,
        f"Файл: {LOG_FILE}",
        f"Найдено событий TLOCK: {len(lock_events)}",
        f"Найдено исключений блокировки: {len(lock_exceptions)}",
        "",
        "ТИПЫ СОБЫТИЙ",
        "-" * 50,
    ]

    for event_type, count in event_types.most_common():
        report_lines.append(f"{event_type}: {count}")

    # Группируем исключения по категории и детали.
    exception_groups = count_exception_groups(
        [exception["description"] for exception in lock_exceptions]
    )

    report_lines.extend(
        [
            "",
            "ГРУППЫ ИСКЛЮЧЕНИЙ",
            "-" * 50,
        ]
    )

    for group_name, count in sorted(
        exception_groups.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        report_lines.append(f"{group_name}: {count}")

    report_lines.extend(["", "ИСКЛЮЧЕНИЯ ПО ПОЛЬЗОВАТЕЛЯМ", "-" * 50])

    for user, count in exceptions_by_user.most_common():
        report_lines.append(f"{user}: {count}")

    report_lines.extend(["", "ИСКЛЮЧЕНИЯ ПО ПОТОКАМ", "-" * 50])

    for thread, count in exceptions_by_thread.most_common():
        report_lines.append(f"{thread}: {count}")

    if lock_exceptions:
        timestamps = [
            exception["timestamp"]
            for exception in lock_exceptions
            if exception["timestamp"]
        ]

        report_lines.extend(
            [
                "",
                "ВРЕМЕННОЙ ДИАПАЗОН ИСКЛЮЧЕНИЙ",
                "-" * 50,
                f"Первое исключение: {min(timestamps) if timestamps else 'не определено'}",
                f"Последнее исключение: {max(timestamps) if timestamps else 'не определено'}",
            ]
        )

    report_lines.extend(["", "ИСКЛЮЧЕНИЯ ПО МИНУТАМ", "-" * 50])

    for minute, count in sorted(exceptions_by_minute.items()):
        report_lines.append(f"{minute}: {count}")

    report_lines.extend(["", "АНАЛИЗ ИСКЛЮЧЕНИЙ", "-" * 50])

    for index, exception in enumerate(lock_exceptions, start=1):
        candidates = find_lock_candidates(
            lock_events=lock_events,
            exception_time=exception["timestamp"],
            exception_thread=exception["thread"],
            window_ms=WINDOW_MS,
        )

        candidates = candidates[:MAX_LOCKS_PER_EXCEPTION]
        summary = summarize_lock_candidates(candidates)

        report_lines.extend(
            [
                "",
                f"Исключение №{index}",
                f"Время: {exception['timestamp']}",
                f"Поток: {exception['thread'] or 'не указан'}",
                f"Пользователь: {exception['user'] or 'не указан'}",
                f"Тип исключения: {exception['exception_type'] or 'не указан'}",
                f"Описание: {exception['description']}",
                summary["summary"],
                f"Кандидатов: {summary['candidate_count']}",
            ]
        )

        for candidate in candidates:
            report_lines.extend(
                [
                    f"  Время TLOCK: {candidate['timestamp']}",
                    f"  Разница по времени: " f"{candidate['time_difference_ms']} мс",
                    f"  Режим: {candidate['lock_mode']}",
                    f"  Оценка совпадения: {candidate['match_strength']}",
                    f"  Основание: {candidate['match_reason']}",
                    f"  Область: {candidate['regions']}",
                    f"  Ресурс: {candidate['resource_id']}",
                    f"  Контекст: {candidate['context'][:300]}",
                    "",
                ]
            )

    report_lines.extend(
        [
            "",
            "ВАЖНО",
            "Совпадение потока и близость времени указывают на кандидатов,",
            "но сами по себе не доказывают причинную связь.",
        ]
    )

    OUTPUT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\nОтчёт сохранён: {OUTPUT_FILE}")
    print(f"Событий TLOCK: {len(lock_events)}")
    print(f"Исключений блокировки: {len(lock_exceptions)}")


if __name__ == "__main__":
    main()
