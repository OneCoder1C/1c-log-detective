from user_analysis import analyze_user_events, format_user_analysis


def test_analyzes_events_by_user(tmp_path):
    log_file = tmp_path / "users.log"

    log_file.write_text(
        "10:00:00.000000-0,EXCP,1,level=ERROR,"
        'Usr="Иванов",Descr="Ошибка"\n'
        "10:00:01.000000-0,TLOCK,2,level=INFO,"
        'Usr="Иванов",Locks="Document.Exclusive"\n'
        "10:00:02.000000-0,SDBL,3,level=INFO,"
        'Usr="Петров",Sql="SELECT 1"\n',
        encoding="utf-8",
    )

    result = analyze_user_events(log_file, user="Иванов")

    assert result["total_events"] == 2
    assert result["by_type"] == {"EXCP": 1, "TLOCK": 1}
    assert result["exceptions"] == 1


def test_counts_all_users(tmp_path):
    log_file = tmp_path / "users.log"

    log_file.write_text(
        "10:00:00.000000-0,EXCP,1,level=ERROR,"
        'Usr="Иванов",Descr="Ошибка"\n'
        "10:00:01.000000-0,TLOCK,2,level=INFO,"
        'Usr="Петров",Locks="Document.Exclusive"\n',
        encoding="utf-8",
    )

    result = analyze_user_events(log_file)

    assert result["users"] == {"Иванов": 1, "Петров": 1}
    assert result["total_events"] == 2


def test_filters_event_types(tmp_path):
    log_file = tmp_path / "users.log"

    log_file.write_text(
        "10:00:00.000000-0,EXCP,1,level=ERROR,"
        'Usr="Иванов",Descr="Ошибка"\n'
        "10:00:01.000000-0,TLOCK,2,level=INFO,"
        'Usr="Иванов",Locks="Document.Exclusive"\n',
        encoding="utf-8",
    )

    result = analyze_user_events(
        log_file,
        user="Иванов",
        event_types={"EXCP"},
    )

    assert result["total_events"] == 1
    assert result["by_type"] == {"EXCP": 1}


def test_rejects_unsupported_event_type(tmp_path):
    log_file = tmp_path / "users.log"
    log_file.write_text("", encoding="utf-8")

    try:
        analyze_user_events(log_file, event_types={"PROC"})
    except ValueError:
        pass
    else:
        raise AssertionError("Ожидалась ошибка ValueError")


def test_formats_user_report():
    result = {
        "user": "Иванов",
        "total_events": 2,
        "matched_events": 2,
        "by_type": {"EXCP": 1, "TLOCK": 1},
        "exceptions": 1,
        "users": {"Иванов": 2},
    }

    report = format_user_analysis(result)

    assert "Иванов" in report
    assert "EXCP: 1" in report
    assert "TLOCK: 1" in report
