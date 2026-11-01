from techlog import TechLogEvent
from performance_analysis import (
    analyze_performance,
    analyze_sql_tables,
)


def make_event(event_type, duration_us):
    return TechLogEvent(
        timestamp="12:00:00.000",
        event_type=event_type,
        level="2",
        raw_text="",
        description="",
        duration_us=duration_us,
    )


def test_analyze_performance_counts_events():
    events = [
        make_event("DBV8DBEng", 5_000),
        make_event("DBV8DBEng", 15_000),
        make_event("SDBL", 20_000),
    ]

    result = analyze_performance(events)

    assert result["total_events"] == 3
    assert result["by_event_type"]["DBV8DBEng"]["count"] == 2
    assert result["by_event_type"]["SDBL"]["count"] == 1


def test_analyze_performance_calculates_durations():
    events = [
        make_event("DBV8DBEng", 5_000),
        make_event("DBV8DBEng", 15_000),
        make_event("DBV8DBEng", 25_000),
    ]

    result = analyze_performance(events)
    stats = result["by_event_type"]["DBV8DBEng"]

    assert stats["total_duration_us"] == 45_000
    assert stats["max_duration_us"] == 25_000
    assert stats["slow_count"] == 2
    assert stats["avg_duration_us"] == 15_000


def test_analyze_performance_ignores_missing_duration():
    events = [
        make_event("DBV8DBEng", 15_000),
        make_event("DBV8DBEng", None),
    ]

    result = analyze_performance(events)

    assert result["total_events"] == 1
    assert result["by_event_type"]["DBV8DBEng"]["count"] == 1


def test_analyze_sql_performance_groups_by_type():
    from performance_analysis import analyze_sql_performance

    events = [
        make_event("DBV8DBEng", 5_000),
        make_event("DBV8DBEng", 15_000),
        make_event("DBV8DBEng", 25_000),
    ]

    events[0].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'
    events[1].raw_text = '12:00:00.000,DBV8DBEng,2,Sql="SELECT * FROM TableB"'
    events[2].raw_text = (
        "12:00:00.000,DBV8DBEng,3,Sql=\"UPDATE TableA SET Name = 'Test'\""
    )

    result = analyze_sql_performance(events)

    assert result["SELECT"]["count"] == 2
    assert result["SELECT"]["total_duration_us"] == 20_000
    assert result["SELECT"]["max_duration_us"] == 15_000
    assert result["SELECT"]["slow_count"] == 1

    assert result["UPDATE"]["count"] == 1
    assert result["UPDATE"]["max_duration_us"] == 25_000
    assert result["SELECT"]["avg_duration_us"] == 10_000
    assert result["UPDATE"]["avg_duration_us"] == 25_000


def test_analyze_sql_performance_ignores_unknown_sql():
    from performance_analysis import analyze_sql_performance

    events = [
        make_event("DBV8DBEng", 15_000),
    ]

    events[0].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SOME UNKNOWN COMMAND"'

    result = analyze_sql_performance(events)

    assert result == {}


def test_analyze_performance_calculates_p95():
    from performance_analysis import analyze_performance

    events = [
        make_event("DBV8DBEng", duration) for duration in range(1_000, 101_000, 1_000)
    ]

    result = analyze_performance(events)
    stats = result["by_event_type"]["DBV8DBEng"]

    assert stats["count"] == 100
    assert stats["p95_duration_us"] == 95_000


def test_analyze_sql_performance_calculates_p95():
    from performance_analysis import analyze_sql_performance

    events = [
        make_event("DBV8DBEng", duration) for duration in range(1_000, 101_000, 1_000)
    ]

    for index, event in enumerate(events, start=1):
        event.raw_text = f"12:00:00.000,DBV8DBEng,{index}," 'Sql="SELECT * FROM TableA"'

    result = analyze_sql_performance(events)

    assert result["SELECT"]["count"] == 100
    assert result["SELECT"]["p95_duration_us"] == 95_000


