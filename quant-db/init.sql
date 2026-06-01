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
                               active BOOLEAN DEFAULT TRUE,
                               created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX quant_idx_tickers_active
    ON quant.tickers (active);

ALTER TABLE quant.tickers
    ADD COLUMN exchange TEXT;

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
    ('BMSB_DISCOUNT'),
--    ('SUPERTREND_BULLISH'),
--    ('SMA20_BOUNCE'),
--    ('RSI_OVERSOLD')
ON CONFLICT (name) DO NOTHING;