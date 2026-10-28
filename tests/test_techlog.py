from techlog import (
    is_event_start,
    split_events,
    iter_techlog_events,
    parse_event,
    summarize_events,
    summarize_event_stream,
    read_techlog_file,
)


def test_recognizes_event_start():
    line = "03:16.700001-0,EXCP,2,level=WARNING"

    assert is_event_start(line) is True


def test_rejects_continuation_line():
    line = "Продолжение описания ошибки"

    assert is_event_start(line) is False


def test_split_multiline_events():
    lines = [
        "03:16.700001-0,EXCP,2,level=WARNING",
        "Описание ошибки",
        "Продолжение описания",
        "03:16.700002-0,TLOCK,2,level=INFO",
    ]

    events = split_events(lines)

    assert len(events) == 2
    assert len(events[0].splitlines()) == 3
    assert events[1].startswith("03:16.700002-0,TLOCK")


def test_split_empty_input():
    assert split_events([]) == []


def test_parse_event_fields():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING," "process=1cv8c,Exception=0874860b-1234"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.timestamp == "03:16.700001-0"
    assert event.event_type == "EXCP"
    assert event.level == "WARNING"
    assert event.raw_text == raw_text


def test_parse_event_info_level():
    raw_text = "03:16.700002-0,TLOCK,2,level=INFO"

    event = parse_event(raw_text)

    assert event is not None
    assert event.level == "INFO"


def test_parse_event_without_level():
    raw_text = "03:16.700003-0,EXCP,2,process=1cv8c"

    event = parse_event(raw_text)

    assert event is not None
    assert event.level == "UNKNOWN"


def test_parse_event_invalid_input():
    assert parse_event("Это обычный текст") is None


def test_parse_realistic_excp_event():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING,"
        "process=1cv8c,OSThread=23124,"
        "Exception=0874860b-1234,Descr='Ошибка программного лицензирования'"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.event_type == "EXCP"
    assert event.level == "WARNING"
    assert "Ошибка программного лицензирования" in event.raw_text


def test_parse_event_description():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING,"
        "Descr='Ошибка программного лицензирования'"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.description == "Ошибка программного лицензирования"


def test_parse_event_description_with_comma():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING,"
        "Descr='Ошибка лицензии, требуется проверка'"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.description == "Ошибка лицензии, требуется проверка"


def test_parse_event_without_description():
    raw_text = "03:16.700001-0,TLOCK,2,level=INFO"

    event = parse_event(raw_text)

    assert event is not None
    assert event.description == ""


def test_parse_multiline_event_description():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING,"
        "Descr='Ошибка программного лицензирования\n"
        "После получения лицензии удалены:\n"
        "BIOS_0: American Megatrends'"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert "Ошибка программного лицензирования" in event.description
    assert "После получения лицензии удалены:" in event.description
    assert "BIOS_0: American Megatrends" in event.description


def test_parse_event_description_with_double_quotes():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING,"
        'Descr="Ошибка программного лицензирования"'
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.description == "Ошибка программного лицензирования"


