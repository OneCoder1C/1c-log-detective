from techlog import TechLogEvent
from incident_analysis import build_incident_timeline


def test_finds_last_exception():
    events = [
        TechLogEvent("10:00.000", "SDBL", "INFO", "event 1", "Запрос", None),
        TechLogEvent("10:00.100", "EXCP", "ERROR", "event 2", "Первая ошибка", None),
        TechLogEvent("10:00.200", "SDBL", "INFO", "event 3", "Запрос", None),
        TechLogEvent("10:00.300", "EXCP", "ERROR", "event 4", "Последняя ошибка", None),
    ]

    incident = build_incident_timeline(events, window=1)

    assert incident["error"] is None
    assert incident["target"]["description"] == "Последняя ошибка"
    assert len(incident["timeline"]) == 2
    assert incident["timeline"][1]["is_target_error"] is True


def test_returns_message_when_no_exceptions():
    events = [
        TechLogEvent("10:00.000", "SDBL", "INFO", "event 1", "Запрос", None),
    ]

    incident = build_incident_timeline(events)

    assert incident["error"] == "В журнале не найдено исключений EXCP."
    assert incident["timeline"] == []


def test_can_select_specific_exception():
    events = [
        TechLogEvent("10:00.000", "EXCP", "ERROR", "event 1", "Первая ошибка", None),
        TechLogEvent("10:00.100", "SDBL", "INFO", "event 2", "Запрос", None),
        TechLogEvent("10:00.200", "EXCP", "ERROR", "event 3", "Вторая ошибка", None),
    ]

    incident = build_incident_timeline(events, error_index=0, window=1)

    assert incident["target"]["description"] == "Первая ошибка"
    assert incident["timeline"][0]["is_target_error"] is True


def test_timeline_extracts_user_thread_and_context():
    raw_text = (
        "10:00.000,EXCP,1,level=ERROR,"
        'process=123,OSThread=456,Usr="Иванов",'
        'Context="Документ.ЗаказКлиента",'
        'Descr="Ошибка проведения"'
    )

    event = TechLogEvent(
        "10:00.000",
        "EXCP",
        "ERROR",
        raw_text,
        "Ошибка проведения",
        None,
    )

    incident = build_incident_timeline([event])
    item = incident["timeline"][0]

    assert item["user"] == "Иванов"
    assert item["thread"] == "456"
    assert item["context"] == "Документ.ЗаказКлиента"


from incident_analysis import format_incident_timeline


def test_formats_incident_report():
    events = [
        TechLogEvent(
            "10:00.000",
            "EXCP",
            "ERROR",
            '10:00.000,EXCP,1,level=ERROR,Descr="Ошибка проведения"',
            "Ошибка проведения",
            None,
        )
    ]

    incident = build_incident_timeline(events)
    report = format_incident_timeline(incident)

    assert "РАЗБОР ИНЦИДЕНТА 1С" in report
    assert "Ошибка проведения" in report
    assert "ХРОНОЛОГИЯ" in report


from incident_analysis import analyze_incident_file


def test_analyze_incident_file_finds_last_exception(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        '10:00.000,EXCP,1,level=ERROR,Descr="Первая ошибка"\n'
        '10:00.100,SDBL,2,level=INFO,Descr="Запрос"\n'
        '10:00.200,EXCP,3,level=ERROR,Descr="Последняя ошибка"\n',
        encoding="utf-8",
    )

    report = analyze_incident_file(log_file, window=1)

    assert "Последняя ошибка" in report
    assert "Первая ошибка" not in report


def test_incident_window_zero_shows_only_error(tmp_path):
    log_file = tmp_path / "empty_window.log"
    log_file.write_text(
        '10:00.000,SDBL,1,level=INFO,Descr="До ошибки"\n'
        '10:00.100,EXCP,2,level=ERROR,Descr="Целевая ошибка"\n'
        '10:00.200,SDBL,3,level=INFO,Descr="После ошибки"\n',
        encoding="utf-8",
    )

    report = analyze_incident_file(log_file, window=0)

    assert "Целевая ошибка" in report
    assert "До ошибки" not in report
    assert "После ошибки" not in report


def test_incident_file_without_exceptions(tmp_path):
    log_file = tmp_path / "no_errors.log"
    log_file.write_text(
        '10:00.000,SDBL,1,level=INFO,Descr="Обычный запрос"\n',
        encoding="utf-8",
    )

    report = analyze_incident_file(log_file)

    assert report == "В журнале не найдено исключений EXCP."
