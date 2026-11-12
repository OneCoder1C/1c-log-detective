"""Подготовка данных для автономного HTML-отчёта."""

import re

from sql_analysis import (
    extract_sql,
    extract_sql_tables,
    extract_rows,
    extract_rows_affected,
    get_sql_type,
)


def _json_safe(value):
    """Преобразует значения в типы, поддерживаемые JSON."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    return str(value)


def _as_list(value):
    """Возвращает список или пустой список."""
    return value if isinstance(value, list) else []


def _unique_events(events):
    """Удаляет дубли событий по индексу или набору основных полей."""
    result = []
    seen = set()

    for event in events:
        if not isinstance(event, dict):
            continue

        key = event.get("index")

        if key is None:
            key = (
                event.get("event_type"),
                event.get("timestamp"),
                event.get("user"),
                event.get("thread"),
                event.get("description"),
            )

        if key in seen:
            continue

        seen.add(key)
        result.append(event)

    return result


def _prepare_timeline_event(event):
    """Добавляет SQL-метаданные события для отображения в HTML-отчёте."""
    if not isinstance(event, dict):
        return event

    prepared = dict(event)

    if prepared.get("event_type") not in {"SDBL", "DBV8DBEng"}:
        return prepared

    raw_text = prepared.get("raw_text") or ""
    sql = extract_sql(raw_text)

    if not sql:
        return prepared

    prepared["sql"] = sql
    prepared["sql_type"] = get_sql_type(sql)
    prepared["sql_tables"] = extract_sql_tables(sql)

    rows = extract_rows(raw_text)
    if rows is not None:
        prepared["rows"] = rows

    rows_affected = extract_rows_affected(raw_text)
    if rows_affected is not None:
        prepared["rows_affected"] = rows_affected

    return prepared


def _format_timestamp(value):
    """Преобразует время технологического журнала в формат ММ:СС.доли."""
    if not value:
        return ""

    value = str(value)

    try:
        # Формат: ММ:СС.доли секунды-номер
        time_part = value.split("-", 1)[0]
        minutes, seconds = time_part.split(":", 1)

        return f"{int(minutes):02d}:{seconds}"

    except (ValueError, TypeError):
        return value


def _extract_context_objects(events):
    """Извлекает типизированные имена объектов метаданных из контекста."""
    pattern = re.compile(
        r"\b(?:Документ|Документы|Справочник|Справочники|"
        r"Константа|Константы|РегистрСведений|РегистрНакопления|"
        r"ПланСчетов|ПланВидовХарактеристик|Перечисление|"
        r"Обработка|Отчет|БизнесПроцесс|Задача)\."
        r"[А-Яа-яЁёA-Za-z0-9_]+"
    )

    objects = []

    for event in events:
        for field in ("object", "object_name", "object_presentation"):
            value = event.get(field)
            if value and value not in objects:
                objects.append(value)

        context = event.get("context") or ""

        for match in pattern.finditer(context):
            name = match.group(0)

            if name.startswith("Справочники."):
                name = "Справочник." + name.split(".", 1)[1]

            if name not in objects:
                objects.append(name)

    return objects


def _build_overview(
    analysis_result,
    incident,
    events,
    findings,
):
    """Формирует краткую сводку инцидента."""

    # Период определяем по порядку событий в цепочке.
    ordered_events = sorted(
        events,
        key=lambda event: (
            event.get("index") is None,
            event.get("index", 0),
        ),
    )

    timestamps = [
        event.get("timestamp") for event in ordered_events if event.get("timestamp")
    ]

    period = {
        "start": _format_timestamp(timestamps[0]) if timestamps else "",
        "end": _format_timestamp(timestamps[-1]) if timestamps else "",
    }

    # Пользователи.
    users = []
    for event in events:
        user = event.get("user")
        if user and user not in users:
            users.append(user)

    if not users and incident.get("user"):
        users.append(incident["user"])

    # Объекты из структурированных полей и контекста событий.
    objects = _extract_context_objects(events)

    # Количество событий каждого типа.
    event_counts = {}
    for event in events:
        event_type = event.get("event_type") or "OTHER"
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    # Число уникальных событий, приведённых в диагностических признаках.
    evidence_events = []
    for finding in findings:
        evidence_events.extend(_as_list(finding.get("events")))

    evidence_count = len(_unique_events(evidence_events))

    # Диагноз может передаваться анализатором.
    # Если его нет, не пытаемся самостоятельно придумывать причину.
    evidence = analysis_result.get("evidence") or {}

    probable_cause = (
        analysis_result.get("probable_cause")
        or evidence.get("probable_cause")
        or "Причина не установлена."
    )

    confidence = (
        analysis_result.get("confidence")
        or evidence.get("confidence")
        or "Недостаточно данных"
    )

    return {
        "period": period,
        "users": users,
        "objects": objects,
        "event_counts": event_counts,
        "probable_cause": probable_cause,
        "detected_symptom": incident.get("exception_category") or "",
        "lock_resource": incident.get("exception_resource") or "",
        "confidence": confidence,
        "evidence_count": evidence_count,
    }


def _build_next_checks(incident, findings, related_findings):
    """Формирует рекомендации по дальнейшей диагностике инцидента."""

    checks = []

    finding_codes = {
        finding.get("code") for finding in findings if isinstance(finding, dict)
    }

    if "TLOCK_BEFORE_EXCP" in finding_codes:
        checks.append(
            "Определить соединение и сеанс, удерживавшие блокировку. "
            "Проверить длительность ожидания и цепочку блокировок."
        )

    if "SDBL_BEFORE_EXCP" in finding_codes or "DBV8DBENG_BEFORE_EXCP" in finding_codes:
        checks.append(
            "Проверить текст SQL-запросов, длительность выполнения "
            "и план запроса. Особое внимание уделить операциям "
            "с длительностью более 1 секунды."
        )

    if "DATAZONEOBJECTLOCKS_LOCK_FAILURE" in finding_codes:
        checks.append(
            "Проверить получение локальной схемы: "
            "_ExtensionsInfo, SchemaStorage, GET NGENERATIONS "
            "и schema get local. Изучить соответствующий контекст 1С."
        )

    if related_findings:
        checks.append(
            "Проверить параллельные операции других потоков "
            "и фоновые задания, работающие с теми же ресурсами."
        )

    if not checks:
        checks.append(
            "Расширить временное окно анализа и проверить события "
            "перед исключением, чтобы собрать дополнительный контекст."
        )

    return checks


def build_html_report_data(analysis_result: dict) -> dict:
    """
    Подготавливает результат анализа инцидента для HTML-отчёта.

    Принимает результат analyze_incident_file_correlated().
    Не выполняет повторный анализ технологического журнала.
    """
    if not isinstance(analysis_result, dict):
        raise TypeError("Результат анализа должен быть словарём.")

    incidents = analysis_result.get("incidents")

    if isinstance(incidents, list) and incidents:
        prepared_incidents = []

        for item in incidents:
            if not isinstance(item, dict):
                continue

            prepared = build_html_report_data(
                {
                    "error": None,
                    "chain": item.get("chain"),
                    "evidence": item.get("evidence"),
                }
            )

            prepared_incidents.append(prepared)

        if prepared_incidents:
            data = dict(prepared_incidents[-1])
            data["incidents"] = prepared_incidents
            data["incident_count"] = len(prepared_incidents)

            return _json_safe(data)

    error = analysis_result.get("error")
    chain = analysis_result.get("chain")

    if error or not isinstance(chain, dict):
        return {
            "schema_version": 1,
            "error": str(error or "Данные инцидента отсутствуют."),
            "incident": None,
            "overview": None,
            "summary": {
                "events_count": 0,
                "before_count": 0,
                "after_count": 0,
                "related_events_count": 0,
                "findings_count": 0,
            },
            "timeline": {
                "before": [],
                "error": None,
                "after": [],
            },
            "related_events": [],
            "related_context_summary": None,
            "findings": [],
            "related_findings": [],
            "incidents": [],
            "incident_count": 0,
        }

    events = _as_list(chain.get("events"))
    before = [_prepare_timeline_event(event) for event in _as_list(chain.get("before"))]
    after = [_prepare_timeline_event(event) for event in _as_list(chain.get("after"))]
    related_events = [
        _prepare_timeline_event(event)
        for event in _as_list(chain.get("related_events"))
    ]

    error_event = next(
        (
            event
            for event in events
            if isinstance(event, dict) and event.get("is_error")
        ),
        None,
    )

    if error_event is None:
        error_index = chain.get("error_index")
        error_event = next(
            (
                event
                for event in events
                if isinstance(event, dict)
                and event.get("index") == error_index
                and event.get("event_type") == "EXCP"
            ),
            None,
        )

    if error_event is None:
        raise ValueError("В цепочке не найдено центральное событие EXCP.")

    error_event = _prepare_timeline_event(error_event)

    evidence = analysis_result.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}

    findings = _as_list(evidence.get("findings"))
    related_findings = _as_list(evidence.get("related_findings"))

    next_checks = _build_next_checks(
        {},
        findings,
        related_findings,
    )

    incident = {
        "user": chain.get("user", ""),
        "process": chain.get("process", ""),
        "thread": chain.get("thread", ""),
        "context": chain.get("context", ""),
        "error_index": chain.get("error_index"),
        "timestamp": error_event.get("timestamp", ""),
        "event_type": error_event.get("event_type", "EXCP"),
        "description": error_event.get("description", ""),
        "exception_category": error_event.get("exception_category", ""),
        "exception_detail": error_event.get("exception_detail", ""),
        "exception_resource": error_event.get("exception_resource", ""),
        "exception_guid": error_event.get("exception_guid", ""),
        "background_session": chain.get("background_session"),
    }

    all_events = _unique_events(before + [error_event] + after + related_events)

    overview = _build_overview(
        analysis_result,
        incident,
        all_events,
        findings,
    )

    data = {
        "schema_version": 1,
        "error": None,
        "incident": incident,
        "overview": overview,
        "next_checks": next_checks,
        "summary": {
            "events_count": len(events),
            "before_count": len(before),
            "after_count": len(after),
            "related_events_count": evidence.get(
                "related_events_count",
                len(related_events),
            ),
            "findings_count": len(findings),
        },
        "timeline": {
            "before": before,
            "error": error_event,
            "after": after,
        },
        "related_events": related_events,
        "related_context_summary": chain.get("related_context_summary"),
        "findings": findings,
        "related_findings": related_findings,
    }

    return _json_safe(data)
