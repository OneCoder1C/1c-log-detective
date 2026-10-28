import pytest

from exception_groups import get_exception_detail, normalize_exception


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (
            "Не удалось заблокировать запись таблицы ACTIVEUSERS",
            "Не удалось заблокировать запись",
        ),
        (
            "Файл не обнаружен: keystor.dat",
            "Файл не обнаружен",
        ),
        (
            "Ошибка программного лицензирования: ошибка привязки",
            "Ошибка привязки программной лицензии",
        ),
        (
            "Ошибка программного лицензирования: срок действия закончился",
            "Истёк срок действия программной лицензии",
        ),
        (
            "Неверно указан пользователь или пароль",
            "Ошибка авторизации",
        ),
        (
            "Ошибка при выполнении файловой операции",
            "Ошибка файловой операции",
        ),
        (
            "Ошибка в неизвестной подсистеме",
            "Прочие исключения",
        ),
    ],
)
def test_normalize_exception(description, expected):
    assert normalize_exception(description) == expected


from exception_groups import get_exception_detail


def test_get_exception_detail_extracts_table_name():
    description = (
        "Не удалось заблокировать запись. Действие "
        "(изменение, удаление или блокировка записи) "
        "не выполнено 'DATAZONEOBJECTLOCKS'"
    )

    assert get_exception_detail(description) == "DATAZONEOBJECTLOCKS"


def test_get_exception_detail_extracts_activeusers():
    description = (
        "Не удалось заблокировать запись. Действие "
        "(изменение, удаление или блокировка записи) "
        "не выполнено 'ACTIVEUSERS'"
    )

    assert get_exception_detail(description) == "ACTIVEUSERS"


def test_get_exception_detail_returns_original_description():
    description = "Неверно указан пользователь или пароль"

    assert get_exception_detail(description) == description


def test_get_exception_detail_extracts_authentication_message():
    description = (
        "src\\backend\\src\\FileJobManagerImpl.cpp(1340):\n"
        "a01f465c-ed70-442e-ada5-847668d7a41c: "
        "Неверно указан пользователь или пароль\n"
        "Неправильное имя пользователя"
    )

    result = get_exception_detail(description)

    assert result == "Неверно указан пользователь или пароль"


def test_get_exception_detail_normalizes_whitespace():
    result = get_exception_detail("  Ошибка   подключения \n к   серверу  ")

    assert result == "Ошибка подключения к серверу"


def test_get_exception_detail_cleans_extracted_message():
    result = get_exception_detail("Операция не выполнено '  подключение   '")

    assert result == "подключение"


from exception_groups import count_exception_groups


def test_count_exception_groups_separates_table_names():
    descriptions = [
        "Не удалось заблокировать запись. Действие "
        "не выполнено 'DATAZONEOBJECTLOCKS'",
        "Не удалось заблокировать запись. Действие "
        "не выполнено 'DATAZONEOBJECTLOCKS'",
        "Не удалось заблокировать запись. Действие " "не выполнено 'ACTIVEUSERS'",
    ]

    result = count_exception_groups(descriptions)

    assert result == {
        "Не удалось заблокировать запись: DATAZONEOBJECTLOCKS": 2,
        "Не удалось заблокировать запись: ACTIVEUSERS": 1,
    }


def test_count_exception_groups_empty():
    assert count_exception_groups([]) == {}
