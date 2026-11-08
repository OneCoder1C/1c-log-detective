import sys

from techlog_discovery import discover_techlog_process_dirs

from user_analysis import analyze_user_events, format_user_analysis

from incident_analysis import (
    analyze_incident_file_correlated,
    format_correlated_incident,
)


def analyze_techlog(log_file, report_file):
    print("Режим: анализ технологического журнала 1С")
    print("=" * 40)

    try:
        incident = analyze_incident_file_correlated(log_file)

        if incident["error"]:
            report = incident["error"]
        else:
            report = format_correlated_incident(incident)

        print(report)

        with open(report_file, "w", encoding="utf-8") as file:
            file.write(report + "\n")

        print(f"\nОтчёт сохранён в файл {report_file}")

    except FileNotFoundError:
        print(f"Не удалось найти файл: {log_file}")
        sys.exit(1)
    except OSError as error:
        print(f"Ошибка чтения или сохранения файла: {error}")
        sys.exit(1)


def analyze_user(log_file, user, report_file):
    print("Режим: история активности пользователя 1С")
    print("=" * 40)

    try:
        result = analyze_user_events(log_file, user=user)
        report = format_user_analysis(result)

        print(report)

        with open(report_file, "w", encoding="utf-8") as file:
            file.write(report + "\n")

        print(f"\nОтчёт сохранён в файл {report_file}")

    except FileNotFoundError:
        print(f"Не удалось найти файл: {log_file}")
        sys.exit(1)
    except OSError as error:
        print(f"Ошибка чтения или сохранения файла: {error}")
        sys.exit(1)


def select_techlog_directory():
    """Показывает найденные процессы 1С и возвращает выбранный каталог."""
    process_dirs = discover_techlog_process_dirs()

    if not process_dirs:
        print("Каталоги технологического журнала 1С не найдены.")
        print("Проверь настройки logcfg.xml и наличие файлов .log.")
        return None

    print("\nНайдены каталоги технологического журнала:")

    for index, process_dir in enumerate(process_dirs, start=1):
        log_files = list(process_dir.glob("*.log"))
        print(f"{index}. {process_dir.name} " f"({len(log_files)} файлов)")

    try:
        choice = int(input("\nВыбери номер процесса: "))
    except (ValueError, EOFError):
        print("Некорректный выбор.")
        return None

    if choice < 1 or choice > len(process_dirs):
        print("Процесс с таким номером не найден.")
        return None

    return process_dirs[choice - 1]


