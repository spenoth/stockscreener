import os

DB_CONFIG = {
    "host":     os.environ.get("PGHOST",     "localhost"),
    "dbname":   os.environ.get("PGDATABASE", "mydb"),
    "user":     os.environ.get("PGUSER",     "myuser"),
    "password": os.environ.get("PGPASSWORD", "mypassword"),
    "port":     int(os.environ.get("PGPORT", "5432")),
}

