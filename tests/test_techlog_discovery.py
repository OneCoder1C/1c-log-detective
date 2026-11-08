from techlog_discovery import (
    discover_techlog_files,
    discover_techlog_process_dirs,
    get_default_techlog_root,
)


def test_default_techlog_root(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    result = get_default_techlog_root()

    assert result == tmp_path / "1C" / "1cv8" / "logs"


def test_default_root_without_local_app_data(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert get_default_techlog_root() is None


def test_discover_process_directories(tmp_path):
    log_root = tmp_path / "logs"

    process_names = [
        "1cv8c_20112",
        "1cv8c_6848",
        "1cv8s_28312",
        "1cv8s_31080",
    ]

    for name in process_names:
        process_dir = log_root / name
        process_dir.mkdir(parents=True)

        (process_dir / "26110601.log").write_text(
            "test event",
            encoding="utf-8",
        )

    result = discover_techlog_process_dirs(log_root)

    assert [path.name for path in result] == process_names


def test_ignore_directories_without_log_files(tmp_path):
    log_root = tmp_path / "logs"

    empty_dir = log_root / "1cv8c_100"
    empty_dir.mkdir(parents=True)

    other_dir = log_root / "other_process"
    other_dir.mkdir()

    result = discover_techlog_process_dirs(log_root)

    assert result == []


def test_missing_log_root(tmp_path):
    result = discover_techlog_process_dirs(tmp_path / "missing_logs")

    assert result == []


def test_discover_default_root(monkeypatch, tmp_path):
    log_root = tmp_path / "1C" / "1cv8" / "logs"
    process_dir = log_root / "1cv8c_12345"
    process_dir.mkdir(parents=True)

    (process_dir / "26110601.log").write_text(
        "test event",
        encoding="utf-8",
    )

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    result = discover_techlog_process_dirs()

    assert len(result) == 1
    assert result[0] == process_dir


def test_discover_techlog_files(tmp_path):
    log_root = tmp_path / "logs"

    expected_files = []

    for process_name in ("1cv8c_100", "1cv8s_200"):
        process_dir = log_root / process_name
        process_dir.mkdir(parents=True)

        for file_name in ("26110601.log", "26110602.log"):
            log_file = process_dir / file_name
            log_file.write_text("test event", encoding="utf-8")
            expected_files.append(log_file)

    result = discover_techlog_files(log_root)

    assert result == sorted(expected_files)


def test_discover_techlog_files_empty_root(tmp_path):
    assert discover_techlog_files(tmp_path / "missing") == []
