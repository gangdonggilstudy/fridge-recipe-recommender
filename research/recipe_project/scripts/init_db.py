# from pathlib import Path

# from db.connection import engine


# BASE_DIR = Path(__file__).resolve().parent.parent
# SCHEMA_PATH = BASE_DIR / "db" / "schema_sqlite.sql"


# def main():
#     schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

#     with engine.begin() as conn:
#         for statement in schema_sql.split(";"):
#             statement = statement.strip()

#             if statement:
#                 conn.exec_driver_sql(statement)

#     print("[OK] SQLite DB initialized")


# if __name__ == "__main__":
#     main()

from pathlib import Path

from db.connection import DB_DIALECT, engine


BASE_DIR = Path(__file__).resolve().parent.parent

SCHEMA_FILE_MAP = {
    "sqlite": BASE_DIR / "db" / "schema_sqlite.sql",
    "mysql": BASE_DIR / "db" / "schema_mysql.sql",
}


def main():
    schema_path = SCHEMA_FILE_MAP.get(DB_DIALECT)

    if not schema_path:
        raise RuntimeError(f"Unsupported DB dialect: {DB_DIALECT}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    with engine.begin() as conn:
        for statement in schema_sql.split(";"):
            statement = statement.strip()

            if statement:
                conn.exec_driver_sql(statement)

    print(f"[OK] {DB_DIALECT} DB initialized")


if __name__ == "__main__":
    main()