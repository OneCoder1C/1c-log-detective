import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from techlog import extract_fields
from techlog import iter_techlog_events, parse_event, parse_lock_event
from exception_groups import (
    normalize_exception,
    count_exception_groups,
    extract_exception_resource,
)
from lock_analysis import (
    calculate_exception_intervals,
    find_exception_series,
    find_lock_candidates,
    summarize_lock_candidates,
)

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
    exception_timestamps = []
    event_types = Counter()
    exceptions_by_user = Counter()
    exceptions_by_thread = Counter()
    exceptions_by_minute = Counter()
    exceptions_by_resource = Counter()

    print("Читаю технологический журнал...")
    print("Большой файл может обрабатываться несколько минут.")

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None:
                continue

            event_types[event.event_type] += 1

            if event.event_type == "TLOCK":
                lock = parse_lock_event(raw_event, event)
                if lock is not None:
                    lock_events.append(lock)

            if event.event_type == "EXCP":
                category = normalize_exception(event.description)

                if category == "Не удалось заблокировать запись":
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

                    resource = extract_exception_resource(fields["description"])

                    if resource and not resource.isdigit():
                        exceptions_by_resource[resource] += 1

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

    report_lines.extend(
        [
            "",
            "ИСКЛЮЧЕНИЯ ПО РЕСУРСАМ",
            "-" * 50,
        ]
    )

    if exceptions_by_resource:
        for resource, count in exceptions_by_resource.most_common():
            report_lines.append(f"{resource}: {count}")
    else:
        report_lines.append("Ресурсы не определены")

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

    # Рассчитываем интервалы между соседними исключениями.
    # parse_event_time возвращает секунды внутри часа.
    timed_exceptions = []
    # Рассчитываем интервалы между исключениями.
    interval_stats = calculate_exception_intervals(
        [exception["timestamp"] for exception in lock_exceptions]
    )

    exception_series = find_exception_series(exception_timestamps)

    report_lines.extend(
        [
            "",
            "ИНТЕРВАЛЫ МЕЖДУ ИСКЛЮЧЕНИЯМИ",
            "-" * 50,
        ]
    )

    if interval_stats["interval_count"]:
        report_lines.extend(
            [
                f"Количество интервалов: {interval_stats['interval_count']}",
                f"Минимальный интервал: {interval_stats['min_ms']:.3f} мс",
                f"Максимальный интервал: {interval_stats['max_ms']:.3f} мс",
                f"Средний интервал: {interval_stats['average_ms']:.3f} мс",
                f"Интервалов до 100 мс: {interval_stats['up_to_100_ms']}",
                f"Интервалов до 1000 мс: {interval_stats['up_to_1000_ms']}",
                "Распределение интервалов:",
                f"  До 10 мс: {interval_stats['interval_ranges']['up_to_10_ms']}",
                f"  10–100 мс: {interval_stats['interval_ranges']['10_to_100_ms']}",
                f"  100–1000 мс: {interval_stats['interval_ranges']['100_to_1000_ms']}",
                f"  1–10 секунд: {interval_stats['interval_ranges']['1_to_10_seconds']}",
                f"  Более 10 секунд: {interval_stats['interval_ranges']['over_10_seconds']}",
            ]
        )
    else:
        report_lines.append("Не удалось рассчитать интервалы")
    report_lines.extend(
        [
            "",
            "СЕРИИ ИСКЛЮЧЕНИЙ",
            "-" * 50,
            f"Найдено серий: {len(exception_series)}",
        ]
    )

    for index, series in enumerate(exception_series, start=1):
        report_lines.extend(
            [
                "",
                f"Серия #{index}",
                f"Количество событий: {series['event_count']}",
                f"Начало: {series['start_timestamp']}",
                f"Окончание: {series['end_timestamp']}",
                f"Продолжительность: {series['duration_ms']:.3f} мс",
                f"Максимальный интервал: {series['max_gap_ms']:.3f} мс",
            ]
        )

    for index, series in enumerate(exception_series, start=1):
        report_lines.extend(
            [
                "",
                f"Серия #{index}",
                f"Количество событий: {series['event_count']}",
                f"Начало: {series['start_timestamp']}",
                f"Окончание: {series['end_timestamp']}",
                f"Продолжительность: {series['duration_ms']:.3f} мс",
                f"Максимальный интервал: {series['max_gap_ms']:.3f} мс",
            ]
        )

    # Для каждого исключения ищем ближайшие события TLOCK.
    for index, exception in enumerate(lock_exceptions, start=1):
        candidates = find_lock_candidates(
            lock_events=lock_events,
            exception_time=exception["timestamp"],
            exception_thread=exception["thread"],
            window_ms=WINDOW_MS,
            exception_description=exception["description"],
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
            context = candidate.get("context", "").strip()

            report_lines.extend(
                [
                    f"  Время TLOCK: {candidate['timestamp']}",
                    f"  Разница по времени: {candidate['time_difference_ms']} мс",
                    f"  Режим: {candidate['lock_mode']}",
                    f"  Оценка совпадения: {candidate['match_strength']}",
                    f"  Основание: {candidate['match_reason']}",
                    f"  Область: {candidate['regions']}",
                    f"  Ресурс: {candidate['resource_id']}",
                    "  Контекст выполнения:",
                ]
            )

            if context:
                report_lines.extend(
                    f"    {line.strip()}"
                    for line in context.splitlines()
                    if line.strip()
                )
            else:
                report_lines.append("    Контекст отсутствует")

            report_lines.append("")

    report_lines.extend(
        [
            "",
            "ВАЖНО",
            "Совпадение потока и близость времени указывают на кандидатов,",
            "но сами по себе не доказывают причинную связь.",
        ]
    )

    OUTPUT_FILE.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(f"\nОтчёт сохранён: {OUTPUT_FILE}")
    print(f"Событий TLOCK: {len(lock_events)}")
    print(f"Исключений блокировки: {len(lock_exceptions)}")


if __name__ == "__main__":
    main()
