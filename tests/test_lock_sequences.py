from lock_sequences import (
    build_lock_sequence,
    find_repeated_resources,
)

from lock_sequences import analyze_resource_transitions


def test_build_lock_sequence_extracts_lock_data():
    events = [
        {
            "timestamp": "03:28.039032-3",
            "process": "1cv8c",
            "thread": "20716",
            "database": "ERP",
            "locks": [
                {
                    "region": "Reference69.REFLOCK",
                    "lock_mode": "SHARED",
                    "resource_id": "69:abc123",
                    "resource_fields": {"Fld2295": "0"},
                    "attributes": {"ID": "69:abc123"},
                }
            ],
        }
    ]

    result = build_lock_sequence(events)

    assert len(result) == 1
    assert result[0]["region"] == "Reference69.REFLOCK"
    assert result[0]["lock_mode"] == "SHARED"
    assert result[0]["resource_id"] == "69:abc123"
    assert result[0]["thread"] == "20716"


def test_build_lock_sequence_handles_multiple_locks_in_event():
    events = [
        {
            "timestamp": "03:28.039032-3",
            "process": "1cv8c",
            "thread": "20716",
            "database": "ERP",
            "locks": [
                {
                    "region": "Reference221.REFLOCK",
                    "lock_mode": "EXCLUSIVE",
                    "resource_id": "",
                    "resource_fields": {},
                    "attributes": {},
                },
                {
                    "region": "InfoRg35800.DIMS",
                    "lock_mode": "EXCLUSIVE",
                    "resource_id": "",
                    "resource_fields": {"Fld35801": "69:abc123"},
                    "attributes": {},
                },
            ],
        }
    ]

    result = build_lock_sequence(events)

    assert len(result) == 2
    assert result[0]["region"] == "Reference221.REFLOCK"
    assert result[1]["region"] == "InfoRg35800.DIMS"


def test_build_lock_sequence_handles_empty_locks():
    events = [
        {
            "timestamp": "03:28.039032-3",
            "process": "1cv8c",
            "thread": "20716",
            "database": "ERP",
            "locks": [],
        }
    ]

    assert build_lock_sequence(events) == []


def test_find_repeated_resources_across_hour_boundary():
    sequence = [
        {
            "timestamp": "59:59.000000-3",
            "region": "Reference69.REFLOCK",
            "resource_id": "69:abc123",
            "lock_mode": "SHARED",
        },
        {
            "timestamp": "00:01.000000-3",
            "region": "Reference69.REFLOCK",
            "resource_id": "69:abc123",
            "lock_mode": "EXCLUSIVE",
        },
    ]

    result = find_repeated_resources(sequence)

    assert len(result) == 1
    assert result[0]["duration_ms"] == 2000.0


from lock_sequences import analyze_resource_transitions


def test_analyze_resource_transitions_distinguishes_transition_types():
    sequence = [
        {
            "event_index": 0,
            "region": "Reference69.REFLOCK",
            "resource_id": "A",
        },
        {
            "event_index": 0,
            "region": "InfoRg35800.DIMS",
            "resource_id": "B",
        },
        {
            "event_index": 1,
            "region": "Reference69.REFLOCK",
            "resource_id": "C",
        },
    ]

    result = analyze_resource_transitions(sequence)

    assert len(result) == 2

    transitions = {item["transition_type"]: item for item in result}

    assert transitions["within_event"]["from_resource_id"] == "A"
    assert transitions["within_event"]["to_resource_id"] == "B"

    assert transitions["between_events"]["from_resource_id"] == "B"
    assert transitions["between_events"]["to_resource_id"] == "C"


def test_analyze_resource_transitions_ignores_same_resource():
    sequence = [
        {
            "event_index": 0,
            "region": "Reference69.REFLOCK",
            "resource_id": "A",
        },
        {
            "event_index": 1,
            "region": "Reference69.REFLOCK",
            "resource_id": "A",
        },
    ]

    assert analyze_resource_transitions(sequence) == []


def test_analyze_resource_transitions_ignores_empty_resource_id():
    sequence = [
        {
            "event_index": 0,
            "region": "Reference69.REFLOCK",
            "resource_id": "A",
        },
        {
            "event_index": 1,
            "region": "InfoRg40263.DIMS",
            "resource_id": "",
        },
        {
            "event_index": 2,
            "region": "Reference70.REFLOCK",
            "resource_id": "B",
        },
    ]

    assert analyze_resource_transitions(sequence) == []
