from incident_correlation import analyze_incident_evidence


def make_event(event_type, index):
    return {
        "index": index,
        "timestamp": f"10:00:0{index}.000",
        "event_type": event_type,
        "level": "INFO",
        "description": "",
        "user": "Иванов",
        "process": "123",
        "thread": "456",
        "context": "Документ.Заказ",
        "is_error": False,
    }


def make_chain(before, after):
    return {
        "before": before,
        "after": after,
    }


def test_detects_lock_events_before_exception():
    chain = make_chain(
        [make_event("TLOCK", 0)],
        [],
    )

    result = analyze_incident_evidence(chain)

    assert result["has_lock_events_before"] is True
    assert result["has_sql_events_before"] is False
    assert result["findings"][0]["code"] == "TLOCK_BEFORE_EXCP"


def test_detects_sql_events_before_exception():
    chain = make_chain(
        [make_event("SDBL", 0)],
        [],
    )

    result = analyze_incident_evidence(chain)

    assert result["has_sql_events_before"] is True
    assert result["findings"][0]["code"] == "SDBL_BEFORE_EXCP"


def test_detects_both_lock_and_sql_events():
    chain = make_chain(
        [
            make_event("TLOCK", 0),
            make_event("SDBL", 1),
        ],
        [],
    )

    result = analyze_incident_evidence(chain)

    codes = {item["code"] for item in result["findings"]}

    assert codes == {
        "TLOCK_BEFORE_EXCP",
        "SDBL_BEFORE_EXCP",
    }


def test_detects_events_after_exception():
    chain = make_chain(
        [],
        [
            make_event("SDBL", 2),
            make_event("TLOCK", 3),
        ],
    )

    result = analyze_incident_evidence(chain)

    codes = {item["code"] for item in result["findings"]}

    assert codes == {
        "TLOCK_AFTER_EXCP",
        "SDBL_AFTER_EXCP",
    }
    assert result["has_events_after"] is True


def test_reports_no_additional_evidence():
    chain = make_chain([], [])

    result = analyze_incident_evidence(chain)

    assert len(result["findings"]) == 1
    assert result["findings"][0]["code"] == "NO_ADDITIONAL_EVIDENCE"


def test_detects_dbv8dbeng_events_before_exception():
    chain = make_chain(
        [make_event("DBV8DBEng", 0)],
        [],
    )

    result = analyze_incident_evidence(chain)

    assert result["has_dbv8dbeng_events_before"] is True
    assert result["findings"][0]["code"] == "DBV8DBENG_BEFORE_EXCP"
