from datetime import datetime


def group_lock_events(lock_events: list[dict]) -> dict:
    """Группирует события блокировок по процессу, потоку и базе данных."""

    groups = {}

    for event in lock_events:
        key = (
            event.get("process", ""),
            event.get("thread", ""),
            event.get("database", ""),
        )

        if key not in groups:
            groups[key] = []

        groups[key].append(event)

    for events in groups.values():
        events.sort(key=lambda item: item.get("timestamp", ""))

    return groups


def build_lock_sequence(events: list[dict]) -> list[dict]:
    """Формирует хронологическую последовательность отдельных блокировок."""

    sequence = []

    for event_index, event in enumerate(events):
        for lock in event.get("locks", []):
            sequence.append(
                {
                    "event_index": event_index,
                    "timestamp": event.get("timestamp", ""),
                    "process": event.get("process", ""),
                    "thread": event.get("thread", ""),
                    "database": event.get("database", ""),
                    "region": lock.get("region", ""),
                    "lock_mode": lock.get("lock_mode", "UNKNOWN"),
                    "resource_id": lock.get("resource_id", ""),
                    "resource_fields": lock.get("resource_fields", {}),
                    "attributes": lock.get("attributes", {}),
                }
            )

    return sequence


def analyze_resource_transitions(sequence: list[dict]) -> list[dict]:
    """Анализирует последовательные переходы между известными ресурсами."""

    transitions = {}

    for index in range(1, len(sequence)):
        previous = sequence[index - 1]
        current = sequence[index]

        previous_resource = (
            previous.get("region", ""),
            previous.get("resource_id", ""),
        )

        current_resource = (
            current.get("region", ""),
            current.get("resource_id", ""),
        )

        if not all(previous_resource) or not all(current_resource):
            continue

        if previous_resource == current_resource:
            continue

        transition_type = (
            "within_event"
            if previous.get("event_index") == current.get("event_index")
            else "between_events"
        )

        key = (previous_resource, current_resource, transition_type)

        if key not in transitions:
            transitions[key] = {
                "from_region": previous_resource[0],
                "from_resource_id": previous_resource[1],
                "to_region": current_resource[0],
                "to_resource_id": current_resource[1],
                "transition_type": transition_type,
                "count": 0,
            }

        transitions[key]["count"] += 1

    return list(transitions.values())


def find_repeated_resources(sequence: list[dict]) -> list[dict]:
    """Находит повторные обращения к одним и тем же ресурсам."""

    resource_groups = {}

    for item in sequence:
        resource_id = item.get("resource_id", "")
        region = item.get("region", "")

        if not resource_id:
            continue

        resource_key = (region, resource_id)

        if resource_key not in resource_groups:
            resource_groups[resource_key] = []

        resource_groups[resource_key].append(item)

    repeated = []

    for (region, resource_id), events in resource_groups.items():
        if len(events) < 2:
            continue

        elapsed_times = []
        hour_offset = 0
        previous_seconds = None

        for event in events:
            timestamp = event["timestamp"]
            time_part = timestamp.split("-", 1)[0]

            parsed = datetime.strptime(time_part, "%M:%S.%f")

            current_seconds = (
                parsed.minute * 60 + parsed.second + parsed.microsecond / 1_000_000
            )

            if (
                previous_seconds is not None
                and previous_seconds - current_seconds > 1800
            ):
                hour_offset += 3600

            elapsed_times.append(current_seconds + hour_offset)
            previous_seconds = current_seconds

        duration_ms = (elapsed_times[-1] - elapsed_times[0]) * 1000

        repeated.append(
            {
                "region": region,
                "resource_id": resource_id,
                "count": len(events),
                "first_timestamp": events[0]["timestamp"],
                "last_timestamp": events[-1]["timestamp"],
                "duration_ms": round(duration_ms, 3),
                "lock_modes": sorted({event["lock_mode"] for event in events}),
            }
        )

    return repeated
