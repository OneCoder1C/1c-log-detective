from techlog import parse_event
from report import format_summary, save_report


def test_format_summary():
    events = [
        parse_event("03:16.700001-0,EXCP,2,level=WARNING"),
        parse_event("03:16.700002-0,SDBL,1,level=DEBUG"),
    ]

    events = [event for event in events if event is not None]

    report = format_summary(events)

    assert "ОТЧЁТ ПО ТЕХНОЛОГИЧЕСКОМУ ЖУРНАЛУ 1С" in report
    assert "Всего событий: 2" in report
    assert "EXCP: 1" in report
    assert "SDBL: 1" in report
    assert "DEBUG: 1" in report
    assert "WARNING: 1" in report


def test_save_report(tmp_path):
    report_file = tmp_path / "report.txt"
    report_text = "Отчёт по журналу 1С\nВсего событий: 5"

    save_report(report_text, report_file)

    assert report_file.exists()
    assert report_file.read_text(encoding="utf-8") == report_text


def test_format_summary_includes_top_exceptions():
    events = [
        parse_event(
            "03:16.700001-0,EXCP,2,level=WARNING," "Descr='Ошибка подключения'"
        ),
        parse_event(
            "03:16.700002-0,EXCP,3,level=WARNING," "Descr='Ошибка подключения'"
        ),
        parse_event("03:16.700003-0,EXCP,4,level=WARNING," "Descr='Ошибка доступа'"),
    ]

    events = [event for event in events if event is not None]
    report_text = format_summary(events)

    assert "ТОП ИСКЛЮЧЕНИЙ" in report_text
    assert "Ошибка подключения" in report_text
    assert "2" in report_text
    assert "Ошибка доступа" in report_text


def test_format_summary_truncates_long_exception():
    long_description = "Ошибка " + "А" * 250
    event = parse_event(
        "03:16.700001-0,EXCP,2,level=WARNING," f"Descr='{long_description}'"
    )

    report_text = format_summary([event])

    assert "ТОП ИСКЛЮЧЕНИЙ" in report_text
    assert "..." in report_text


def test_format_summary_groups_exceptions_by_category():
    from exception_groups import normalize_exception

    descriptions = [
        "Не удалось заблокировать запись таблицы ACTIVEUSERS",
        "Не удалось заблокировать запись таблицы DATAZONEOBJECTLOCKS",
        "Файл не обнаружен: keystor.dat",
    ]

    categories = [normalize_exception(item) for item in descriptions]

    assert categories.count("Не удалось заблокировать запись") == 2
    assert categories.count("Файл не обнаружен") == 1


def test_format_summary_accepts_generator():
    raw_events = [
        "03:16.700001-0,EXCP,2,level=WARNING,Descr='Ошибка подключения'",
        "03:16.700002-0,SDBL,1,level=INFO",
    ]

    events = (
        event for event in (parse_event(raw) for raw in raw_events) if event is not None
    )

    report_text = format_summary(events)

    assert "Всего событий: 2" in report_text
    assert "EXCP: 1" in report_text
    assert "SDBL: 1" in report_text
    assert "Ошибка подключения" in report_text


def test_format_summary_sql_counts_match_source_totals():
    raw_events = [
        "03:16.700001-1500,SDBL,1,level=DEBUG,Sdbl='SELECT * FROM TableA'",
        "03:16.700002-250000,SDBL,2,level=DEBUG,Sdbl='SELECT * FROM TableB'",
        "03:16.700003-1000000,DBV8DBEng,3,level=DEBUG,Sql='SELECT * FROM TableA'",
    ]

    events = (
        event for event in (parse_event(raw) for raw in raw_events) if event is not None
    )

    report_text = format_summary(events)

    assert "Всего распознанных SQL-команд: 3" in report_text
    assert "Уникальных нормализованных запросов: 2" in report_text

    assert "SDBL:" in report_text
    assert "Распознанных SQL-команд: 2" in report_text
    assert "Уникальных нормализованных запросов: 2" in report_text

    assert "DBV8DBEng:" in report_text
    assert "Распознанных SQL-команд: 1" in report_text
    assert "Уникальных нормализованных запросов: 1" in report_text

    assert "SDBL:" in report_text
    assert "SQL-событий с известной длительностью: 2" in report_text

    assert "DBV8DBEng:" in report_text
    assert "SQL-событий с известной длительностью: 1" in report_text

    assert "Суммарная длительность SQL-событий: 251.500 мс" in report_text
    assert "Суммарная длительность SQL-событий: 1000.000 мс" in report_text

    assert "SQL-событий длительностью от 100 мс: 1" in report_text
    assert "SQL-событий длительностью от 1 секунды: 0" in report_text
    assert "SQL-событий длительностью от 1 секунды: 1" in report_text


def test_format_summary_keeps_lock_objects_separate_in_timeline():
    raw_events = [
        "03:16.700001-0,EXCP,1,level=WARNING,Descr=\"Не удалось заблокировать запись не выполнено 'ACTIVEUSERS'\"",
        "03:16.700002-0,EXCP,2,level=WARNING,Descr=\"Не удалось заблокировать запись не выполнено 'ACTIVEUSERS'\"",
        "03:16.700003-0,EXCP,3,level=WARNING,Descr=\"Не удалось заблокировать запись не выполнено 'DATAZONEOBJECTLOCKS'\"",
    ]

    events = [
        event for event in (parse_event(raw) for raw in raw_events) if event is not None
    ]

    report_text = format_summary(events)

    assert "ПОВТОРЯЮЩИЕСЯ ИСКЛЮЧЕНИЯ ПО ВРЕМЕНИ" in report_text
    assert "2 раз(а)" in report_text
    assert "Не удалось заблокировать запись — ACTIVEUSERS" in report_text
    assert "Не удалось заблокировать запись — DATAZONEOBJECTLOCKS" in report_text


def test_extract_guid_from_exception_description():
    from exception_groups import extract_guid

    description = (
        "src\\backend\\src\\FileJobManagerImpl.cpp(1340): "
        "a01f465c-ed70-442e-ada5-847668d7a41c: "
        "Неверно указан пользователь или пароль"
    )

    assert extract_guid(description) == "a01f465c-ed70-442e-ada5-847668d7a41c"


def test_extract_guid_returns_none_when_guid_is_missing():
    from exception_groups import extract_guid

    description = "Неверно указан пользователь или пароль"

    assert extract_guid(description) is None


def test_format_summary_includes_exception_context():
    raw_events = [
        "03:16.700001-0,EXCP,2,level=WARNING,"
        "OSThread=456,Usr=Иванов,Context=МодульСеанса,"
        "Descr='Не удалось заблокировать запись не выполнено "
        "'ACTIVEUSERS''",
    ]

    events = [
        event for event in (parse_event(raw) for raw in raw_events) if event is not None
    ]

    report_text = format_summary(events)

    assert "Пользователи: Иванов" in report_text
    assert "Потоки: 456" in report_text
    assert "Контексты: МодульСеанса" in report_text
