from unified_analysis import analyze_techlog_file


def test_analyze_techlog_file_counts_events(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "12:00:00.000000-0,EXCP,1,level=ERROR,Descr='Ошибка'\n"
        "12:00:01.000000-0,PROC,1,level=INFO\n",
        encoding="utf-8",
    )

    result = analyze_techlog_file(log_file)

    assert result["total_events"] == 2
    assert result["by_type"]["EXCP"] == 1
    assert result["by_type"]["PROC"] == 1
    assert result["by_level"]["ERROR"] == 1
    assert result["by_level"]["INFO"] == 1
