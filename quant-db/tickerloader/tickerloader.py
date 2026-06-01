import csv
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    dbname="mydb",
    user="myuser",
    password="mypassword"
)

cur = conn.cursor()

with open("tickers.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        symbol = row["ticker"].strip()
        name = row["name"].strip()
        exchange = row["exchange"].strip()

        cur.execute(
            """
            INSERT INTO tickers (symbol, name, exchange)
            VALUES (%s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE
            SET
                name = EXCLUDED.name,
                exchange = EXCLUDED.exchange
            """,
            (symbol, name, exchange)
        )

conn.commit()
cur.close()
conn.close()