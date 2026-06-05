-- get all the tickers that are above their
-- bull market support band according to the latest bmsb screening
-- "Latest" is defined by the most recent created_at (BR-7).
SELECT wi.ticker, wv.version
FROM quant.watchlist_items wi
JOIN quant.watchlist_versions wv
    ON wi.watchlist_version_id = wv.id
JOIN quant.watchlists wl
    ON wv.watchlist_id = wl.id
WHERE wl.name = 'BMSB_ABOVE'
  AND wv.id = (
    SELECT wv2.id
    FROM quant.watchlist_versions wv2
    JOIN quant.watchlists wl2 ON wv2.watchlist_id = wl2.id
    WHERE wl2.name = 'BMSB_ABOVE'
    ORDER BY wv2.created_at DESC, wv2.id DESC
    LIMIT 1
  );
