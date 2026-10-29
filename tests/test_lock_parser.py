from techlog import parse_lock_event


def make_tlock(locks: str) -> str:
    """Создаёт тестовое событие блокировки 1С."""
    return (
        "03:28.039032-3,TLOCK,2,"
        "level=INFO,process=1cv8c,OSThread=20716,"
        "Usr=DefUser,DBMS=DBV8DBEng,DataBase=ERP,"
        f"Regions=Reference69.REFLOCK,Locks='{locks}',"
        "Context='Тестовый контекст'"
    )


def test_parse_shared_lock():
    raw_event = make_tlock(
        "Reference69.REFLOCK Shared " "Fld2295=0 ID=69:b0a17c10c924aec011f1d1eaa847bbb1"
    )

    result = parse_lock_event(raw_event)

    assert result is not None
    assert result["lock_mode"] == "SHARED"
    assert result["resource_id"] == ("69:b0a17c10c924aec011f1d1eaa847bbb1")
    assert result["thread"] == "20716"
    assert result["user"] == "DefUser"
    assert result["database"] == "ERP"
    assert result["resource_fields"] == {"Fld2295": "0"}


def test_parse_exclusive_lock():
    raw_event = make_tlock(
        "Reference69.REFLOCK Exclusive "
        "Fld2295=0 ID=69:b0a17c10c924aec011f1d1eaa847bbb1"
    )

    result = parse_lock_event(raw_event)

    assert result is not None
    assert result["lock_mode"] == "EXCLUSIVE"


def test_parse_lock_without_resource_id():
    raw_event = make_tlock("Reference69.REFLOCK Exclusive Fld2295=0")

    result = parse_lock_event(raw_event)

    assert result is not None
    assert result["lock_mode"] == "EXCLUSIVE"
    assert result["resource_id"] == ""


def test_non_tlock_event_returns_none():
    raw_event = "03:28.039032-3,EXCP,2," "level=INFO,process=1cv8c,OSThread=20716"

    assert parse_lock_event(raw_event) is None