def test_parse_event_description_followed_by_newline():
    raw_text = (
        "03:16.700001-0,EXCP,2,level=WARNING,"
        'Descr="Ошибка программного лицензирования"'
        "\n"
        "04:17.552005-1,SDBL,1,level=INFO"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.description == "Ошибка программного лицензирования"


def test_summarize_events_counts_types_and_levels():
    events = [
        parse_event("03:16.700001-0,EXCP,2,level=WARNING,Descr='Ошибка 1'"),
        parse_event("03:16.700002-0,EXCP,3,level=ERROR,Descr='Ошибка 2'"),
        parse_event("03:16.700003-0,SDBL,1,level=INFO"),
    ]

    events = [event for event in events if event is not None]

    summary = summarize_events(events)

    assert summary["total"] == 3
    assert summary["by_type"] == {"EXCP": 2, "SDBL": 1}
    assert summary["by_level"] == {
        "WARNING": 1,
        "ERROR": 1,
        "INFO": 1,
    }


def test_summarize_empty_events():
    summary = summarize_events([])

    assert summary["total"] == 0
    assert summary["by_type"] == {}
    assert summary["by_level"] == {}


def test_read_techlog_file(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "03:16.700001-0,EXCP,2,level=WARNING,Descr='Ошибка 1'\n"
        "03:16.700002-0,SDBL,1,level=INFO\n",
        encoding="utf-8",
    )

    events = read_techlog_file(log_file)

    assert len(events) == 2
    assert events[0].event_type == "EXCP"
    assert events[0].level == "WARNING"
    assert events[1].event_type == "SDBL"
    assert events[1].level == "INFO"


def test_read_empty_techlog_file(tmp_path):
    log_file = tmp_path / "empty.log"
    log_file.write_text("", encoding="utf-8")

    events = read_techlog_file(log_file)

    assert events == []


def test_summarize_events_total_matches_counts():
    events = [
        parse_event("03:16.700001-0,EXCP,2,level=WARNING"),
        parse_event("03:16.700002-0,SDBL,1,level=DEBUG"),
        parse_event("03:16.700003-0,SDBL,2,level=DEBUG"),
        parse_event("03:16.700004-0,SESN,1,level=INFO"),
    ]

    events = [event for event in events if event is not None]
    summary = summarize_events(events)

    assert summary["total"] == 4
    assert sum(summary["by_type"].values()) == 4
    assert sum(summary["by_level"].values()) == 4


def test_iter_techlog_events_matches_split_events():
    lines = [
        "03:16.700001-0,EXCP,2,level=WARNING",
        "Описание ошибки",
        "Продолжение описания",
        "03:16.700002-0,TLOCK,2,level=INFO",
        "03:16.700003-0,SDBL,1,level=DEBUG",
    ]

    streamed_events = list(iter_techlog_events(lines))
    expected_events = split_events(lines)

    assert streamed_events == expected_events


def test_iter_techlog_events_empty_input():
    assert list(iter_techlog_events([])) == []


def test_summarize_events_counts_types_and_levels_from_iterator():
    events = (
        parse_event(line)
        for line in [
            "03:16.700001-0,EXCP,2,level=WARNING",
            "03:16.700002-0,EXCP,3,level=ERROR",
            "03:16.700003-0,SDBL,1,level=INFO",
        ]
    )

    events = [event for event in events if event is not None]
    summary = summarize_events(events)

    assert summary["total"] == 3
    assert summary["by_type"] == {"EXCP": 2, "SDBL": 1}
    assert summary["by_level"] == {
        "WARNING": 1,
        "ERROR": 1,
        "INFO": 1,
    }


def test_summarize_event_stream_accepts_generator():
    raw_events = (
        line
        for line in [
            "03:16.700001-0,EXCP,2,level=WARNING",
            "03:16.700002-0,EXCP,3,level=ERROR",
            "03:16.700003-0,SDBL,1,level=INFO",
        ]
    )

    events = (
        event for event in (parse_event(raw) for raw in raw_events) if event is not None
    )

    summary = summarize_event_stream(events)

    assert summary["total"] == 3
    assert summary["by_type"] == {"EXCP": 2, "SDBL": 1}
    assert summary["by_level"] == {
        "WARNING": 1,
        "ERROR": 1,
        "INFO": 1,
    }


def test_parse_event_preserves_sql_timing_properties():
    raw_text = (
        "03:16.700001-0,SDBL,1,level=DEBUG," "Duration=1500,process=1234,Sql='SELECT 1'"
    )

    event = parse_event(raw_text)

    assert event is not None
    assert event.event_type == "SDBL"
    assert event.raw_text == raw_text
    assert "Duration=1500" in event.raw_text


def test_parse_event_extracts_duration():
    raw_text = "03:16.700001-1500,SDBL,1,level=DEBUG"

    event = parse_event(raw_text)

    assert event is not None
    assert event.timestamp == "03:16.700001-1500"
    assert event.duration_us == 1500


def test_parse_event_extracts_zero_duration():
    raw_text = "03:16.700001-0,SDBL,1,level=DEBUG"

    event = parse_event(raw_text)

    assert event is not None
    assert event.duration_us == 0
