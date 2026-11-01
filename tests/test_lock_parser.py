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


def test_parse_multiple_locks():
    raw_event = make_tlock(
        "Reference221.REFLOCK Exclusive Fld2295=0,"
        "InfoRg35800.DIMS Exclusive "
        "Fld2295=0 Fld35801=69:b0a17c10c924aec011f1d2148cd87c97"
    )

    result = parse_lock_event(raw_event)

    assert result is not None
    assert len(result["locks"]) == 2

    assert result["locks"][0]["region"] == "Reference221.REFLOCK"
    assert result["locks"][0]["lock_mode"] == "EXCLUSIVE"
    assert result["locks"][0]["resource_fields"] == {"Fld2295": "0"}

    assert result["locks"][1]["region"] == "InfoRg35800.DIMS"
    assert result["locks"][1]["lock_mode"] == "EXCLUSIVE"
    assert result["locks"][1]["resource_fields"] == {
        "Fld2295": "0",
        "Fld35801": "69:b0a17c10c924aec011f1d2148cd87c97",
    }


def test_parse_lock_with_quoted_field_value():
    raw_event = make_tlock(
        "InfoRg38298.DIMS Exclusive "
        "Fld2295=0 "
        "Fld38299=69:b0a17c10c924aec011f1d2148cd87c97 "
        'Fld38300="СтандартныеПодсистемы.УправлениеДоступом.ПраваРолей"'
    )

    result = parse_lock_event(raw_event)

    assert result is not None
    assert len(result["locks"]) == 1

    assert result["locks"][0]["resource_fields"]["Fld38300"] == (
        "СтандартныеПодсистемы.УправлениеДоступом.ПраваРолей"
    )


def test_parse_lock_with_comma_inside_quoted_value():
    raw_event = make_tlock(
        "SystemSettings.SYSTEMLOCK Exclusive "
        'ObjectKey="LogonUnited.f/Такси,НастройкиОкнаТонкогоКлиента"'
    )

    result = parse_lock_event(raw_event)

    assert result is not None
    assert len(result["locks"]) == 1


def test_parse_lock_with_additional_attributes():
    raw_event = make_tlock(
        "SystemSettings.SYSTEMLOCK Exclusive "
        'ObjectKey="LogonUnited.f/Такси/НастройкиОкнаТонкогоКлиента" '
        "SettingsKeyHash=0 UserIdHash=2244921122"
    )

    result = parse_lock_event(raw_event)

    assert result is not None
    assert len(result["locks"]) == 1

    attributes = result["locks"][0]["attributes"]

    assert attributes["ObjectKey"] == (
        "LogonUnited.f/Такси/НастройкиОкнаТонкогоКлиента"
    )
    assert attributes["SettingsKeyHash"] == "0"
    assert attributes["UserIdHash"] == "2244921122"
