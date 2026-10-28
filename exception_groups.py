import re

from collections import Counter


def normalize_exception(description: str) -> str:
    """Возвращает категорию исключения по его описанию."""
    text = description.casefold()

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


def extract_guid(description: str) -> str | None:
    """Извлекает GUID из описания исключения."""
    match = re.search(
        r"\b[0-9a-fA-F]{8}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12}\b",
        description,
    )

    return match.group(0) if match else None


def get_exception_detail(description: str) -> str:
    """Извлекает и очищает уточнение из описания исключения."""
    description = " ".join(description.split())

    match = re.search(r"не выполнено\s+'([^']+)'", description, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    if "неверно указан пользователь или пароль" in description.casefold():
        return "Неверно указан пользователь или пароль"

    return description.strip(" :")


def count_exception_groups(descriptions: list[str]) -> dict[str, int]:
    """Подсчитывает исключения по категории и детали."""

    groups = Counter()

    for description in descriptions:
        category = normalize_exception(description)
        detail = get_exception_detail(description)

        key = f"{category}: {detail}"
        groups[key] += 1

    return dict(groups)
