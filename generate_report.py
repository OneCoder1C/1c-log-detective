import argparse
from pathlib import Path

from techlog import iter_techlog_events, parse_event
from report import format_summary, save_report
from incident_analysis import analyze_incident_file


def main():
    parser = argparse.ArgumentParser(description="Анализ технологического журнала 1С")
    parser.add_argument(
        "--incident",
        action="store_true",
        help="Сформировать хронологию последнего исключения",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="Путь к файлу технологического журнала",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=20,
        help="Количество событий до и после исключения",
    )
    args = parser.parse_args()

    if args.window < 0:
        parser.error("--window не может быть отрицательным")

    log_dir = Path("1c_logs")
    output_file = Path("incident_report.txt" if args.incident else "report.txt")

    log_files = list(log_dir.rglob("*.log"))

    if not log_files:
        print("В папке 1c_logs не найдены файлы .log")
        return

    if args.log:
        log_file = args.log

        if not log_file.is_file():
            parser.error(f"Файл не найден: {log_file}")
    else:
        log_files = list(log_dir.rglob("*.log"))

        if not log_files:
            print("В папке 1c_logs не найдены файлы .log")
            return

        log_file = max(
            log_files,
            key=lambda path: path.stat().st_size,
        )
    print(f"Обрабатываем файл: {log_file.name}")

    if args.incident:
        report_text = analyze_incident_file(log_file, window=args.window)
    else:

        def read_events():
            with log_file.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:
                for raw_event in iter_techlog_events(file):
                    event = parse_event(raw_event)
                    if event is not None:
                        yield event

        report_text = format_summary(read_events())

    save_report(report_text, output_file)
    print(f"Отчёт сохранён: {output_file.resolve()}")


if __name__ == "__main__":
    main()