def test_analyze_slow_sql_groups_normalized_queries():
    from performance_analysis import analyze_slow_sql

    events = [
        make_event("DBV8DBEng", 10_000),
        make_event("DBV8DBEng", 20_000),
        make_event("DBV8DBEng", 30_000),
    ]

    events[0].raw_text = (
        '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA WHERE ID = 100"'
    )
    events[1].raw_text = (
        '12:00:00.000,DBV8DBEng,2,Sql="SELECT * FROM TableA WHERE ID = 200"'
    )
    events[2].raw_text = (
        '12:00:00.000,DBV8DBEng,3,Sql="SELECT * FROM TableB WHERE ID = 300"'
    )

    result = analyze_slow_sql(events)

    assert len(result) == 2
    assert result[0]["count"] == 2
    assert result[0]["total_duration_us"] == 30_000
    assert result[0]["max_duration_us"] == 20_000
    assert result[0]["normalized_sql"] == ("SELECT * FROM TableA WHERE ID = ?")


def test_analyze_slow_sql_sorts_by_total_duration_and_respects_limit():
    from performance_analysis import analyze_slow_sql

    events = [
        make_event("DBV8DBEng", 50_000),
        make_event("DBV8DBEng", 10_000),
        make_event("DBV8DBEng", 20_000),
    ]

    events[0].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'
    events[1].raw_text = '12:00:00.000,DBV8DBEng,2,Sql="SELECT * FROM TableB"'
    events[2].raw_text = '12:00:00.000,DBV8DBEng,3,Sql="SELECT * FROM TableC"'

    result = analyze_slow_sql(events, limit=2)

    assert len(result) == 2
    assert result[0]["total_duration_us"] == 50_000
    assert result[1]["total_duration_us"] == 20_000


def test_analyze_slow_sql_returns_empty_for_no_sql_events():
    from performance_analysis import analyze_slow_sql

    events = [
        make_event("EXCP", 15_000),
        make_event("SDBL", None),
    ]

    assert analyze_slow_sql(events) == []


def test_analyze_slow_sql_returns_empty_when_limit_is_zero():
    from performance_analysis import analyze_slow_sql

    events = [
        make_event("DBV8DBEng", 15_000),
    ]

    events[0].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'

    assert analyze_slow_sql(events, limit=0) == []


def test_analyze_slow_sql_rejects_negative_limit():
    import pytest
    from performance_analysis import analyze_slow_sql

    with pytest.raises(ValueError, match="limit"):
        analyze_slow_sql([], limit=-1)


def test_analyze_sql_tables_counts_table_accesses():
    events = [
        make_event("DBV8DBEng", 5_000),
        make_event("DBV8DBEng", 15_000),
        make_event("DBV8DBEng", 25_000),
    ]

    events[0].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'
    events[1].raw_text = '12:00:00.000,DBV8DBEng,2,Sql="SELECT * FROM TableA"'
    events[2].raw_text = '12:00:00.000,DBV8DBEng,3,Sql="SELECT * FROM TableB"'

    result = analyze_sql_tables(events)

    table_a = next(item for item in result if item["table"] == "TableA")
    table_b = next(item for item in result if item["table"] == "TableB")

    assert table_a["count"] == 2
    assert table_a["total_duration_us"] == 20_000
    assert table_a["max_duration_us"] == 15_000
    assert table_a["slow_count"] == 1

    assert table_b["count"] == 1
    assert table_b["total_duration_us"] == 25_000
    assert table_b["max_duration_us"] == 25_000
    assert table_b["slow_count"] == 1


def test_analyze_sql_tables_counts_join_for_each_table():
    events = [
        make_event("DBV8DBEng", 20_000),
    ]

    events[0].raw_text = (
        "12:00:00.000,DBV8DBEng,1,"
        'Sql="SELECT * FROM TableA JOIN TableB ON TableA.ID = TableB.ID"'
    )

    result = analyze_sql_tables(events)

    assert len(result) == 2
    assert result[0]["count"] == 1
    assert result[1]["count"] == 1
    assert result[0]["total_duration_us"] == 20_000
    assert result[1]["total_duration_us"] == 20_000


def test_analyze_sql_tables_ignores_missing_sql_and_duration():
    events = [
        make_event("DBV8DBEng", 15_000),
        make_event("DBV8DBEng", None),
        make_event("EXCP", 20_000),
    ]

    events[0].raw_text = "DBV8DBEng,Func=BeginTransaction"
    events[1].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'
    events[2].raw_text = '12:00:00.000,EXCP,1,Sql="SELECT * FROM TableB"'

    assert analyze_sql_tables(events) == []