def main():
    print("1C Log Detective")
    print("=" * 40)

    if len(sys.argv) == 1:
        log_file = select_techlog_directory()

        if log_file is None:
            sys.exit(1)

        analyze_techlog(log_file, "techlog_report.txt")
        return

    log_file = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2].upper() == "USER":
        if len(sys.argv) < 4:
            print(
                "Укажи имя пользователя: "
                'python main.py "путь_к_логу" USER "Имя пользователя"'
            )
            sys.exit(1)

        user = sys.argv[3]
        report_file = sys.argv[4] if len(sys.argv) > 4 else "user_report.txt"

        analyze_user(log_file, user, report_file)
        return

    report_file = sys.argv[2] if len(sys.argv) > 2 else "report.txt"

    if len(sys.argv) > 3 and sys.argv[3].upper() == "TECHLOG":
        analyze_techlog(log_file, report_file)
        return

    event_filter = sys.argv[3].upper() if len(sys.argv) > 3 else "ALL"
    allowed_filters = ["ALL", "ERROR", "WARNING", "CRITICAL"]

    if event_filter not in allowed_filters:
        print(f"Неизвестный фильтр: {event_filter}")
        print("Допустимые фильтры: ERROR, WARNING, CRITICAL, ALL")
        sys.exit(1)

    errors = 0
    warnings = 0
    criticals = 0
    total_lines = 0

    filtered_errors = 0
    filtered_warnings = 0
    filtered_criticals = 0

    report_lines = []
    recommendations = []

    try:
        with open(log_file, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                total_lines += 1

                if "CRITICAL" in line:
                    event_type = "CRITICAL"
                    message = "[КРИТИЧЕСКАЯ ОШИБКА] " + line
                    criticals += 1
                    recommendations.append(
                        "CRITICAL: проверить аварийное завершение задания "
                        "и подробности события в журнале регистрации 1С."
                    )

                elif "ERROR" in line:
                    event_type = "ERROR"
                    message = "[ОШИБКА] " + line
                    errors += 1

                    if "блокировк" in line.lower():
                        recommendations.append(
                            "ERROR: проверить конкурирующие транзакции, "
                            "ожидания и блокировки в СУБД."
                        )
                    elif "соединени" in line.lower():
                        recommendations.append(
                            "ERROR: проверить доступность сервера 1С, "
                            "СУБД и сетевого подключения."
                        )

                elif "WARNING" in line:
                    event_type = "WARNING"
                    message = "[ПРЕДУПРЕЖДЕНИЕ] " + line
                    warnings += 1

                    if "длительн" in line.lower() or "долг" in line.lower():
                        recommendations.append(
                            "WARNING: проверить длительность выполнения "
                            "запроса и его план."
                        )

                else:
                    continue

                if event_filter == "ALL" or event_filter == event_type:
                    if event_type == "ERROR":
                        filtered_errors += 1
                    elif event_type == "WARNING":
                        filtered_warnings += 1
                    elif event_type == "CRITICAL":
                        filtered_criticals += 1

                    print(message)
                    report_lines.append(message)

    except FileNotFoundError:
        print(f"Не удалось найти файл: {log_file}")
        sys.exit(1)

    if criticals > 0:
        status = "Обнаружены критические ошибки, требуется срочная проверка"
    elif errors > 0:
        status = "Обнаружены ошибки, требуется проверка"
    else:
        status = "Ошибок не обнаружено"

    if filtered_criticals > 0:
        filtered_status = "В выбранных событиях обнаружены критические ошибки"
    elif filtered_errors > 0:
        filtered_status = "В выбранных событиях обнаружены ошибки"
    elif filtered_warnings > 0:
        filtered_status = "В выбранных событиях есть предупреждения"
    else:
        filtered_status = "В выбранных событиях ошибок и предупреждений нет"

    report_lines.append("-" * 40)
    report_lines.append("ИТОГОВЫЙ ОТЧЁТ")
    report_lines.append(f"Всего строк журнала: {total_lines}")
    report_lines.append(f"Критических ошибок: {criticals}")
    report_lines.append(f"Всего ошибок: {errors}")
    report_lines.append(f"Всего предупреждений: {warnings}")
    report_lines.append(f"Фильтр: {event_filter}")
    report_lines.append(f"Общий статус журнала: {status}")
    report_lines.append(f"Статус выбранного фильтра: {filtered_status}")

    report_lines.append("")
    report_lines.append("РЕКОМЕНДАЦИИ")

    if event_filter == "ALL":
        filtered_recommendations = recommendations
    else:
        filtered_recommendations = [
            recommendation
            for recommendation in recommendations
            if recommendation.startswith(event_filter + ":")
        ]

    if filtered_recommendations:
        for recommendation in filtered_recommendations:
            report_lines.append(f"- {recommendation}")
    else:
        report_lines.append("Рекомендаций нет.")

    report_lines.append(f"Статус: {status}")
    report_lines.append("Анализ завершён.")

    print("-" * 40)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print(f"Всего строк журнала: {total_lines}")
    print(f"Критических ошибок: {criticals}")
    print(f"Всего ошибок: {errors}")
    print(f"Всего предупреждений: {warnings}")
    print(f"Фильтр: {event_filter}")
    print(f"Общий статус журнала: {status}")
    print(f"Статус выбранного фильтра: {filtered_status}")

    print()
    if filtered_recommendations:
        for recommendation in filtered_recommendations:
            print(f"- {recommendation}")
    else:
        print("Рекомендаций нет.")

    print("Анализ завершён.")

    try:
        with open(report_file, "w", encoding="utf-8") as report:
            report.write("\n".join(report_lines) + "\n")

        print(f"Отчёт сохранён в файл {report_file}")

    except OSError as error:
        print(f"Не удалось сохранить отчёт: {error}")


if __name__ == "__main__":
    main()
