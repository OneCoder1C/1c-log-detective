import json

import pytest

from html_report.data_builder import build_html_report_data


@pytest.fixture
def analysis_result():
    error_event = {
        "index": 2,
        "timestamp": "2026-10-26 09:16:04",
        "event_type": "EXCP",
        "description": "Ошибка выполнения",
        "is_error": True,
        "exception_category": "Ошибка",
    }

    before_event = {
        "index": 1,
        "timestamp": "2026-10-26 09:16:03",
        "event_type": "SDBL",
        "sql": "SELECT * FROM Документ",
        "is_error": False,
    }

    after_event = {
        "index": 3,
        "timestamp": "2026-10-26 09:16:05",
        "event_type": "TLOCK",
        "is_error": False,
    }

    related_event = {
        "index": 4,
        "timestamp": "2026-10-26 09:16:06",
        "event_type": "SDBL",
        "thread": "200",
        "correlation_reason": "Совпадают пользователь и процесс, но отличается поток.",
        "correlation_strength": "weak",
    }

    return {
        "error": None,
        "chain": {
            "user": "Иванов",
            "process": "100",
            "thread": "150",
            "context": "Документ.Реализация",
            "error_index": 2,
            "events": [before_event, error_event, after_event],
            "before": [before_event],
            "after": [after_event],
            "related_events": [related_event],
            "related_context_summary": (
                "У связанных событий обнаружены различные контексты выполнения."
            ),
        },
        "evidence": {
            "findings": [{"code": "SDBL_BEFORE_EXCP"}],
            "related_findings": [{"event_type": "SDBL", "count": 1}],
            "related_events_count": 1,
        },
    }


def test_builds_incident_timeline(analysis_result):
    result = build_html_report_data(analysis_result)

    assert result["timeline"]["before"][0]["event_type"] == "SDBL"
    assert result["timeline"]["error"]["event_type"] == "EXCP"
    assert result["timeline"]["after"][0]["event_type"] == "TLOCK"


def test_keeps_related_events_separate(analysis_result):
    result = build_html_report_data(analysis_result)

    assert len(result["related_events"]) == 1
    assert result["related_events"][0]["thread"] == "200"

    assert (
        result["related_events"][0]["correlation_reason"]
        == "Совпадают пользователь и процесс, но отличается поток."
    )
    assert result["related_events"][0]["correlation_strength"] == "weak"

    assert result["related_context_summary"] == (
        "У связанных событий обнаружены различные контексты выполнения."
    )


def test_builds_summary(analysis_result):
    result = build_html_report_data(analysis_result)

    assert result["summary"] == {
        "events_count": 3,
        "before_count": 1,
        "after_count": 1,
        "related_events_count": 1,
        "findings_count": 1,
    }


def test_preserves_specialized_event_details(analysis_result):
    result = build_html_report_data(analysis_result)

    assert result["timeline"]["before"][0]["sql"] == "SELECT * FROM Документ"
    assert result["timeline"]["error"]["exception_category"] == "Ошибка"


def test_result_can_be_serialized_to_json(analysis_result):
    result = build_html_report_data(analysis_result)

    serialized = json.dumps(result, ensure_ascii=False)

    assert "Иванов" in serialized
    assert "SELECT * FROM Документ" in serialized


def test_returns_error_payload_when_no_incident():
    result = build_html_report_data(
        {
            "error": "В журнале не найдено исключений EXCP.",
            "chain": None,
            "evidence": None,
        }
    )

    assert result["timeline"]["error"] is None
    assert result["error"] == "В журнале не найдено исключений EXCP."


def test_rejects_missing_central_exception():
    with pytest.raises(ValueError, match="центральное событие EXCP"):
        build_html_report_data(
            {
                "error": None,
                "chain": {
                    "events": [],
                    "error_index": 10,
                },
                "evidence": {},
            }
        )


def test_does_not_modify_source_data(analysis_result):
    original_sql = analysis_result["chain"]["before"][0]["sql"]

    build_html_report_data(analysis_result)

    assert analysis_result["chain"]["before"][0]["sql"] == original_sql


def test_builds_multiple_incidents_without_mixing_data(analysis_result):
    incidents = []

    for i in range(8):
        chain = {
            **analysis_result["chain"],
            "user": f"Пользователь_{i + 1}",
            "events": [
                {
                    **event,
                    "index": event["index"] + i * 10,
                }
                for event in analysis_result["chain"]["events"]
            ],
            "before": [
                {
                    **event,
                    "index": event["index"] + i * 10,
                }
                for event in analysis_result["chain"]["before"]
            ],
            "after": [
                {
                    **event,
                    "index": event["index"] + i * 10,
                }
                for event in analysis_result["chain"]["after"]
            ],
            "related_events": analysis_result["chain"]["related_events"],
        }

        incidents.append(
            {
                "chain": chain,
                "evidence": analysis_result["evidence"],
            }
        )

    source = {
        "error": None,
        "chain": incidents[-1]["chain"],
        "evidence": incidents[-1]["evidence"],
        "incidents": incidents,
    }

    result = build_html_report_data(source)

    assert result["incident_count"] == 8
    assert len(result["incidents"]) == 8

    assert result["incidents"][0]["incident"]["user"] == "Пользователь_1"
    assert result["incidents"][7]["incident"]["user"] == "Пользователь_8"

    assert result["incident"]["user"] == "Пользователь_8"


