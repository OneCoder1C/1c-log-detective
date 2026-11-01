import pytest

from lock_analysis import analyze_lock_incident, parse_event_time
from lock_analysis import calculate_exception_intervals
from lock_analysis import find_exception_series


def test_analyze_lock_incident():
    lock_event = (
        "03:28.039032-3,TLOCK,2,"
        "level=INFO,process=1cv8c,OSThread=20716,"
        "Usr=DefUser,DBMS=DBV8DBEng,DataBase=ERP,"
        "Regions=Reference69.REFLOCK,"
        "Locks='Reference69.REFLOCK Exclusive "
        "Fld2295=0 ID=69:b0a17c10c924aec011f1d1eaa847bbb1',"
        "Context='Тестовый контекст'"
    )

    exception_event = (
        "Не удалось заблокировать запись. "
        "Действие не выполнено 'DATAZONEOBJECTLOCKS'"
    )

    result = analyze_lock_incident(
        lock_events=[lock_event],
        exception_events=[exception_event],
    )

    assert result["lock_events_count"] == 1
    assert result["lock_exceptions_count"] == 1
    assert result["locks"][0]["lock_mode"] == "EXCLUSIVE"
    assert result["exceptions"][0]["category"] == ("Не удалось заблокировать запись")


from lock_analysis import find_lock_candidates


def test_find_lock_candidates_matches_thread_and_time():
    locks = [
        {
            "timestamp": "03:28.039032-3",
            "thread": "20716",
            "lock_mode": "SHARED",
            "resource_id": "resource-1",
        },
        {
            "timestamp": "03:28.039049-3",
            "thread": "99999",
            "lock_mode": "EXCLUSIVE",
            "resource_id": "resource-2",
        },
    ]

    result = find_lock_candidates(
        lock_events=locks,
        exception_time="03:28.148031-0",
        exception_thread="20716",
        window_ms=1000,
    )

    assert len(result) == 1
    assert result[0]["thread"] == "20716"
    assert result[0]["resource_id"] == "resource-1"
    assert result[0]["time_difference_ms"] == 108.999


def test_find_lock_candidates_ignores_events_outside_window():
    locks = [
        {
            "timestamp": "03:28.039032-3",
            "thread": "20716",
            "lock_mode": "SHARED",
            "resource_id": "resource-1",
        },
    ]

    result = find_lock_candidates(
        lock_events=locks,
        exception_time="03:28.148031-0",
        exception_thread="20716",
        window_ms=50,
    )

    assert result == []


def test_find_lock_candidates_invalid_timestamp():
    result = find_lock_candidates(
        lock_events=[
            {
                "timestamp": "invalid",
                "thread": "20716",
                "lock_mode": "SHARED",
                "resource_id": "resource-1",
            }
        ],
        exception_time="invalid",
        exception_thread="20716",
    )

    assert result == []


from lock_analysis import summarize_lock_candidates


def test_summarize_lock_candidates_without_matches():
    result = summarize_lock_candidates([])

    assert result["candidate_count"] == 0
    assert result["candidates"] == []


def test_summarize_lock_candidates_with_matches():
    candidates = [
        {
            "timestamp": "03:28.039032-3",
            "thread": "20716",
            "lock_mode": "EXCLUSIVE",
            "time_difference_ms": 108.999,
        }
    ]

    result = summarize_lock_candidates(candidates)

    assert result["candidate_count"] == 1
    assert result["candidates"] == candidates
    assert "не подтверждена" in result["summary"]


def test_find_lock_candidates_ignores_lock_after_exception():
    locks = [
        {
            "timestamp": "03:28.039032-3",
            "thread": "20716",
            "lock_mode": "EXCLUSIVE",
            "resource_id": "resource-1",
        }
    ]

    result = find_lock_candidates(
        lock_events=locks,
        exception_time="03:27.758042-0",
        exception_thread="20716",
        window_ms=1000,
    )

    assert result == []


def test_find_lock_candidates_ignores_lock_after_exception():
    locks = [
        {
            "timestamp": "03:28.039032-3",
            "thread": "20716",
            "lock_mode": "EXCLUSIVE",
            "resource_id": "resource-1",
        }
    ]

    result = find_lock_candidates(
        lock_events=locks,
        exception_time="03:27.758042-0",
        exception_thread="20716",
        window_ms=1000,
    )

    assert result == []


