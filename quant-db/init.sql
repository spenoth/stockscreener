-- Create schema
CREATE SCHEMA quant;

-- timeframe-ek
CREATE TYPE quant.timeframe_enum AS ENUM ('1h', '1d', '1w');

-- job típusok
CREATE TYPE quant.job_type_enum AS ENUM ('screener', 'signal');

-- direction (nem kötelező minden eventnél)
CREATE TYPE quant.direction_enum AS ENUM ('bullish', 'bearish');

CREATE TABLE quant.prices (
                              id BIGSERIAL PRIMARY KEY,
                              ticker TEXT NOT NULL,
                              timestamp TIMESTAMPTZ NOT NULL,
                              timeframe quant.timeframe_enum NOT NULL,

                              open NUMERIC NOT NULL,
                              high NUMERIC NOT NULL,
                              low NUMERIC NOT NULL,
                              close NUMERIC NOT NULL,
                              volume NUMERIC,

                              created_at TIMESTAMPTZ DEFAULT NOW(),

                              CONSTRAINT unique_price UNIQUE (ticker, timestamp, timeframe)
);

CREATE INDEX quant_idx_prices_ticker_tf_time
    ON quant.prices (ticker, timeframe, timestamp DESC);

CREATE INDEX quant_idx_prices_time
    ON quant.prices (timestamp DESC);

CREATE TABLE quant.jobs (
                            id BIGSERIAL PRIMARY KEY,
                            name TEXT NOT NULL,
                            type quant.job_type_enum NOT NULL,

                            schedule TEXT NOT NULL,
                            config JSONB NOT NULL,

                            enabled BOOLEAN DEFAULT TRUE,

                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX quant_idx_jobs_type
    ON quant.jobs (type);

CREATE INDEX quant_idx_jobs_enabled
    ON quant.jobs (enabled);

CREATE TABLE quant.events (
                              id BIGSERIAL PRIMARY KEY,
                              ticker TEXT NOT NULL,
                              timestamp TIMESTAMPTZ NOT NULL,
                              timeframe quant.timeframe_enum NOT NULL,

                              event_type TEXT NOT NULL,
                              direction quant.direction_enum,

                              value NUMERIC,
                              metadata JSONB,

                              job_id BIGINT,
                              created_at TIMESTAMPTZ DEFAULT NOW(),

                              CONSTRAINT fk_job
                                  FOREIGN KEY (job_id)
                                      REFERENCES quant.jobs(id)
                                      ON DELETE SET NULL
);

CREATE INDEX quant_idx_events_ticker_type_time
    ON quant.events (ticker, event_type, timestamp DESC);

CREATE INDEX quant_idx_events_type_time
    ON quant.events (event_type, timestamp DESC);

CREATE INDEX quant_idx_events_ticker_time
    ON quant.events (ticker, timestamp DESC);

CREATE INDEX quant_idx_events_metadata
    ON quant.events USING GIN (metadata);

CREATE TABLE quant.watchlist_snapshots (
                                           id BIGSERIAL PRIMARY KEY,
                                           name TEXT NOT NULL,
                                           week_id TEXT NOT NULL,

                                           created_at TIMESTAMPTZ DEFAULT NOW(),

                                           CONSTRAINT unique_snapshot UNIQUE (name, week_id)
);

CREATE INDEX quant_idx_watchlist_week
    ON quant.watchlist_snapshots (week_id);

CREATE TABLE quant.watchlists (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE quant.watchlist_versions (
    id BIGSERIAL PRIMARY KEY,
    watchlist_id BIGINT NOT NULL,
    version BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    run_outcome   TEXT,
    total_tickers INTEGER,
    scanned_count INTEGER,
    failed_count  INTEGER,

    FOREIGN KEY (watchlist_id)
        REFERENCES quant.watchlists(id),

    UNIQUE(watchlist_id, version)
);

CREATE TABLE quant.watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    watchlist_version_id BIGINT NOT NULL,
    ticker TEXT NOT NULL,

    FOREIGN KEY (watchlist_version_id)
        REFERENCES quant.watchlist_versions(id),

    UNIQUE(watchlist_version_id, ticker)
);

CREATE TABLE quant.tickers (
                               id BIGSERIAL PRIMARY KEY,
                               symbol TEXT NOT NULL UNIQUE,
                               name TEXT,
                               exchange TEXT,
                               active BOOLEAN DEFAULT TRUE,
                               created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX quant_idx_tickers_active
    ON quant.tickers (active);


-- Seed tickers
INSERT INTO quant.tickers (symbol, name, exchange, active) VALUES
    ('TSLA', 'Tesla Inc.', 'NASDAQ', true),
    ('ARES', 'Ares Management Corporation', 'NYSE', false),
    ('SWK', 'Stanley Black & Decker Inc.', 'NYSE', false),
    ('V', 'Visa Inc.', 'NYSE', false),
    ('MSFT', 'Microsoft Corporation', 'NASDAQ', false),
    ('MSCI', 'MSCI Inc.', 'NYSE', false),
    ('MAIN', 'Main Street Capital Corporation', 'NYSE', false)
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO quant.watchlists (name)
VALUES
    ('BMSB_ABOVE'),
    ('BMSB_DISCOUNT')
--    ('SUPERTREND_BULLISH'),
--    ('SMA20_BOUNCE'),
--    ('RSI_OVERSOLD')
ON CONFLICT (name) DO NOTHING;

-- Wave 1 – F-03: Exchange completeness verification.
-- Run this query after seeding to confirm no active ticker is missing exchange data.
-- Must return 0 rows before a production run (active_tickers_missing_exchange).
-- SELECT symbol FROM quant.tickers WHERE active = true AND (exchange IS NULL OR exchange = '');
-- active_tickers_missing_exchange

-- Wave 1 – F-04: canonical view for current passing BMSB_ABOVE stocks
-- "Latest version" = watchlist_version with the most recent created_at for BMSB_ABOVE.
-- Returns empty set when latest version has zero items (BR-8).
-- Scoped exclusively to BMSB_ABOVE (BR-9).
CREATE OR REPLACE VIEW quant.v_current_bmsb AS
SELECT
    wi.ticker  AS symbol,
    t.exchange AS exchange
FROM quant.watchlist_items wi
         JOIN quant.watchlist_versions wv
              ON wi.watchlist_version_id = wv.id
         JOIN quant.watchlists wl
              ON wv.watchlist_id = wl.id
         JOIN quant.tickers t
              ON wi.ticker = t.symbol
WHERE wl.name = 'BMSB_ABOVE'
  AND wv.id = (
    SELECT wv2.id
    FROM quant.watchlist_versions wv2
             JOIN quant.watchlists wl2 ON wv2.watchlist_id = wl2.id
    WHERE wl2.name = 'BMSB_ABOVE'
    ORDER BY wv2.created_at DESC, wv2.id DESC
    LIMIT 1
    );
