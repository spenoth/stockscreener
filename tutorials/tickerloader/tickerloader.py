import csv
import psycopg2
from config import DB_CONFIG

print(f"[DEBUG] Connecting to database '{DB_CONFIG['dbname']}' at {DB_CONFIG['host']}:{DB_CONFIG['port']} as user '{DB_CONFIG['user']}'")
conn = psycopg2.connect(**DB_CONFIG)
print("[DEBUG] Connection established successfully.")

cur = conn.cursor()

inserted = 0
updated = 0

with open("us_symbols.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    rows = list(reader)
    print(f"[DEBUG] Loaded {len(rows)} rows from us_symbols.csv")

    for row in rows:
        symbol = row["ticker"].strip()
        name = row["name"].strip()
        exchange = row["exchange"].strip()

        print(f"[DEBUG] Upserting ticker: {symbol} | {name} | {exchange}")
        cur.execute(
            """
            INSERT INTO quant.tickers (symbol, name, exchange)
            VALUES (%s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE
            SET
                name = EXCLUDED.name,
                exchange = EXCLUDED.exchange
            RETURNING (xmax = 0) AS inserted
            """,
            (symbol, name, exchange)
        )
        was_inserted = cur.fetchone()[0]
        if was_inserted:
            inserted += 1
        else:
            updated += 1

conn.commit()
print(f"[DEBUG] Commit done. Inserted: {inserted}, Updated: {updated}")
cur.close()
conn.close()
print("[DEBUG] Connection closed.")
