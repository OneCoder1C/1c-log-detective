import json

from html_report.generator import generate_html_report


def sample_result():
    error = {
        "index": 1,
        "timestamp": "2026-10-26 09:16:04",
        "event_type": "EXCP",
        "description": "Тестовое исключение",
        "is_error": True,
        "exception_detail": "Детали исключения",
    }
    before = {
        "index": 0,
        "timestamp": "2026-10-26 09:16:03",
        "event_type": "SDBL",
        "description": "SQL-запрос",
        "sql": "SELECT * FROM Документ",
    }
    return {
        "error": None,
        "chain": {
            "user": "Тестовый пользователь",
            "process": "100",
            "thread": "200",
            "context": "Документ.Тест",
            "error_index": 1,
            "events": [before, error],
            "before": [before],
            "after": [],
            "related_events": [],
        },
        "evidence": {
            "findings": [
                {
                    "code": "SDBL_BEFORE_EXCP",
                    "title": "SQL перед ошибкой",
                    "count": 1,
                    "confidence": "Признак",
                    "events": [before],
                }
            ],
            "related_findings": [],
            "related_events_count": 0,
        },
    }


def test_generates_html_file(tmp_path):
    output = tmp_path / "report.html"

    result = generate_html_report(sample_result(), output)

    assert result == output
    assert output.exists()
    assert output.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_html_contains_report_sections(tmp_path):
    output = tmp_path / "report.html"
    generate_html_report(sample_result(), output)
    html = output.read_text(encoding="utf-8")

    assert "Временная шкала" in html
    assert "Центральное исключение" in html
    assert "События других потоков" in html
    assert "Диагностические признаки" in html
    assert "Что проверить дальше" in html
    assert 'id="next-checks"' in html
    assert "function renderNextChecks()" in html


def test_html_contains_embedded_data(tmp_path):
    output = tmp_path / "report.html"
    generate_html_report(sample_result(), output)
    html = output.read_text(encoding="utf-8")

    assert "Тестовый пользователь" in html
    assert "SELECT * FROM Документ" in html
    assert "Тестовое исключение" in html


def test_untrusted_script_text_is_not_embedded_as_html(tmp_path):
    result = sample_result()
    result["chain"]["events"][1]["description"] = "</script><script>alert(1)</script>"
    result["chain"]["events"][1]["is_error"] = True

    output = tmp_path / "report.html"
    generate_html_report(result, output)
    html = output.read_text(encoding="utf-8")

    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html


def test_creates_missing_output_directory(tmp_path):
    output = tmp_path / "nested" / "reports" / "incident.html"

    generate_html_report(sample_result(), output)

    assert output.exists()


def test_html_is_standalone(tmp_path):
    output = tmp_path / "report.html"
    generate_html_report(sample_result(), output)
    html = output.read_text(encoding="utf-8")

    assert "https://" not in html
    assert "<style>" in html
    assert "<script>" in html


def test_finding_contains_expandable_events(tmp_path):
    output = tmp_path / "report.html"

    generate_html_report(sample_result(), output)

    html = output.read_text(encoding="utf-8")

    assert "События признака (" in html
    assert "finding.events" in html
    assert "renderEvent(event)" in html
    assert "SQL перед ошибкой" in html
    assert "SQL-запрос" in html


def test_html_contains_bug_report_export(tmp_path):
    output = tmp_path / "report.html"

    generate_html_report(sample_result(), output)

    html = output.read_text(encoding="utf-8")

    assert "Экспорт отчёта" in html
    assert 'id="export-bug-report"' in html
    assert "function buildBugReportMarkdown()" in html
    assert "text/markdown;charset=utf-8" in html
    assert "bug-report-" in html
