from sql_analysis import (
    count_sql_commands,
    extract_rows,
    extract_sql,
    get_sql_type,
)


def test_extract_rows_returns_number():
    assert extract_rows("Sdbl=SELECT 1,Rows=5") == 5


def test_extract_rows_returns_zero():
    assert extract_rows("Sdbl=schema set local 1;,Rows=0") == 0


def test_extract_rows_returns_none_when_missing():
    assert extract_rows("Sdbl=SELECT 1") is None


def test_extract_sql_extracts_query():
    assert extract_sql("Sdbl=SELECT 1,Rows=1") == "SELECT 1"


def test_extract_sql_extracts_multiline_query():
    raw_text = "Sdbl='SELECT\nFld1\nFROM Table1',Rows=1"

    assert extract_sql(raw_text) == "SELECT\nFld1\nFROM Table1"


def test_extract_sql_returns_none_when_missing():
    assert extract_sql("Rows=1") is None


from types import SimpleNamespace

from sql_analysis import count_sql_queries


def test_count_sql_queries_counts_repeated_commands():
    events = [
        SimpleNamespace(
            event_type="SDBL",
            raw_text="Sdbl=SELECT * FROM Table1 WHERE ID = 10,Rows=1",
        ),
        SimpleNamespace(
            event_type="SDBL",
            raw_text="Sdbl=SELECT * FROM Table1 WHERE ID = 20,Rows=1",
        ),
        SimpleNamespace(
            event_type="SDBL",
            raw_text="Sdbl=SELECT * FROM Table1 WHERE ID = 30,Rows=1",
        ),
    ]

    counts = count_sql_queries(events)

    normalized_query = "SELECT * FROM Table1 WHERE ID = ?"
    assert counts[normalized_query] == 3


def test_count_sql_queries_ignores_other_events():
    events = [
        SimpleNamespace(
            event_type="EXCP",
            raw_text="Sdbl=SELECT 1,Rows=1",
        ),
    ]

    counts = count_sql_queries(events)

    assert len(counts) == 0


from sql_analysis import normalize_sql


def test_normalize_sql_groups_different_numbers():
    sql1 = "SELECT * FROM Table1 WHERE ID = 10"
    sql2 = "SELECT * FROM Table1 WHERE ID = 20"

    assert normalize_sql(sql1) == normalize_sql(sql2)


def test_normalize_sql_preserves_digits_in_identifiers():
    sql = "SELECT Fld123 FROM Table1 WHERE ID = 42"

    assert normalize_sql(sql) == "SELECT Fld123 FROM Table1 WHERE ID = ?"


def test_normalize_sql_preserves_numbers_inside_strings():
    sql = "SELECT * FROM T WHERE Name = 'Заказ 123'"

    assert normalize_sql(sql) == "SELECT * FROM T WHERE Name = 'Заказ 123'"


def test_normalize_sql_replaces_numbers_outside_strings():
    sql = "SELECT * FROM T WHERE ID = 42"

    assert normalize_sql(sql) == "SELECT * FROM T WHERE ID = ?"


def test_normalize_sql_preserves_escaped_quotes():
    sql = "SELECT * FROM T WHERE Name = 'Заказ ''123''' AND ID = 42"

    assert (
        normalize_sql(sql) == "SELECT * FROM T WHERE Name = 'Заказ ''123''' AND ID = ?"
    )


def test_normalize_sql_preserves_digits_inside_identifiers():
    sql = "SELECT Fld32349 FROM Const32348 WHERE ID = 10"

    result = normalize_sql(sql)

    assert result == "SELECT Fld32349 FROM Const32348 WHERE ID = ?"


def test_normalize_sql_preserves_digits_in_alphanumeric_tokens():
    sql = "SELECT 123abc, 45_xyz, 67 FROM Table1"

    result = normalize_sql(sql)

    assert result == "SELECT 123abc, 45_xyz, ? FROM Table1"


def test_normalize_sql_replaces_hexadecimal_literals():
    sql = "SELECT * FROM Table1 WHERE RecordKey = 0x31"

    result = normalize_sql(sql)

    assert result == "SELECT * FROM Table1 WHERE RecordKey = ?"


def test_count_sql_queries_ignores_sdbl_events_without_sql():
    events = [
        SimpleNamespace(
            event_type="SDBL",
            raw_text="Sdbl=SELECT * FROM Table1 WHERE ID = 10,Rows=1",
        ),
        SimpleNamespace(
            event_type="SDBL",
            raw_text="Func=BeginTransaction",
        ),
        SimpleNamespace(
            event_type="SDBL",
            raw_text="Func=HoldConnection,Context='test'",
        ),
    ]

    counts = count_sql_queries(events)

    assert sum(counts.values()) == 1


def test_get_sql_type_identifies_select():
    assert get_sql_type("SELECT * FROM Table1") == "SELECT"


def test_get_sql_type_ignores_leading_spaces_and_case():
    assert get_sql_type("  select * FROM Table1") == "SELECT"


def test_get_sql_type_identifies_update():
    assert get_sql_type("UPDATE Table1 SET ID = 10") == "UPDATE"


def test_get_sql_type_returns_other_for_unknown_command():
    assert get_sql_type("schema set local ?;") == "OTHER"


def test_get_sql_type_returns_other_for_empty_string():
    assert get_sql_type("") == "OTHER"


def test_get_sql_type_identifies_get():
    assert get_sql_type("GET NGENERATIONS") == "GET"


def test_get_sql_type_identifies_drop():
    assert get_sql_type("DROP TABLE #T123abc") == "DROP"


from types import SimpleNamespace


def test_count_sql_commands_counts_recognized_commands():
    events = [
        SimpleNamespace(event_type="SDBL", raw_text="Sdbl=SELECT * FROM Table1"),
        SimpleNamespace(event_type="SDBL", raw_text="Sdbl=SELECT * FROM Table1"),
        SimpleNamespace(event_type="SDBL", raw_text="Sdbl=UPDATE Table1 SET ID = 10"),
    ]

    counts = count_sql_commands(events)

    assert sum(counts.values()) == 3
    assert len(counts) == 2


def test_count_sql_commands_ignores_other_and_non_sdbl_events():
    events = [
        SimpleNamespace(event_type="SDBL", raw_text="Sdbl=schema set local 1;"),
        SimpleNamespace(event_type="EXCP", raw_text="Sdbl=SELECT * FROM Table1"),
    ]

    counts = count_sql_commands(events)

    assert sum(counts.values()) == 0