def test_find_lock_candidates_across_minute_boundary():
    locks = [
        {
            "timestamp": "03:59.900000-3",
            "thread": "20716",
            "lock_mode": "EXCLUSIVE",
            "resource_id": "resource-1",
        }
    ]

    result = find_lock_candidates(
        lock_events=locks,
        exception_time="04:00.100000-0",
        exception_thread="20716",
        window_ms=1000,
    )

    assert len(result) == 1
    assert result[0]["time_difference_ms"] == 200.0


def test_find_lock_candidates_across_hour_boundary():
    locks = [
        {
            "timestamp": "59:59.900000-3",
            "thread": "20716",
            "lock_mode": "EXCLUSIVE",
            "resource_id": "resource-1",
        }
    ]

    result = find_lock_candidates(
        lock_events=locks,
        exception_time="00:00.100000-0",
        exception_thread="20716",
        window_ms=1000,
    )

    assert len(result) == 1
    assert result[0]["time_difference_ms"] == pytest.approx(200.0)


def test_summarize_lock_candidates_with_resource_match():
    candidates = [
        {
            "timestamp": "03:28.039032-3",
            "thread": "20716",
            "lock_mode": "EXCLUSIVE",
            "resource_id": "69:b0a17c10c924aec011f1d1eaa847bbb1",
            "resource_fields": {"Fld2295": "0"},
            "time_difference_ms": 108.999,
            "resource_match": True,
        }
    ]

    result = summarize_lock_candidates(candidates)

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["resource_match"] is True
    assert "ресурс" in result["candidates"][0]["match_reason"].lower()


def test_parse_event_time_across_hour_boundary():
    previous_time = parse_event_time("59:59.900000-3")
    current_time = parse_event_time("00:00.100000-0")

    assert previous_time is not None
    assert current_time is not None

    interval_ms = (current_time + 3600 - previous_time) * 1000

    assert interval_ms == pytest.approx(200.0)


def test_calculate_exception_intervals():
    result = calculate_exception_intervals(
        [
            "03:28.000000-0",
            "03:28.100000-0",
            "03:28.300000-0",
        ]
    )

    assert result["interval_count"] == 2
    assert result["min_ms"] == pytest.approx(100)
    assert result["max_ms"] == pytest.approx(200)
    assert result["average_ms"] == pytest.approx(150)
    assert result["up_to_100_ms"] == 1
    assert result["up_to_1000_ms"] == 2
    assert result["interval_ranges"] == {
        "up_to_10_ms": 0,
        "10_to_100_ms": 1,
        "100_to_1000_ms": 1,
        "1_to_10_seconds": 0,
        "over_10_seconds": 0,
    }


def test_calculate_exception_intervals_across_hour_boundary():
    result = calculate_exception_intervals(
        [
            "59:59.900000-0",
            "00:00.100000-0",
        ]
    )

    assert result["interval_count"] == 1
    assert result["min_ms"] == pytest.approx(200)


def test_calculate_exception_intervals_without_valid_timestamps():
    result = calculate_exception_intervals(["invalid", "incorrect"])

    assert result["interval_count"] == 0
    assert result["min_ms"] is None
    assert result["max_ms"] is None
    assert result["average_ms"] is None


def test_find_exception_series():
    result = find_exception_series(
        [
            "03:28.000000-0",
            "03:28.100000-0",
            "03:28.300000-0",
            "03:28.500000-0",
            "03:30.000000-0",
        ]
    )

    assert len(result) == 1
    assert result[0]["event_count"] == 4
    assert result[0]["duration_ms"] == pytest.approx(500)
    assert result[0]["max_gap_ms"] == pytest.approx(200)


def test_find_exception_series_across_hour_boundary():
    result = find_exception_series(
        [
            "59:59.500000-0",
            "59:59.800000-0",
            "00:00.100000-0",
        ]
    )

    assert len(result) == 1
    assert result[0]["event_count"] == 3
    assert result[0]["duration_ms"] == pytest.approx(600)


def test_find_exception_series_respects_min_events():
    result = find_exception_series(
        [
            "03:28.000000-0",
            "03:28.100000-0",
        ]
    )

    assert result == []