def test_analyze_sql_tables_sorts_by_total_duration():
    events = [
        make_event("DBV8DBEng", 10_000),
        make_event("DBV8DBEng", 30_000),
        make_event("DBV8DBEng", 20_000),
    ]

    events[0].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'
    events[1].raw_text = '12:00:00.000,DBV8DBEng,2,Sql="SELECT * FROM TableB"'
    events[2].raw_text = '12:00:00.000,DBV8DBEng,3,Sql="SELECT * FROM TableB"'

    result = analyze_sql_tables(events)

    assert result[0]["table"] == "TableB"
    assert result[0]["total_duration_us"] == 50_000
    assert result[1]["table"] == "TableA"


def test_analyze_sql_performance_ignores_non_sql_event_types():
    from performance_analysis import analyze_sql_performance

    events = [
        make_event("EXCP", 20_000),
        make_event("DBV8DBEng", 15_000),
    ]

    events[0].raw_text = '12:00:00.000,EXCP,1,Sql="SELECT * FROM TableB"'
    events[1].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'

    result = analyze_sql_performance(events)

    assert result["SELECT"]["count"] == 1
    assert result["SELECT"]["total_duration_us"] == 15_000


def test_analyze_slow_sql_ignores_non_sql_event_types():
    from performance_analysis import analyze_slow_sql

    events = [
        make_event("EXCP", 30_000),
        make_event("DBV8DBEng", 15_000),
    ]

    events[0].raw_text = '12:00:00.000,EXCP,1,Sql="SELECT * FROM TableB"'
    events[1].raw_text = '12:00:00.000,DBV8DBEng,1,Sql="SELECT * FROM TableA"'

    result = analyze_slow_sql(events)

    assert len(result) == 1
    assert result[0]["count"] == 1
    assert result[0]["total_duration_us"] == 15_000
    assert "TableA" in result[0]["normalized_sql"]


def test_analyze_sql_tables_calculates_p95():
    from performance_analysis import analyze_sql_tables

    events = [
        TechLogEvent(
            timestamp="12:00:00",
            event_type="DBV8DBEng",
            level="1",
            raw_text=("12:00:00.000,DBV8DBEng,1," 'Sql="SELECT * FROM TableA"'),
            description="",
            duration_us=duration,
        )
        for duration in [1_000, 2_000, 3_000, 4_000, 5_000]
    ]

    result = analyze_sql_tables(events)

    assert len(result) == 1
    assert result[0]["table"] == "TableA"
    assert result[0]["p95_duration_us"] == 5_000


def test_analyze_slow_events_groups_by_event_type():
    from performance_analysis import analyze_slow_events

    events = [
        make_event("EXCP", 20_000),
        make_event("EXCP", 30_000),
        make_event("CALL", 15_000),
        make_event("SDBL", 50_000),
        make_event("DBV8DBEng", 60_000),
        make_event("EXCP", 5_000),
    ]

    result = analyze_slow_events(events)

    assert len(result) == 2
    assert result[0]["event_type"] == "EXCP"
    assert result[0]["count"] == 2
    assert result[0]["total_duration_us"] == 50_000
    assert result[0]["p95_duration_us"] == 30_000
    assert result[1]["event_type"] == "CALL"


def test_analyze_slow_events_respects_limit():
    from performance_analysis import analyze_slow_events

    events = [
        make_event("EXCP", 20_000),
        make_event("CALL", 30_000),
        make_event("SDBL", 50_000),
    ]

    result = analyze_slow_events(events, limit=1)

    assert len(result) == 1
    assert result[0]["event_type"] == "CALL"


def test_analyze_slow_events_rejects_negative_limit():
    import pytest
    from performance_analysis import analyze_slow_events

    with pytest.raises(ValueError):
        analyze_slow_events([], limit=-1)


def test_analyze_slow_events_returns_empty_when_no_slow_events():
    from performance_analysis import analyze_slow_events

    events = [
        make_event("EXCP", 5_000),
        make_event("CALL", 9_999),
        make_event("SDBL", 50_000),
        make_event("DBV8DBEng", 60_000),
    ]

    result = analyze_slow_events(events)

    assert result == []
