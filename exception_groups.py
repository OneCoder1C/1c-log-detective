import re
from collections import Counter


GUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}\b"
)

EXCEPTION_DETAIL_PATTERN = re.compile(
    r"не выполнено\s+'([^']+)'",
    re.IGNORECASE,
)

EXCEPTION_RESOURCE_PATTERN = re.compile(
    r"не выполнено\s+'([A-Z][A-Z0-9_]*)'",
    re.IGNORECASE,
)


def _normalize_description(description: str | None) -> str:
    """Приводит описание исключения к безопасной строке."""
    if not isinstance(description, str):
        return ""

    return " ".join(description.split())


def normalize_exception(description: str | None) -> str:
    """Возвращает категорию исключения по его описанию."""
    text = _normalize_description(description).casefold()

    if "не удалось заблокировать запись" in text:
        return "Не удалось заблокировать запись"

    if "файл не обнаружен" in text:
        return "Файл не обнаружен"

    if "ошибка программного лицензирования" in text:
        if "ошибка привязки" in text:
            return "Ошибка привязки программной лицензии"

        if "срок действия закончился" in text:
            return "Истёк срок действия программной лицензии"

        return "Ошибка программного лицензирования"

    if "неверно указан пользователь" in text:
        return "Ошибка авторизации"

    if "ошибка при выполнении файловой операции" in text:
        return "Ошибка файловой операции"

    if "dynamicalworkcache" in text:
        return "Ошибка файлового кэша"

    return "Прочие исключения"


def extract_guid(description: str | None) -> str | None:
    """Извлекает GUID из описания исключения."""
    text = _normalize_description(description)
    match = GUID_PATTERN.search(text)

    return match.group(0) if match else None


def get_exception_detail(description: str | None) -> str:
    """Извлекает и очищает уточнение из описания исключения."""
    text = _normalize_description(description)

    match = EXCEPTION_DETAIL_PATTERN.search(text)

    if match:
        return match.group(1).strip()

    if "неверно указан пользователь или пароль" in text.casefold():
        return "Неверно указан пользователь или пароль"

    return text.strip(" :")


def count_exception_groups(
    descriptions: list[str | None],
) -> dict[str, int]:
    """Подсчитывает исключения по категории и детали."""
    groups = Counter()

    for description in descriptions:
        category = normalize_exception(description)
        detail = get_exception_detail(description)

        key = f"{category}: {detail}"
        groups[key] += 1

    return dict(groups)


def extract_exception_resource(
    description: str | None,
) -> str | None:
    """Извлекает имя ресурса из описания исключения."""
    text = _normalize_description(description)
    match = EXCEPTION_RESOURCE_PATTERN.search(text)

    return match.group(1) if match else None
