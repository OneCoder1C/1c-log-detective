from incident_correlation import _extract_select_fields


def test_union_all_id_query_normalizes_db_and_sdbl_fields():
    db_sql = """
    SELECT 0x000001A6, T1._IDRRef
    FROM _Reference422 T1
    UNION ALL
    SELECT 0x00000077, T2._IDRRef
    FROM _Reference119 T2
    """

    sdbl_sql = """
    SELECT Q_000_T_001.ID Q_000_F_000
    FROM Reference422 Q_000_T_001
    UNION ALL
    SELECT Q_001_T_001.ID
    FROM Reference119 Q_001_T_001
    """

    assert _extract_select_fields(db_sql) == _extract_select_fields(sdbl_sql)


def test_union_all_field_query_normalizes_db_and_sdbl_fields():
    db_sql = """
    SELECT T1._Fld57625
    FROM _Reference422 T1
    UNION ALL
    SELECT T2._Fld50204
    FROM _Reference119 T2
    """

    sdbl_sql = """
    SELECT Q_000_T_001.Fld57625 Q_000_F_000_00
    FROM Reference422 Q_000_T_001
    UNION ALL
    SELECT Q_001_T_001.Fld50204
    FROM Reference119 Q_001_T_001
    """

    assert _extract_select_fields(db_sql) == _extract_select_fields(sdbl_sql)
