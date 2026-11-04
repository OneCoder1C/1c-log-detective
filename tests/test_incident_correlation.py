from techlog import parse_event
from incident_correlation import (
    build_incident_chain,
    is_same_execution,
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