def test_builds_sql_next_checks(analysis_result):
    result = build_html_report_data(analysis_result)

    assert any("SQL-запрос" in check for check in result["next_checks"])
    assert any("параллельные операции" in check for check in result["next_checks"])


def test_builds_lock_next_checks(analysis_result):
    analysis_result["evidence"]["findings"] = [{"code": "TLOCK_BEFORE_EXCP"}]
    analysis_result["evidence"]["related_findings"] = []

    result = build_html_report_data(analysis_result)

    assert any("блокиров" in check.lower() for check in result["next_checks"])


def test_builds_datazone_next_checks(analysis_result):
    analysis_result["evidence"]["findings"] = [
        {"code": "DATAZONEOBJECTLOCKS_LOCK_FAILURE"}
    ]
    analysis_result["evidence"]["related_findings"] = []

    result = build_html_report_data(analysis_result)

    assert any("SchemaStorage" in check for check in result["next_checks"])


def test_builds_fallback_next_checks(analysis_result):
    analysis_result["evidence"]["findings"] = []
    analysis_result["evidence"]["related_findings"] = []

    result = build_html_report_data(analysis_result)

    assert result["next_checks"]
    assert any("временное окно анализа" in check for check in result["next_checks"])


def test_extracts_sql_metadata_from_sdbl_event():
    raw_text = "1:09:16:04.123000-0,SDBL," "Rows=15," "Sdbl=SELECT * FROM _Document123"

    result = build_html_report_data(
        {
            "error": None,
            "chain": {
                "events": [
                    {
                        "index": 1,
                        "event_type": "SDBL",
                        "raw_text": raw_text,
                    },
                    {
                        "index": 2,
                        "event_type": "EXCP",
                        "is_error": True,
                    },
                ],
                "before": [
                    {
                        "index": 1,
                        "event_type": "SDBL",
                        "raw_text": raw_text,
                    },
                ],
                "after": [],
                "related_events": [],
                "error_index": 2,
            },
            "evidence": {},
        }
    )

    event = result["timeline"]["before"][0]

    assert event["sql"] == "SELECT * FROM _Document123"
    assert event["sql_type"] == "SELECT"
    assert event["sql_tables"]
    assert event["rows"] == 15


def test_extracts_sql_metadata_from_dbv8dbeng_event():
    raw_text = "1:09:16:04.123000-0,DBV8DBEng," "Sql=UPDATE _Document123 SET _Fld123=1"

    result = build_html_report_data(
        {
            "error": None,
            "chain": {
                "events": [
                    {
                        "index": 1,
                        "event_type": "DBV8DBEng",
                        "raw_text": raw_text,
                    },
                    {
                        "index": 2,
                        "event_type": "EXCP",
                        "is_error": True,
                    },
                ],
                "before": [
                    {
                        "index": 1,
                        "event_type": "DBV8DBEng",
                        "raw_text": raw_text,
                    },
                ],
                "after": [],
                "related_events": [],
                "error_index": 2,
            },
            "evidence": {},
        }
    )

    event = result["timeline"]["before"][0]

    assert event["sql"] == "UPDATE _Document123 SET _Fld123=1"
    assert event["sql_type"] == "UPDATE"
    assert event["sql_tables"]
    assert "rows" not in event
    assert "rows_affected" not in event


def test_extracts_rows_from_dbv8dbeng_event():
    raw_text = (
        "14:40.597017-1,DBV8DBEng,3,level=DEBUG,"
        "Sql='SELECT * FROM Table1',NParams=0,Rows=5"
    )

    result = build_html_report_data(
        {
            "error": None,
            "chain": {
                "events": [
                    {"index": 1, "event_type": "DBV8DBEng", "raw_text": raw_text},
                    {"index": 2, "event_type": "EXCP", "is_error": True},
                ],
                "before": [
                    {"index": 1, "event_type": "DBV8DBEng", "raw_text": raw_text},
                ],
                "after": [],
                "related_events": [],
                "error_index": 2,
            },
            "evidence": {},
        }
    )

    event = result["timeline"]["before"][0]
    assert event["rows"] == 5


def test_extracts_rows_affected_from_dbv8dbeng_event():
    raw_text = (
        '14:40.597019-1,DBV8DBEng,3,level=DEBUG,'
        'Sql="UPDATE Table1 SET Value=1",NParams=0,RowsAffected=1'
    )

    result = build_html_report_data(
        {
            "error": None,
            "chain": {
                "events": [
                    {"index": 1, "event_type": "DBV8DBEng", "raw_text": raw_text},
                    {"index": 2, "event_type": "EXCP", "is_error": True},
                ],
                "before": [
                    {"index": 1, "event_type": "DBV8DBEng", "raw_text": raw_text},
                ],
                "after": [],
                "related_events": [],
                "error_index": 2,
            },
            "evidence": {},
        }
    )

    event = result["timeline"]["before"][0]
    assert event["rows_affected"] == 1
    assert "rows" not in event
