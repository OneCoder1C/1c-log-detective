import os
from pathlib import Path


def get_default_techlog_root():
    """Возвращает стандартный каталог технологического журнала 1С."""
    local_app_data = os.environ.get("LOCALAPPDATA")

    if not local_app_data:
        return None

    return Path(local_app_data) / "1C" / "1cv8" / "logs"


def discover_techlog_process_dirs(log_root=None):
    """Находит каталоги клиентских и серверных процессов с файлами ТЖ."""
    if log_root is None:
        log_root = get_default_techlog_root()

    if log_root is None:
        return []

    log_root = Path(log_root)

    if not log_root.is_dir():
        return []

    process_dirs = []

    for prefix in ("1cv8c_", "1cv8s_"):
        for process_dir in sorted(log_root.glob(f"{prefix}*")):
            if process_dir.is_dir() and any(process_dir.glob("*.log")):
                process_dirs.append(process_dir)

    return process_dirs


def discover_techlog_files(log_root=None):
    """Находит все файлы технологического журнала в каталогах процессов."""
    log_files = []

    for process_dir in discover_techlog_process_dirs(log_root):
        log_files.extend(sorted(process_dir.glob("*.log")))

    return log_files
