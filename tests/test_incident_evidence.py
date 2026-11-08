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


def make_chain(before, after, events=None):
    return {
        "before": before,
        "after": after,
        "events": events or [],
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


def test_detects_datazoneobjectlocks_lock_failure():
    before = [
        {**make_event("DBV8DBEng", 1), "sql": "SELECT * FROM _ExtensionsInfoNGS"},
        {
            **make_event("DBV8DBEng", 2),
            "sql": "SELECT Status FROM SchemaStorage WHERE SchemaID = 1",
        },
        {**make_event("SDBL", 3), "sql": "GET NGENERATIONS"},
        {**make_event("SDBL", 4), "sql": "schema get local"},
    ]

    error = {
        **make_event("EXCP", 5),
        "is_error": True,
        "exception_resource": "DATAZONEOBJECTLOCKS",
    }

    result = analyze_incident_evidence(make_chain(before, [], events=[error]))

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "DATAZONEOBJECTLOCKS_LOCK_FAILURE"
    )

    assert finding["confidence"] == "Наблюдаемая закономерность"
    assert finding["count"] == 5

    assert "локальной схемы" in result["probable_cause"]
    assert result["confidence"] == "Низкая"


def test_does_not_detect_datazoneobjectlocks_without_full_sequence():
    before = [
        {**make_event("DBV8DBEng", 1), "sql": "SELECT * FROM _ExtensionsInfo"},
        {**make_event("SDBL", 2), "sql": "GET NGENERATIONS"},
    ]

    error = {
        **make_event("EXCP", 3),
        "is_error": True,
        "exception_resource": "DATAZONEOBJECTLOCKS",
    }

    result = analyze_incident_evidence(make_chain(before, [], events=[error]))

    codes = {item["code"] for item in result["findings"]}

    assert "DATAZONEOBJECTLOCKS_LOCK_FAILURE" not in codes

    assert result["probable_cause"] == ("Причина не установлена по имеющимся событиям.")
    assert result["confidence"] == "Недостаточно данных"


def test_does_not_detect_datazoneobjectlocks_for_other_exception():
    before = [
        {**make_event("DBV8DBEng", 1), "sql": "SELECT * FROM _ExtensionsInfo"},
        {**make_event("DBV8DBEng", 2), "sql": "SELECT Status FROM SchemaStorage"},
        {**make_event("SDBL", 3), "sql": "GET NGENERATIONS"},
        {**make_event("SDBL", 4), "sql": "schema get local"},
    ]

    error = {
        **make_event("EXCP", 5),
        "is_error": True,
        "exception_resource": "OTHER_RESOURCE",
    }

    result = analyze_incident_evidence(make_chain(before, [], events=[error]))

    codes = {item["code"] for item in result["findings"]}

    assert "DATAZONEOBJECTLOCKS_LOCK_FAILURE" not in codes
