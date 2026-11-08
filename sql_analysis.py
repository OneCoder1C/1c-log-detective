import re

SQL_TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO)\s+"
    r"(?:\[?([A-Za-z_][\w$]*)\]?\.)?"
    r"\[?([A-Za-z_][\w$]*)\]?",
    re.IGNORECASE,
)


def extract_rows(raw_text: str) -> int | None:
    """Извлекает количество строк из события технологического журнала SDBL."""
    match = re.search(r"(?:^|,)Rows=(\d+)(?:,|$)", raw_text)

    if match is None:
        return None

    return int(match.group(1))


def extract_rows_affected(raw_text: str) -> int | None:
    """Извлекает количество затронутых строк из DBV8DBEng."""
    match = re.search(r"(?:^|,)RowsAffected=(\d+)(?:,|$)", raw_text)

    if match is None:
        return None

    return int(match.group(1))


SQL_FIELD_END_PATTERN = re.compile(r"(?:NParams|Rows|Context)=")


def extract_sql(raw_text: str) -> str | None:
    """Извлекает SQL из полей Sdbl или Sql технологического журнала."""

    first_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
    parts = first_line.split(",", maxsplit=2)
    event_type = parts[1] if len(parts) > 1 else None

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

    match = re.search(rf"(?:^|,){field_name}=", raw_text)

    if match is None:
        return None

    sql_start = match.end()
    sql_text = raw_text[sql_start:]

    in_string = False
    i = 0

    while i < len(sql_text):
        char = sql_text[i]

        if char == "'":
            if in_string and i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                i += 2
                continue

            in_string = not in_string

        elif char == "," and not in_string:
            if SQL_FIELD_END_PATTERN.match(sql_text, i + 1):
                sql_text = sql_text[:i]
                break

        i += 1

    sql = sql_text.strip()

    if len(sql) >= 2 and sql[0] == sql[-1] and sql[0] in {"'", '"'}:
        sql = sql[1:-1]

    return sql or None


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


def normalize_sql_reference(sql: str) -> str:
    """Заменяет строковые, числовые и шестнадцатеричные литералы на ?."""
    result = []
    in_string = False
    i = 0

    while i < len(sql):
        char = sql[i]

        if char == "'":
            if not in_string:
                result.append("?")
                in_string = True
            elif i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            else:
                in_string = False

            i += 1
            continue

        if in_string:
            i += 1
            continue

        if (
            sql[i : i + 2].lower() == "0x"
            and i + 2 < len(sql)
            and sql[i + 2] in "0123456789abcdefABCDEF"
            and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_"))
        ):
            i += 2
            while i < len(sql) and sql[i] in "0123456789abcdefABCDEF":
                i += 1
            result.append("?")
            continue

        if char.isdigit():
            if i > 0 and (sql[i - 1].isalnum() or sql[i - 1] == "_"):
                result.append(char)
                i += 1
                continue

            start = i
            while i < len(sql) and sql[i].isdigit():
                i += 1

            if i < len(sql) and (sql[i].isalnum() or sql[i] == "_"):
                result.append(sql[start:i])
                continue

            result.append("?")
            continue

        result.append(char)
        i += 1

    return "".join(result)


def normalize_sql(sql: str) -> str:
    """Быстрая нормализация SQL с сохранением поведения эталона."""

    result = []
    in_string = False
    i = 0
    length = len(sql)

    while i < length:
        char = sql[i]

        # Обработка строк в одинарных кавычках.
        if char == "'":
            if not in_string:
                result.append("?")
                in_string = True
            elif i + 1 < length and sql[i + 1] == "'":
                i += 2
                continue
            else:
                in_string = False

            i += 1
            continue

        if in_string:
            i += 1
            continue

        # Обработка шестнадцатеричных литералов.
        if (
            char == "0"
            and i + 2 < length
            and sql[i + 1] in "xX"
            and sql[i + 2] in "0123456789abcdefABCDEF"
            and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_"))
        ):
            i += 2

            while i < length and sql[i] in "0123456789abcdefABCDEF":
                i += 1

            result.append("?")
            continue

        # Обработка числовых литералов.
        if char.isdigit():
            if i > 0 and (sql[i - 1].isalnum() or sql[i - 1] == "_"):
                result.append(char)
                i += 1
                continue

            start = i

            while i < length and sql[i].isdigit():
                i += 1

            if i < length and (sql[i].isalnum() or sql[i] == "_"):
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


def extract_sql_tables(sql: str) -> list[str]:
    """Извлекает имена таблиц из SQL-запроса."""

    tables = []
    seen = set()

    for match in SQL_TABLE_PATTERN.finditer(sql):
        schema = match.group(1)
        table = match.group(2)

        full_name = f"{schema}.{table}" if schema else table
        normalized_name = full_name.lower()

        if normalized_name not in seen:
            seen.add(normalized_name)
            tables.append(full_name)

    return tables
