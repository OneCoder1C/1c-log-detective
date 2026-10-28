import re


def extract_rows(raw_text: str) -> int | None:
    """Извлекает количество строк из события технологического журнала SDBL."""
    match = re.search(r"(?:^|,)Rows=(\d+)(?:,|$)", raw_text)

    if match is None:
        return None

    return int(match.group(1))


def extract_sql(raw_text: str) -> str | None:
    """Извлекает SQL из полей Sdbl или Sql технологического журнала."""

    first_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
    parts = first_line.split(",", maxsplit=2)
    event_type = parts[1] if len(parts) > 1 else None

    # Поддерживаем как полный текст события, так и отдельное поле Sdbl=.
    if event_type == "SDBL":
        field_name = "Sdbl"
    elif event_type == "DBV8DBEng":
        field_name = "Sql"
    elif re.search(r"(?:^|,)Sdbl=", raw_text):
        field_name = "Sdbl"
    elif re.search(r"(?:^|,)Sql=", raw_text):
        field_name = "Sql"
    else:
        return None

    match = re.search(
        rf"(?:^|,){field_name}=(.*?)(?=,NParams=|,Rows=|,Context=|$)",
        raw_text,
        re.DOTALL,
    )

    if match is None:
        return None

    return match.group(1).strip().strip("'")


from collections import Counter


def count_sql_queries(events) -> Counter:
    """Подсчитывает частоту SQL-команд по нормализованному тексту."""
    queries = []

    for event in events:
        if event.event_type != "SDBL":
            continue

        sql = extract_sql(event.raw_text)

        if sql is not None:
            queries.append(normalize_sql(sql))

    return Counter(queries)


def count_sql_commands(events) -> Counter:
    """Подсчитывает SQL-команды из событий SDBL и DBV8DBEng."""
    counts = Counter()

    for event in events:
        if event.event_type not in {"SDBL", "DBV8DBEng"}:
            continue

        sql = extract_sql(event.raw_text)

        if sql is None:
            continue

        if get_sql_type(sql) == "OTHER":
            continue

        counts[normalize_sql(sql)] += 1

    return counts


def count_sql_commands_by_source(events) -> dict[str, Counter]:
    """Подсчитывает SQL-команды отдельно для SDBL и DBV8DBEng."""
    counts = {
        "SDBL": Counter(),
        "DBV8DBEng": Counter(),
    }

    for event in events:
        if event.event_type not in counts:
            continue

        sql = extract_sql(event.raw_text)

        if sql is None or get_sql_type(sql) == "OTHER":
            continue

        counts[event.event_type][normalize_sql(sql)] += 1

    return counts


def normalize_sql(sql: str) -> str:
    """Заменяет числовые значения SQL вне строковых литералов на знак вопроса."""
    result = []
    in_string = False
    i = 0

    while i < len(sql):
        char = sql[i]

        if char == "'":
            result.append(char)

            # Две одинарные кавычки внутри строки означают кавычку в значении.
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                result.append("'")
                i += 2
                continue

            in_string = not in_string
            i += 1
            continue

        if (
            not in_string
            and sql[i : i + 2].lower() == "0x"
            and i + 2 < len(sql)
            and sql[i + 2] in "0123456789abcdefABCDEF"
            and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_"))
        ):
            i += 2

            while i < len(sql) and sql[i] in "0123456789abcdefABCDEF":
                i += 1

            result.append("?")
            continue

        if not in_string and char.isdigit():
            # Число, начинающееся внутри идентификатора, не заменяем.
            if i > 0 and (sql[i - 1].isalnum() or sql[i - 1] == "_"):
                result.append(char)
                i += 1
                continue

            # Находим все цифры подряд.
            start = i
            while i < len(sql) and sql[i].isdigit():
                i += 1

            # Если после цифр идёт буква или _, это часть идентификатора.
            if i < len(sql) and (sql[i].isalnum() or sql[i] == "_"):
                result.append(sql[start:i])
                continue

            result.append("?")
            continue

        result.append(char)
        i += 1

    return "".join(result)


def get_sql_type(sql: str) -> str:
    """Определяет тип SQL-команды по первому ключевому слову."""
    match = re.match(r"\s*([A-Za-z]+)", sql)

    if match is None:
        return "OTHER"

    command = match.group(1).upper()

    if command in {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "GET",
        "DROP",
    }:
        return command

    return "OTHER"
