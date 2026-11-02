import os

import pytest
import unified_analysis

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


def test_analyze_techlog_file_removes_database_on_error(tmp_path, monkeypatch):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "12:00:00.000000-0,EXCP,1,level=ERROR,Descr='Ошибка'\n",
        encoding="utf-8",
    )

    database_paths = []
    original_named_temporary_file = unified_analysis.tempfile.NamedTemporaryFile

    def track_temporary_file(*args, **kwargs):
        temporary_file = original_named_temporary_file(*args, **kwargs)
        database_paths.append(temporary_file.name)
        return temporary_file

    def raise_error(self, event):
        raise RuntimeError("Тестовая ошибка")

    monkeypatch.setattr(
        unified_analysis.tempfile,
        "NamedTemporaryFile",
        track_temporary_file,
    )
    monkeypatch.setattr(
        unified_analysis.StreamingPerformanceAnalyzer,
        "add_event",
        raise_error,
    )

    with pytest.raises(RuntimeError, match="Тестовая ошибка"):
        unified_analysis.analyze_techlog_file(log_file)

    assert len(database_paths) == 1
    assert not os.path.exists(database_paths[0])


def test_analyze_techlog_file_counts_lock_exceptions(tmp_path):
    log_file = tmp_path / "lock_exceptions.log"
    log_file.write_text(
        "12:00:00.000000-0,EXCP,1,level=ERROR,"
        "Descr='Не удалось заблокировать запись'\n"
        "12:00:01.000000-0,EXCP,1,level=ERROR,"
        "Descr='Обычная ошибка'\n"
        "12:00:02.000000-0,EXCP,1,level=ERROR,"
        "Descr='Не удалось заблокировать запись'\n",
        encoding="utf-8",
    )

    result = analyze_techlog_file(log_file)

    assert result["total_events"] == 3
    assert result["by_type"]["EXCP"] == 3
    assert result["lock_exceptions_count"] == 2
