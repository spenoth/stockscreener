from pathlib import Path
import psycopg

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "mydb",
    "user": "mydb",
    "password": "mypassword",
}

CSV_FILE = Path("prices.csv")
TABLE_NAME = "prices"

with psycopg.connect(**DB_CONFIG) as conn:
    with conn.cursor() as cur:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            copy_sql = f"""
                COPY {TABLE_NAME}
                (id, ticker, timestamp, timeframe, open, high, low, close, volume, created_at)
                FROM STDIN
                WITH (
                    FORMAT CSV,
                    HEADER TRUE
                )
            """

            with cur.copy(copy_sql) as copy:
                while data := f.read(1024 * 1024):
                    copy.write(data)

    conn.commit()

print("Import completed.")