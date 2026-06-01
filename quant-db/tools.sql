-- get all the tickers that are above their 
-- bull market support band according to the latest bmsb screening
SELECT wi.ticker, wv.version
FROM quant.watchlist_items wi
JOIN quant.watchlist_versions wv
    ON wi.watchlist_version_id = wv.id
JOIN quant.watchlists wl
    ON wv.watchlist_id = wl.id
WHERE wl.name = 'BMSB_ABOVE'
AND wv.version = (
    SELECT MAX(version)
    FROM quant.watchlist_versions
    WHERE watchlist_id = wl.id
);