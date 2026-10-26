import sys


def main():
    print("1C Log Detective")
    print("=" * 40)

    log_file = sys.argv[1] if len(sys.argv) > 1 else "sample_log.txt"
    report_file = sys.argv[2] if len(sys.argv) > 2 else "report.txt"
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
