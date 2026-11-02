import time

import sqlite3

from sql_analysis import (
    extract_sql,
    extract_sql_tables,
    get_sql_type,
    normalize_sql,
)

SLOW_THRESHOLD_US = 10_000


class StreamingPerformanceAnalyzer:
    """Потоковый анализ производительности с расчётом P95 через SQLite."""

    def __init__(self, database_path: str = "streaming_performance.db"):
        self.database_path = database_path
        self.connection = sqlite3.connect(database_path)

        self.batch_size = 1000
        self.duration_buffer = []
        self.sql_buffer = []
        self.table_buffer = []

        self.flush_count = 0
        self.duration_write_time = 0.0
        self.sql_write_time = 0.0
        self.table_write_time = 0.0
        self.commit_time = 0.0

        self._create_tables()

        self.connection.executescript(
            """
            DELETE FROM durations;
            DELETE FROM sql_stats;
            DELETE FROM table_stats;
            """
        )
        self.connection.commit()

    def _create_tables(self):
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS durations (
                event_type TEXT NOT NULL,
                duration_us INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sql_stats (
                sql_type TEXT NOT NULL,
                normalized_sql TEXT NOT NULL,
                duration_us INTEGER NOT NULL
            );


            CREATE TABLE IF NOT EXISTS table_stats (
                table_name TEXT NOT NULL,
                duration_us INTEGER NOT NULL
            );
            """
        )
        self.connection.commit()

    def _create_sql_index(self):
        """Создаёт индекс SQL-запросов после массовой загрузки данных."""

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sql_stats_query
            ON sql_stats(normalized_sql)
        """
        )

        self.connection.commit()

    def _create_duration_index(self):
        """Создаёт индекс длительности после массовой загрузки."""

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_durations_type
            ON durations(event_type)
            """
        )
        self.connection.commit()

    def _create_table_index(self):
        """Создаёт индекс таблиц после массовой загрузки."""

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_table_stats_name
            ON table_stats(table_name)
            """
        )
        self.connection.commit()

    def flush(self):
        """Записывает накопленные данные в SQLite и измеряет время операций."""

        self.max_duration_buffer = max(
            getattr(self, "max_duration_buffer", 0),
            len(self.duration_buffer),
        )

        self.max_sql_buffer = max(
            getattr(self, "max_sql_buffer", 0),
            len(self.sql_buffer),
        )

        self.max_table_buffer = max(
            getattr(self, "max_table_buffer", 0),
            len(self.table_buffer),
        )

        self.flush_count += 1

        if self.duration_buffer:
            start = time.perf_counter()

            self.connection.executemany(
                "INSERT INTO durations VALUES (?, ?)",
                self.duration_buffer,
            )

            self.duration_write_time += time.perf_counter() - start
            self.duration_buffer.clear()

        if self.sql_buffer:
            start = time.perf_counter()

            self.connection.executemany(
                "INSERT INTO sql_stats VALUES (?, ?, ?)",
                self.sql_buffer,
            )

            self.sql_write_time += time.perf_counter() - start
            self.sql_buffer.clear()

        if self.table_buffer:
            start = time.perf_counter()

            self.connection.executemany(
                "INSERT INTO table_stats VALUES (?, ?)",
                self.table_buffer,
            )

            self.table_write_time += time.perf_counter() - start
            self.table_buffer.clear()

        start = time.perf_counter()
        self.connection.commit()
        self.commit_time += time.perf_counter() - start

    def add_event(self, event):
        """Добавляет событие в буфер статистики."""

        duration = event.duration_us

        if duration is None:
            return

        duration_group = event.event_type

        if event.event_type == "SESN" and event.func:
            duration_group = f"SESN.{event.func}"

        self.duration_buffer.append((duration_group, duration))

        if event.event_type in {"SDBL", "DBV8DBEng"}:
            sql = extract_sql(event.raw_text)

            if sql:
                sql_type = get_sql_type(sql)

                if sql_type != "OTHER":
                    normalized_sql = normalize_sql(sql)

                    self.sql_buffer.append((sql_type, normalized_sql, duration))

                    for table in extract_sql_tables(sql):
                        self.table_buffer.append((table, duration))

                        if len(self.table_buffer) >= self.batch_size:
                            self.flush()

        if len(self.duration_buffer) >= self.batch_size:
            self.flush()

    def _duration_stats(self, table, group_column):
        """Рассчитывает статистику длительности по группам."""

        query = f"""
            SELECT
                {group_column},
                COUNT(*),
                SUM(duration_us),
                MAX(duration_us),
                AVG(duration_us),
                SUM(CASE WHEN duration_us >= ? THEN 1 ELSE 0 END)
            FROM {table}
            GROUP BY {group_column}
        """

        result = {}

        for row in self.connection.execute(query, (SLOW_THRESHOLD_US,)):
            key, count, total, maximum, average, slow_count = row

            p95_index = max(1, int(count * 0.95 + 0.999999))

            p95 = self.connection.execute(
                f"""
                SELECT duration_us
                FROM {table}
                WHERE {group_column} = ?
                ORDER BY duration_us
                LIMIT 1 OFFSET ?
                """,
                (key, p95_index - 1),
            ).fetchone()[0]

            result[key] = {
                "count": count,
                "total_duration_us": total,
                "max_duration_us": maximum,
                "avg_duration_us": average,
                "slow_count": slow_count,
                "p95_duration_us": p95,
            }

        return result

    def get_performance(self):
        """Возвращает общую статистику длительности по типам событий."""

        self.flush()
        stats = self._duration_stats("durations", "event_type")

        return {
            "total_events": sum(item["count"] for item in stats.values()),
            "by_event_type": stats,
        }

    def get_sql_performance(self):
        """Возвращает статистику SQL по типам команд."""

        self.flush()

        query = """
            SELECT sql_type, COUNT(*), SUM(duration_us),
                   MAX(duration_us), AVG(duration_us),
                   SUM(CASE WHEN duration_us >= ? THEN 1 ELSE 0 END)
            FROM sql_stats
            GROUP BY sql_type
        """

        result = {}

        for row in self.connection.execute(query, (SLOW_THRESHOLD_US,)):
            sql_type, count, total, maximum, average, slow_count = row

            p95_index = max(1, int(count * 0.95 + 0.999999))

            p95 = self.connection.execute(
                """
                SELECT duration_us FROM sql_stats
                WHERE sql_type = ?
                ORDER BY duration_us
                LIMIT 1 OFFSET ?
                """,
                (sql_type, p95_index - 1),
            ).fetchone()[0]

            result[sql_type] = {
                "count": count,
                "total_duration_us": total,
                "max_duration_us": maximum,
                "avg_duration_us": average,
                "slow_count": slow_count,
                "p95_duration_us": p95,
            }

        return result

    def get_slow_sql(self, limit=20):
        """Возвращает SQL-запросы с наибольшей суммарной длительностью."""

        self.flush()

        if limit < 0:
            raise ValueError("limit не может быть отрицательным")

        query = """
            SELECT normalized_sql, sql_type, COUNT(*),
                   SUM(duration_us), MAX(duration_us), AVG(duration_us),
                   SUM(CASE WHEN duration_us >= ? THEN 1 ELSE 0 END)
            FROM sql_stats
            GROUP BY normalized_sql, sql_type
            ORDER BY SUM(duration_us) DESC
            LIMIT ?
        """

        result = []

        for row in self.connection.execute(
            query,
            (SLOW_THRESHOLD_US, limit),
        ):
            sql, sql_type, count, total, maximum, average, slow_count = row

            p95_index = max(1, int(count * 0.95 + 0.999999))

            p95 = self.connection.execute(
                """
                SELECT duration_us FROM sql_stats
                WHERE normalized_sql = ? AND sql_type = ?
                ORDER BY duration_us
                LIMIT 1 OFFSET ?
                """,
                (sql, sql_type, p95_index - 1),
            ).fetchone()[0]

            result.append(
                {
                    "normalized_sql": sql,
                    "sql_type": sql_type,
                    "count": count,
                    "total_duration_us": total,
                    "max_duration_us": maximum,
                    "avg_duration_us": average,
                    "slow_count": slow_count,
                    "p95_duration_us": p95,
                }
            )

        return result

    def get_sql_tables(self):
        """Возвращает статистику использования SQL-таблиц."""

        self.flush()

        result = {}

        rows = self.connection.execute(
            """
            SELECT
                table_name,
                COUNT(*),
                SUM(duration_us),
                MAX(duration_us),
                AVG(duration_us)
            FROM table_stats
            GROUP BY table_name
            ORDER BY SUM(duration_us) DESC
            """
        )

        for row in rows:
            table_name, count, total, maximum, average = row

            result[table_name] = {
                "count": count,
                "total_duration_us": total,
                "max_duration_us": maximum,
                "avg_duration_us": average,
            }

        return result

    def close(self):
        """Записывает остатки буферов и закрывает соединение."""

        self.flush()
        print("\nСтатистика SQLite:")
        print(f"Количество flush: {self.flush_count}")
        print(f"Запись durations: {self.duration_write_time:.2f} сек.")
        print(f"Запись sql_stats: {self.sql_write_time:.2f} сек.")
        print(f"Запись table_stats: {self.table_write_time:.2f} сек.")
        print(f"Commit: {self.commit_time:.2f} сек.")
        print(f"Максимальный duration_buffer: {self.max_duration_buffer}")
        print(f"Максимальный sql_buffer: {self.max_sql_buffer}")
        print(f"Максимальный table_buffer: {self.max_table_buffer}")
        self.connection.close()

    def __enter__(self):
        """Поддерживает конструкцию with."""

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Закрывает соединение при выходе из with."""

        self.close()
        return False
