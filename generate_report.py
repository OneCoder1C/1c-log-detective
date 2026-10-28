from pathlib import Path

from techlog import iter_techlog_events, parse_event
from report import format_summary, save_report


log_dir = Path("1c_logs")
output_file = Path("report.txt")


log_files = list(log_dir.rglob("*.log"))

if not log_files:
    print("В папке 1c_logs не найдены файлы .log")
else:
    log_file = max(log_files, key=lambda path: path.stat().st_size)

    print(f"Обрабатываем файл: {log_file.name}")

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

    print("Обработка событий завершена.")
    print(f"Отчёт сохранён: {output_file.resolve()}")
