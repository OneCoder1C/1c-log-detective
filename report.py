from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from techlog import TechLogEvent
from exception_groups import (
    extract_guid,
    get_exception_detail,
    normalize_exception,
)
from sql_analysis import extract_sql, get_sql_type, normalize_sql


def format_summary(events: Iterable[TechLogEvent]) -> str:
    """Формирует текстовый отчёт по технологическому журналу 1С."""

    total = 0
    by_type = Counter()
    by_level = Counter()

    exceptions = Counter()
    exception_categories = Counter()
    exception_details = {}

    exception_events = []

    sql_counts = Counter()
    sql_counts_by_source = {
        "SDBL": Counter(),
        "DBV8DBEng": Counter(),
    }

    sql_duration_us_by_source = {
        "SDBL": 0,
        "DBV8DBEng": 0,
    }
    sql_duration_count_by_source = {
        "SDBL": 0,
        "DBV8DBEng": 0,
    }
    sql_over_100ms_by_source = {
        "SDBL": 0,
        "DBV8DBEng": 0,
    }
    sql_over_1s_by_source = {
        "SDBL": 0,
        "DBV8DBEng": 0,
    }
    for event in events:
        total += 1
        by_type[event.event_type] += 1
        by_level[event.level] += 1

        # Анализ исключений.
        if event.event_type == "EXCP" and event.description.strip():
            description = event.description.strip()
            exceptions[description] += 1

            exception_events.append(
                {
                    "timestamp": event.timestamp,
                    "level": event.level,
                    "description": description,
                }
            )

            category = normalize_exception(description)
            detail = get_exception_detail(description)

            exception_categories[category] += 1

            if category not in exception_details:
                exception_details[category] = Counter()

            exception_details[category][detail] += 1

        # Анализ SQL без накопления событий в списке.
        if event.event_type in sql_counts_by_source:
            sql = extract_sql(event.raw_text)

            if sql is not None and get_sql_type(sql) != "OTHER":
                normalized_sql = normalize_sql(sql)
                sql_counts[normalized_sql] += 1
                sql_counts_by_source[event.event_type][normalized_sql] += 1

                # Учитываем длительность SQL-события, если она известна.
                if event.duration_us is not None:
                    source = event.event_type

                    sql_duration_us_by_source[source] += event.duration_us
                    sql_duration_count_by_source[source] += 1

                    if event.duration_us >= 100_000:
                        sql_over_100ms_by_source[source] += 1

                    if event.duration_us >= 1_000_000:
                        sql_over_1s_by_source[source] += 1

    lines = [
        "ОТЧЁТ ПО ТЕХНОЛОГИЧЕСКОМУ ЖУРНАЛУ 1С",
        "=" * 42,
        "",
        f"Всего событий: {total}",
        "",
        "СОБЫТИЯ ПО ТИПАМ:",
    ]

    for event_type, count in sorted(by_type.items()):
        lines.append(f"  {event_type}: {count}")

    lines.extend(["", "СОБЫТИЯ ПО УРОВНЯМ:"])

    for level, count in sorted(by_level.items()):
        lines.append(f"  {level}: {count}")

    lines.extend(["", "СВОДКА ПО КАТЕГОРИЯМ:"])

    if exception_categories:
        for category, count in exception_categories.most_common():
            lines.append(f"  {category}: {count}")

            for detail, detail_count in exception_details[category].most_common():
                if detail != category:
                    lines.append(f"    {detail}: {detail_count}")
    else:
        lines.append("  Исключения с описанием не найдены.")

    lines.extend(["", "ПОСЛЕДОВАТЕЛЬНОСТЬ ИСКЛЮЧЕНИЙ:"])

    if exception_events:
        for item in exception_events:
            description = " ".join(item["description"].split())
            description = description.lstrip(" :")
            guid = extract_guid(description)

            if guid:
                description = description.replace(f"{guid}: ", "").strip()
                description = description.replace(f": {guid}", "").strip()

            if len(description) > 180:
                description = description[:177] + "..."

            line = (
                f"  {item['timestamp']} | "
                f"Уровень: {item['level']} | "
                f"{description}"
            )

            if guid:
                line += f" | GUID: {guid}"

            lines.append(line)
    else:
        lines.append("  Исключения с описанием не найдены.")

    lines.extend(["", "ПОВТОРЯЮЩИЕСЯ ИСКЛЮЧЕНИЯ ПО ВРЕМЕНИ:"])

    exception_timeline = {}

    for item in exception_events:
        description = item["description"]
        category = normalize_exception(description)
        detail = get_exception_detail(description)

        key = (category, detail)

        if key not in exception_timeline:
            exception_timeline[key] = {
                "count": 0,
                "first": item["timestamp"],
                "last": item["timestamp"],
            }

        exception_timeline[key]["count"] += 1
        exception_timeline[key]["last"] = item["timestamp"]

    if exception_timeline:
        repeated_exceptions = sorted(
            exception_timeline.items(),
            key=lambda item: item[1]["count"],
            reverse=True,
        )

        for (category, detail), stats in repeated_exceptions[:10]:
            label = category

            if detail and detail.casefold() != category.casefold():
                label = f"{category} — {detail}"

            label = label.replace("\n", " ")

            if len(label) > 160:
                label = label[:157] + "..."

            lines.append(
                f"  {stats['count']} раз(а) | "
                f"Первое: {stats['first']} | "
                f"Последнее: {stats['last']} | "
                f"{label}"
            )
    else:
        lines.append("  Исключения с описанием не найдены.")

    lines.extend(["", "ТОП ИСКЛЮЧЕНИЙ:"])

    if exceptions:
        for description, count in exceptions.most_common(10):
            if len(description) > 180:
                description = description[:177] + "..."

            lines.append(f"  {count} раз(а): {description}")
    else:
        lines.append("  Исключения с описанием не найдены.")

    lines.extend(["", "АНАЛИЗ SQL-КОМАНД:"])

    sql_type_counts = Counter()

    for sql, count in sql_counts.items():
        sql_type_counts[get_sql_type(sql)] += count

    if sql_type_counts:
        lines.append(
            f"  Всего распознанных SQL-команд: {sum(sql_type_counts.values())}"
        )
        lines.append(f"  Уникальных нормализованных запросов: {len(sql_counts)}")
        lines.append("  Распределение по типам:")

        for command_type, count in sql_type_counts.most_common():
            lines.append(f"    {command_type}: {count}")

        lines.append("  ТОП-10 повторяющихся SQL:")

        for sql, count in sql_counts.most_common(10):
            if len(sql) > 180:
                sql = sql[:177] + "..."

            lines.append(f"    {count} раз(а): {sql}")
    else:
        lines.append("  Распознанные SQL-команды не найдены.")

    # Отдельная статистика по каждому источнику SQL.
    lines.extend(["", "АНАЛИЗ SQL ПО ИСТОЧНИКАМ:"])

    for source in ("SDBL", "DBV8DBEng"):
        source_counts = sql_counts_by_source[source]

        lines.append(f"  {source}:")
        lines.append(f"    Распознанных SQL-команд: {sum(source_counts.values())}")
        lines.append(f"    Уникальных нормализованных запросов: {len(source_counts)}")

        duration_count = sql_duration_count_by_source[source]
        duration_ms = sql_duration_us_by_source[source] / 1000

        lines.append(f"    SQL-событий с известной длительностью: {duration_count}")
        lines.append(f"    Суммарная длительность SQL-событий: {duration_ms:.3f} мс")

        lines.append(
            f"    SQL-событий длительностью от 100 мс: "
            f"{sql_over_100ms_by_source[source]}"
        )
        lines.append(
            f"    SQL-событий длительностью от 1 секунды: "
            f"{sql_over_1s_by_source[source]}"
        )

        if not source_counts:
            lines.append("    Распознанные SQL-команды не найдены.")
            continue

        source_type_counts = Counter()

        for sql, count in source_counts.items():
            source_type_counts[get_sql_type(sql)] += count

        lines.append("    Распределение по типам:")

        for command_type, count in source_type_counts.most_common():
            lines.append(f"      {command_type}: {count}")

        lines.append("    ТОП-10 повторяющихся SQL:")

        for sql, count in source_counts.most_common(10):
            if len(sql) > 180:
                sql = sql[:177] + "..."

            lines.append(f"      {count} раз(а): {sql}")

    return "\n".join(lines)


def save_report(report_text: str, output_path: str | Path) -> None:
    """Сохраняет текстовый отчёт в файл."""
    path = Path(output_path)
    path.write_text(report_text, encoding="utf-8")
