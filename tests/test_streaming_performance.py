from techlog import TechLogEvent
import pytest

from streaming_performance import StreamingPerformanceAnalyzer


@pytest.fixture
def analyzer(tmp_path):
    database_path = tmp_path / "test_streaming_performance.db"

    with StreamingPerformanceAnalyzer(str(database_path)) as instance:
        yield instance


def make_event(duration_us):
    return TechLogEvent(
        timestamp="12:00:00.000",
        event_type="DBV8DBEng",
        level="2",
        raw_text="",
        description="",
        duration_us=duration_us,
    )


def test_streaming_performance_calculates_statistics():
    with StreamingPerformanceAnalyzer() as analyzer:
        for duration in [5_000, 10_000, 15_000, 20_000, 25_000]:
            analyzer.add_event(make_event(duration))

        result = analyzer.get_performance()

    stats = result["by_event_type"]["DBV8DBEng"]

    assert result["total_events"] == 5
    assert stats["count"] == 5
    assert stats["total_duration_us"] == 75_000
    assert stats["max_duration_us"] == 25_000
    assert stats["avg_duration_us"] == 15_000
    assert stats["slow_count"] == 4
    assert stats["p95_duration_us"] == 25_000


def test_streaming_performance_ignores_events_without_duration():
    event = make_event(None)

    with StreamingPerformanceAnalyzer() as analyzer:
        analyzer.add_event(event)
        result = analyzer.get_performance()

    assert result["total_events"] == 0
    assert result["by_event_type"] == {}


def make_sql_event(duration_us, sql):
    return TechLogEvent(
        timestamp="12:00:00.000",
        event_type="SDBL",
        level="2",
        raw_text=f"Sdbl={sql},Rows=1",
        description="",
        duration_us=duration_us,
    )


def test_streaming_performance_groups_sql_queries():
    with StreamingPerformanceAnalyzer() as analyzer:
        analyzer.add_event(
            make_sql_event(
                15_000,
                "SELECT * FROM Table1 WHERE ID = 10",
            )
        )
        analyzer.add_event(
            make_sql_event(
                25_000,
                "SELECT * FROM Table1 WHERE ID = 20",
            )
        )

        result = analyzer.get_slow_sql()

    assert len(result) == 1
    assert result[0]["count"] == 2
    assert result[0]["total_duration_us"] == 40_000
    assert result[0]["slow_count"] == 2


def test_streaming_performance_groups_sql_tables():
    with StreamingPerformanceAnalyzer() as analyzer:
        analyzer.add_event(
            make_sql_event(
                15_000,
                "SELECT * FROM Table1 WHERE ID = 10",
            )
        )
        analyzer.add_event(
            make_sql_event(
                25_000,
                "SELECT * FROM Table1 WHERE ID = 20",
            )
        )

        result = analyzer.get_sql_tables()

    assert result["Table1"]["count"] == 2
    assert result["Table1"]["total_duration_us"] == 40_000
    assert result["Table1"]["max_duration_us"] == 25_000


def test_streaming_performance_calculates_sql_p95():
    with StreamingPerformanceAnalyzer() as analyzer:
        for duration in range(1_000, 101_000, 1_000):
            analyzer.add_event(
                make_sql_event(
                    duration,
                    "SELECT * FROM Table1 WHERE ID = 10",
                )
            )

        result = analyzer.get_slow_sql()

    assert result[0]["count"] == 100
    assert result[0]["p95_duration_us"] == 95_000


def test_streaming_performance_groups_sql_by_type():
    with StreamingPerformanceAnalyzer() as analyzer:
        analyzer.add_event(make_sql_event(15_000, "SELECT * FROM Table1"))
        analyzer.add_event(make_sql_event(20_000, "SELECT * FROM Table2"))
        analyzer.add_event(make_sql_event(25_000, "UPDATE Table1 SET Name = 'Test'"))

        result = analyzer.get_sql_performance()

    assert result["SELECT"]["count"] == 2
    assert result["SELECT"]["total_duration_us"] == 35_000
    assert result["UPDATE"]["count"] == 1
    assert result["UPDATE"]["total_duration_us"] == 25_000


def test_streaming_performance_calculates_p95_for_small_sample():
    with StreamingPerformanceAnalyzer() as analyzer:
        for duration in range(1, 21):
            analyzer.add_event(make_event(duration * 1000))

        result = analyzer.get_performance()

    stats = result["by_event_type"]["DBV8DBEng"]

    assert stats["count"] == 20
    assert stats["p95_duration_us"] == 19_000


def test_streaming_performance_calculates_p95_for_single_event():
    with StreamingPerformanceAnalyzer() as analyzer:
        analyzer.add_event(make_event(15_000))
        result = analyzer.get_performance()

    stats = result["by_event_type"]["DBV8DBEng"]

    assert stats["count"] == 1
    assert stats["p95_duration_us"] == 15_000


def test_streaming_performance_counts_slow_sql():
    with StreamingPerformanceAnalyzer() as analyzer:
        durations = [5_000, 9_999, 10_000, 10_001, 20_000]

        for duration in durations:
            analyzer.add_event(
                make_sql_event(
                    duration,
                    "SELECT * FROM Table1 WHERE ID = 10",
                )
            )

        result = analyzer.get_slow_sql()

    assert result[0]["count"] == 5
    assert result[0]["slow_count"] == 3


def test_sql_without_duration_is_counted():
    with StreamingPerformanceAnalyzer() as analyzer:
        analyzer.add_event(
            make_sql_event(
                None,
                "SELECT * FROM Table1 WHERE ID = 10",
            )
        )

        stats = analyzer.get_sql_performance()

    assert stats["SELECT"]["count"] == 1
    assert stats["SELECT"]["measured_count"] == 0
    assert stats["SELECT"]["missing_duration_count"] == 1
    assert stats["SELECT"]["total_duration_us"] is None
    assert stats["SELECT"]["p95_duration_us"] is None


def test_sql_without_duration_is_counted(analyzer):
    analyzer.add_event(
        make_sql_event(
            None,
            "SELECT * FROM Table1 WHERE ID = 10",
        )
    )

    stats = analyzer.get_sql_performance()

    assert stats["SELECT"]["count"] == 1
    assert stats["SELECT"]["measured_count"] == 0
    assert stats["SELECT"]["missing_duration_count"] == 1
    assert stats["SELECT"]["total_duration_us"] is None
    assert stats["SELECT"]["p95_duration_us"] is None


def test_slow_sql_and_tables_ignore_missing_durations(analyzer):
    analyzer.connection.executemany(
        "INSERT INTO sql_stats VALUES (?, ?, ?)",
        [
            ("SELECT", "SELECT * FROM Table1", None),
            ("SELECT", "SELECT * FROM Table1", 15_000),
        ],
    )

    analyzer.connection.executemany(
        "INSERT INTO table_stats VALUES (?, ?)",
        [
            ("Table1", None),
            ("Table1", 15_000),
        ],
    )

    sql_stats = analyzer.get_slow_sql()
    table_stats = analyzer.get_sql_tables()

    assert sql_stats[0]["count"] == 2
    assert sql_stats[0]["measured_count"] == 1
    assert sql_stats[0]["missing_duration_count"] == 1
    assert sql_stats[0]["total_duration_us"] == 15_000
    assert sql_stats[0]["p95_duration_us"] == 15_000

    assert table_stats["Table1"]["count"] == 2
    assert table_stats["Table1"]["measured_count"] == 1
    assert table_stats["Table1"]["missing_duration_count"] == 1
    assert table_stats["Table1"]["total_duration_us"] == 15_000
