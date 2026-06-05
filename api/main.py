import logging
import logging.handlers
import time
import traceback
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    CORS_ALLOWED_ORIGINS, CORS_ALLOWED_ORIGIN_REGEX, CORS_ALLOW_CREDENTIALS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s UTC %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logging.Formatter.converter = time.gmtime
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connectivity
    try:
        conn = get_connection()
        conn.close()
        logger.info(
            "Database connection verified on startup (host=%s port=%s dbname=%s)",
            DB_HOST, DB_PORT, DB_NAME,
        )
    except Exception as exc:
        logger.error(
            "STARTUP FAILED: cannot connect to database at %s:%s/%s — %s",
            DB_HOST, DB_PORT, DB_NAME, exc,
        )
        raise RuntimeError(
            f"Cannot connect to database at {DB_HOST}:{DB_PORT}/{DB_NAME}"
        ) from exc
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_origin_regex=CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )



# ---------------------------------------------------------------------------
# Global exception handler — ensures no raw tracebacks leak into responses
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s: %s\n%s",
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Current BMSB results
# ---------------------------------------------------------------------------

@app.get("/api/screener/bmsb/current")
def get_current_bmsb(request: Request):
    try:
        conn = get_connection()
    except Exception as exc:
        logger.error(
            "DB connectivity failure on %s: %s\n%s",
            request.url.path,
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT symbol, exchange FROM quant.v_current_bmsb ORDER BY symbol;")
                rows = cur.fetchall()
        return [{"symbol": row[0], "exchange": row[1]} for row in rows]
    except Exception as exc:
        logger.error(
            "Query failure on %s: %s\n%s",
            request.url.path,
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    finally:
        conn.close()
