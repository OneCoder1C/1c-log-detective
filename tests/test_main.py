import os
import subprocess
import sys
from pathlib import Path


def test_error_filter():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    report_file = project_dir / "tests" / "test_report.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(project_dir / "sample_log.txt"),
            str(report_file),
            "ERROR",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode == 0
    assert "Ошибка блокировки таблицы" in result.stdout
    assert "Не удалось установить соединение" in result.stdout
    assert "Длительное выполнение запроса" not in result.stdout
    assert "WARNING:" not in result.stdout
    assert report_file.exists()


def test_warning_filter():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    report_file = project_dir / "tests" / "test_report_warnings.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(project_dir / "sample_log.txt"),
            str(report_file),
            "WARNING",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode == 0
    assert "Длительное выполнение запроса" in result.stdout
    assert "Ошибка блокировки таблицы" not in result.stdout
    assert "Не удалось установить соединение" not in result.stdout
    assert "WARNING: проверить длительность выполнения запроса" in result.stdout
    assert "ERROR:" not in result.stdout
    assert report_file.exists()


def test_critical_filter():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    report_file = project_dir / "tests" / "test_report_critical.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(project_dir / "sample_log.txt"),
            str(report_file),
            "CRITICAL",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode == 0
    assert "CRITICAL" in result.stdout
    assert "CRITICAL: проверить аварийное завершение задания" in result.stdout
    assert "ERROR:" not in result.stdout
    assert "WARNING:" not in result.stdout
    assert report_file.exists()


def test_all_filter():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    report_file = project_dir / "tests" / "test_report_all.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(project_dir / "sample_log.txt"),
            str(report_file),
            "ALL",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode == 0
    assert "Ошибка блокировки таблицы" in result.stdout
    assert "Не удалось установить соединение" in result.stdout
    assert "Длительное выполнение запроса" in result.stdout
    assert "CRITICAL" in result.stdout

    assert "ERROR: проверить конкурирующие транзакции" in result.stdout
    assert "ERROR: проверить доступность сервера 1С" in result.stdout
    assert "WARNING: проверить длительность выполнения запроса" in result.stdout
    assert "CRITICAL: проверить аварийное завершение задания" in result.stdout

    assert report_file.exists()


def test_missing_log_file():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    missing_file = project_dir / "tests" / "missing_log.txt"
    report_file = project_dir / "tests" / "test_report_missing.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(missing_file),
            str(report_file),
            "ALL",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode != 0


def test_unknown_filter():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    report_file = project_dir / "tests" / "test_report_unknown.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(project_dir / "sample_log.txt"),
            str(report_file),
            "ABC",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode != 0
    assert "Неизвестный фильтр: ABC" in result.stdout
    assert "Допустимые фильтры: ERROR, WARNING, CRITICAL, ALL" in result.stdout


def test_log_without_events(tmp_path):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    project_dir = Path(__file__).resolve().parent.parent
    log_file = tmp_path / "plain_log.txt"
    report_file = tmp_path / "plain_report.txt"

    log_file.write_text(
        "Запуск программы\nОперация выполнена успешно\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(project_dir / "main.py"),
            str(log_file),
            str(report_file),
            "ALL",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=project_dir,
    )

    assert result.returncode == 0
    assert "Ошибок не обнаружено" in result.stdout
    assert "Рекомендаций нет." in result.stdout
    assert report_file.exists()
