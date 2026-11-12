import pytest

from techlog import parse_event
from incident_correlation import (
    build_incident_chain,
    find_sql_event_pairs,
    get_correlation_fields,
    is_same_execution,
    is_same_process_thread,
)


def make_event(raw_text):
    event = parse_event(raw_text)
    assert event is not None
    return event


def test_builds_chain_for_same_user_process_and_thread():
    events = [
        make_event(
            "10:00:00.000-0,SDBL,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,Context="Документ.Заказ"'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR,"
            'Usr="Иванов",process=123,OSThread=456,Context="Документ.Заказ"'
        ),
        make_event(
            "10:00:02.000-0,SDBL,3,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,Context="Документ.Заказ"'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert len(result["events"]) == 3
    assert len(result["before"]) == 1
    assert len(result["after"]) == 1
    assert result["user"] == "Иванов"
    assert result["process"] == "123"
    assert result["thread"] == "456"


def test_does_not_mix_different_threads():
    anchor = {
        "user": "Иванов",
        "process": "123",
        "thread": "456",
        "context": "",
    }

    candidate = {
        "user": "Иванов",
        "process": "123",
        "thread": "789",
        "context": "",
    }

    assert not is_same_execution(anchor, candidate)


def test_does_not_mix_different_processes():
    anchor = {
        "user": "Иванов",
        "process": "123",
        "thread": "456",
        "context": "",
    }

    candidate = {
        "user": "Иванов",
        "process": "999",
        "thread": "456",
        "context": "",
    }

    assert not is_same_execution(anchor, candidate)


def test_rejects_event_without_process_or_thread():
    anchor = {
        "user": "Иванов",
        "process": "123",
        "thread": "456",
        "context": "",
    }

    candidate = {
        "user": "Иванов",
        "process": "123",
        "thread": "",
        "context": "",
    }

    assert not is_same_execution(anchor, candidate)


def test_rejects_non_exception_center():
    events = [
        make_event(
            "10:00:00.000-0,SDBL,1,level=INFO," 'Usr="Иванов",process=123,OSThread=456'
        )
    ]

    try:
        build_incident_chain(events, error_index=0)
        assert False, "Ожидалась ошибка ValueError"
    except ValueError:
        pass


def test_extracts_lock_details_from_tlock():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,'
            'Regions="РегистрНакопления.Остатки",'
            'Locks="Exclusive ID=123 Fld1=456"'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    lock_event = result["before"][0]

    assert "lock" in lock_event
    assert lock_event["lock"]["lock_mode"] == "EXCLUSIVE"
    assert lock_event["lock"]["resource_id"] == "123"


def test_extracts_sql_details_from_sdbl():
    events = [
        make_event(
            "10:00:00.000-0,SDBL,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,Rows=15,'
            "Sdbl=SELECT * FROM _Document123"
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    sql_event = result["before"][0]

    assert sql_event["sql_type"] == "SELECT"
    assert "_Document123" in sql_event["sql_tables"]
    assert sql_event["rows"] == 15


def test_extracts_sql_details_from_dbv8dbeng():
    events = [
        make_event(
            "10:00:00.000-0,DBV8DBEng,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,'
            "Sql=SELECT * FROM _Reference123"
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    sql_event = result["before"][0]

    assert sql_event["event_type"] == "DBV8DBEng"
    assert sql_event["sql_type"] == "SELECT"
    assert "_Reference123" in sql_event["sql_tables"]


def test_does_not_include_next_exception_in_chain():
    events = [
        make_event(
            "10:00:00.000-0,EXCP,1,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
        make_event(
            "10:00:01.000-0,SDBL,2,level=INFO," 'Usr="Иванов",process=123,OSThread=456'
        ),
        make_event(
            "10:00:02.000-0,EXCP,3,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=0)

    assert [item["index"] for item in result["events"]] == [0, 1]
    assert result["after"][0]["event_type"] == "SDBL"


def test_keeps_unknown_user_as_context():
    events = [
        make_event("10:00:00.000-0,SDBL,1,level=INFO," "process=123,OSThread=456"),
        make_event("10:00:01.000-0,EXCP,2,level=ERROR," "process=123,OSThread=456"),
        make_event(
            "10:00:02.000-0,SDBL,3,level=INFO," 'Usr="DefUser",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert len(result["before"]) == 1
    assert len(result["after"]) == 1
    assert result["before"][0]["user_relation"] == "unknown"
    assert result["after"][0]["user_relation"] == "unknown"


def test_does_not_mix_different_known_users():
    events = [
        make_event(
            "10:00:00.000-0,SDBL,1,level=INFO," 'Usr="DefUser",process=123,OSThread=456'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert result["before"] == []


def test_finds_related_events_from_another_thread():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO," 'Usr="Иванов",process=123,OSThread=789'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert len(result["related_events"]) == 1
    assert result["related_events"][0]["event_type"] == "TLOCK"
    assert result["related_events"][0]["thread"] == "789"


def test_does_not_add_different_user_to_related_events():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO," 'Usr="Петров",process=123,OSThread=789'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert result["related_events"] == []


def test_does_not_add_same_thread_to_related_events():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO," 'Usr="Иванов",process=123,OSThread=456'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert result["related_events"] == []


def test_related_events_do_not_include_exception_itself():
    events = [
        make_event(
            "10:00:00.000-0,EXCP,1,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=0)

    assert result["related_events"] == []
    assert result["related_before"] == []
    assert result["related_after"] == []


def test_related_events_include_correlation_explanation():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO," 'Usr="Иванов",process=123,OSThread=789'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    related = result["related_events"][0]

    assert related["correlation_strength"] == "weak"
    assert "Совпадают пользователь и процесс" in related["correlation_reason"]
    assert "другом потоке" in related["correlation_reason"]
    assert "Контекст выполнения отсутствует" in related["correlation_reason"]


def test_related_events_with_matching_context():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=789,'
            'Context="Документ.Заказ.Форма.Форма"'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR,"
            'Usr="Иванов",process=123,OSThread=456,'
            'Context="Документ.Заказ.Форма.Форма"'
        ),
    ]

    result = build_incident_chain(events, error_index=1)
    related = result["related_events"][0]

    assert related["correlation_strength"] == "weak"
    assert "контекст выполнения" in related["correlation_reason"]
    assert "не доказывает причинность" in related["correlation_reason"]


def test_related_events_with_different_context():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=789,'
            'Context="Документ.Заказ.Форма.Форма"'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR,"
            'Usr="Иванов",process=123,OSThread=456,'
            'Context="Справочник.Номенклатура.Форма.Форма"'
        ),
    ]

    result = build_incident_chain(events, error_index=1)
    related = result["related_events"][0]

    assert related["correlation_strength"] == "weak"
    assert "контексты выполнения различаются" in related["correlation_reason"]


def test_related_events_without_context():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO," 'Usr="Иванов",process=123,OSThread=789'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)
    related = result["related_events"][0]

    assert related["correlation_strength"] == "weak"
    assert "Контекст выполнения отсутствует" in related["correlation_reason"]


def test_related_events_with_partially_missing_context():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=789,'
            'Context="Документ.Заказ.Форма.Форма"'
        ),
        make_event(
            "10:00:00.500-0,DBV8DBEng,2,level=INFO,"
            'Usr="Иванов",process=123,OSThread=790'
        ),
        make_event(
            "10:00:01.000-0,EXCP,3,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=2)

    assert len(result["related_events"]) == 2

    reason = result["related_events"][0]["correlation_reason"]
    summary = result["related_context_summary"]

    assert "Контекст выполнения отсутствует или не определён" in reason
    assert "части связанных событий" in summary
    assert "одинаковый контекст выполнения" in summary
    assert "не доказывает причинную связь" in summary
    assert "части связанных событий" not in reason


def test_related_events_with_partially_missing_and_different_contexts():
    events = [
        make_event(
            "10:00:00.000-0,TLOCK,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=789,'
            'Context="Документ.Заказ.Форма.Форма"'
        ),
        make_event(
            "10:00:00.500-0,DBV8DBEng,2,level=INFO,"
            'Usr="Иванов",process=123,OSThread=790,'
            'Context="Справочник.Номенклатура.Форма.Форма"'
        ),
        make_event(
            "10:00:00.700-0,SDBL,3,level=INFO," 'Usr="Иванов",process=123,OSThread=791'
        ),
        make_event(
            "10:00:01.000-0,EXCP,4,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=3)

    assert len(result["related_events"]) == 3

    reason = result["related_events"][0]["correlation_reason"]
    summary = result["related_context_summary"]

    assert "Контекст выполнения отсутствует или не определён" in reason
    assert "части связанных событий" in summary
    assert "различные контексты выполнения" in summary
    assert "одинаковый контекст выполнения" not in summary
    assert "части связанных событий" not in reason


def test_extracts_exception_metadata_from_excp_event():
    description = (
        "Не удалось заблокировать запись. Действие "
        "не выполнено 'DATAZONEOBJECTLOCKS'. "
        "GUID: 12345678-1234-1234-1234-123456789abc"
    )
    event = make_event(
        "10:00:01.000-0,EXCP,2,level=ERROR,"
        'Usr="Иванов",process=123,OSThread=456,'
        f'Descr="{description}"'
    )

    result = build_incident_chain([event], error_index=0)
    target = result["events"][0]

    assert target["exception_category"] == "Не удалось заблокировать запись"
    assert target["exception_detail"] == "DATAZONEOBJECTLOCKS"
    assert target["exception_guid"] == "12345678-1234-1234-1234-123456789abc"
    assert target["exception_resource"] == "DATAZONEOBJECTLOCKS"


def test_exception_metadata_uses_none_when_guid_and_resource_are_missing():
    event = make_event('10:00:01.000-0,EXCP,2,level=ERROR,Descr="Неизвестная ошибка"')

    result = build_incident_chain([event], error_index=0)
    target = result["events"][0]

    assert target["exception_category"] == "Прочие исключения"
    assert target["exception_guid"] is None
    assert target["exception_resource"] is None


def test_correlates_exception_with_background_session():
    session_id = "9db3a907-2d96-4a79-8971-a5813cbd3309"

    events = [
        make_event(
            "10:00:00.000-0,SESN,1,level=INFO,"
            "process=123,OSThread=456,"
            f"Func=Start,Appl=BackgroundJob,Nmb=248,ID={session_id}"
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR,"
            "process=123,OSThread=456,Usr=DefUser,"
            'Descr="Ошибка базы данных"'
        ),
        make_event(
            "10:00:02.000-0,SESN,3,level=INFO,"
            "process=123,OSThread=456,"
            f"Func=Finish,Appl=BackgroundJob,Nmb=248,ID={session_id}"
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    session = result["background_session"]

    assert session["id"] == session_id
    assert session["nmb"] == "248"
    assert session["appl"] == "BackgroundJob"
    assert session["start_index"] == 0
    assert session["finish_index"] == 2


def test_does_not_correlate_exception_with_unfinished_session():
    events = [
        make_event(
            "10:00:00.000-0,SESN,1,level=INFO,"
            "process=123,OSThread=456,"
            "Func=Start,Appl=BackgroundJob,Nmb=248,ID=guid-start"
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR,"
            "process=123,OSThread=456,Usr=DefUser,"
            'Descr="Ошибка базы данных"'
        ),
        make_event(
            "10:00:02.000-0,SESN,3,level=INFO,"
            "process=123,OSThread=456,"
            "Func=Finish,Appl=BackgroundJob,Nmb=248,ID=guid-other"
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert result["background_session"] is None


def test_timestamp_to_microseconds():
    from incident_correlation import _timestamp_to_microseconds

    assert _timestamp_to_microseconds("11:11.615047-1") == (
        (11 * 3600 + 11 * 60) * 1_000_000 + 615047
    )

    assert _timestamp_to_microseconds("6254082: 08:30.471046-35") == (
        (8 * 3600 + 30 * 60) * 1_000_000 + 471046
    )


def test_timestamp_to_microseconds_rejects_invalid_value():
    from incident_correlation import _timestamp_to_microseconds

    assert _timestamp_to_microseconds("invalid") is None


def test_normalize_table_name():
    from incident_correlation import _normalize_table_name

    assert _normalize_table_name("_Const84490") == "const84490"
    assert _normalize_table_name("Const84490") == "const84490"


def test_finds_matching_dbv8dbeng_and_sdbl_events():
    events = [
        make_event(
            "11:11.615047-1,DBV8DBEng,1,"
            "level=DEBUG,process=1cv8c,OSThread=23240,"
            "Usr=Иван,Sql=SELECT * FROM _Const84490"
        ),
        make_event(
            "11:11.615048-1,SDBL,1,"
            "level=DEBUG,process=1cv8c,OSThread=23240,"
            "Usr=Иван,Sdbl=SELECT * FROM Const84490"
        ),
    ]

    pairs = find_sql_event_pairs(events)

    assert len(pairs) == 1
    assert pairs[0]["db_index"] == 0
    assert pairs[0]["sdbl_index"] == 1
    assert pairs[0]["interval_us"] == 1
    assert pairs[0]["correlation_strength"] == "weak"


def test_matches_dbv8dbeng_and_sdbl_with_different_field_names():
    events = [
        make_event(
            "11:11.615047-1,DBV8DBEng,1,"
            "level=DEBUG,process=1cv8c,OSThread=23240,"
            "Usr=Иван,Sql=SELECT T1._Fld84491 FROM _Const84490 T1"
        ),
        make_event(
            "11:11.615048-1,SDBL,1,"
            "level=DEBUG,process=1cv8c,OSThread=23240,"
            "Usr=Иван,Sdbl=SELECT Fld84491 FROM Const84490"
        ),
    ]

    pairs = find_sql_event_pairs(events)

    assert len(pairs) == 1
    assert pairs[0]["db_index"] == 0
    assert pairs[0]["sdbl_index"] == 1
    assert pairs[0]["correlation_strength"] == "weak"


def test_does_not_confirm_different_queries_as_exact_pairs():
    events = [
        make_event(
            "11:11.615047-1,DBV8DBEng,1,"
            "level=DEBUG,process=1cv8c,OSThread=23240,"
            "Usr=Иван,Sql=SELECT Name FROM _Const84490 WHERE Active = 1"
        ),
        make_event(
            "11:11.615048-1,SDBL,1,"
            "level=DEBUG,process=1cv8c,OSThread=23240,"
            "Usr=Иван,Sdbl=SELECT Code FROM Const84490 WHERE Deleted = 0"
        ),
    ]

    pairs = find_sql_event_pairs(events)

    assert all(pair["correlation_strength"] != "strong" for pair in pairs)


def test_includes_ttimeout_in_incident_chain():
    events = [
        make_event(
            "10:00:00.000-0,TTIMEOUT,1,level=WARNING,"
            'Usr="Иванов",process=123,OSThread=456'
        ),
        make_event(
            "10:00:01.000-0,EXCP,2,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=1)

    assert len(result["before"]) == 1
    assert result["before"][0]["event_type"] == "TTIMEOUT"
    assert result["events"][0]["event_type"] == "TTIMEOUT"


def test_links_xlocktables_operation_to_matching_tlock_resource():
    events = [
        make_event(
            "10:00:00.000-0,DBV8DBEng,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,'
            "Func=xlockTables(_InfoRg97191)"
        ),
        make_event(
            "10:00:00.001-0,TLOCK,2,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,'
            'Regions="InfoRg97191.DIMS",'
            'Locks="InfoRg97191.DIMS Exclusive Fld31136=0"'
        ),
        make_event(
            "10:00:01.000-0,EXCP,3,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=2)

    links = result["diagnostic_links"]

    assert len(links) == 1
    assert links[0]["from_index"] == 0
    assert links[0]["to_index"] == 1
    assert links[0]["resource"] == "inforg97191"
    assert links[0]["causal"] is False


def test_does_not_link_xlocktables_to_different_tlock_resource():
    events = [
        make_event(
            "10:00:00.000-0,DBV8DBEng,1,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,'
            "Func=xlockTables(_InfoRg97191)"
        ),
        make_event(
            "10:00:00.001-0,TLOCK,2,level=INFO,"
            'Usr="Иванов",process=123,OSThread=456,'
            'Regions="InfoRg97192.DIMS",'
            'Locks="InfoRg97192.DIMS Exclusive Fld31136=0"'
        ),
        make_event(
            "10:00:01.000-0,EXCP,3,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=2)

    assert result["diagnostic_links"] == []


def test_keeps_events_between_previous_and_current_exception():
    events = [
        make_event(
            "10:00:00.000-0,EXCP,1,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
        make_event(
            "10:00:01.000-0,SDBL,2,level=INFO," 'Usr="Иванов",process=123,OSThread=456'
        ),
        make_event(
            "10:00:02.000-0,EXCP,3,level=ERROR," 'Usr="Иванов",process=123,OSThread=456'
        ),
    ]

    result = build_incident_chain(events, error_index=2)

    assert len(result["before"]) == 1
    assert result["before"][0]["event_type"] == "SDBL"
    assert result["before"][0]["index"] == 1
