import argparse
from pathlib import Path

from incident_analysis import analyze_incident_file_correlated
from html_report.generator import generate_html_report


def main():
    parser = argparse.ArgumentParser(
        description="Генерация интерактивного HTML-отчёта по журналу 1С"
    )
    parser.add_argument("log_file", help="Путь к технологическому журналу")
    parser.add_argument("output_file", help="Путь для сохранения HTML-отчёта")

    args = parser.parse_args()

    log_file = Path(args.log_file)
    output_file = Path(args.output_file)

    if not log_file.is_file():
        parser.error(f"Файл журнала не найден: {log_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Читаем журнал: {log_file}")
    print(f"Размер: {log_file.stat().st_size / 1024 / 1024:.2f} МБ")

    incident = analyze_incident_file_correlated(str(log_file))

    if incident.get("error"):
        print(f"Ошибка анализа: {incident['error']}")
        return

    chain = incident.get("chain") or {}
    evidence = incident.get("evidence") or {}

    print(f"Событий в цепочке: {len(chain.get('events', []))}")
    print(f"Событий до ошибки: {len(chain.get('before', []))}")
    print(f"Событий после ошибки: {len(chain.get('after', []))}")
    print(f"Связанных событий: {len(chain.get('related_events', []))}")
    print(f"Диагностических признаков: {len(evidence.get('findings', []))}")

    output = generate_html_report(incident, output_file)

    print(f"\nHTML-отчёт создан: {output.resolve()}")
    print(f"Размер отчёта: {output.stat().st_size / 1024:.2f} КБ")


if __name__ == "__main__":
    main()
