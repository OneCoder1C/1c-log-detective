import pytest

from techlog import parse_event
from incident_correlation import (
    build_incident_chain,
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
