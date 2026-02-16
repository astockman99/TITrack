-- ============================================================
-- 003_economy_website_rpcs.sql
-- RPCs for the TITrack Economy read-only website (TINinja)
-- ============================================================

-- 1. get_economy_overview(p_season_id)
--    Returns all items with current price + 24h/7d % changes.
CREATE OR REPLACE FUNCTION get_economy_overview(p_season_id INTEGER)
RETURNS TABLE (
    config_base_id INTEGER,
    price_fe_median REAL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    unique_devices INTEGER,
    submission_count INTEGER,
    updated_at TIMESTAMPTZ,
    change_24h REAL,
    change_7d REAL
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.config_base_id,
        a.price_fe_median,
        a.price_fe_p10,
        a.price_fe_p90,
        a.unique_devices,
        a.submission_count,
        a.updated_at,
        CASE
            WHEN h24.price_fe_median IS NOT NULL AND h24.price_fe_median > 0
            THEN ((a.price_fe_median - h24.price_fe_median) / h24.price_fe_median * 100)::REAL
            ELSE NULL
        END AS change_24h,
        CASE
            WHEN h7d.price_fe_median IS NOT NULL AND h7d.price_fe_median > 0
            THEN ((a.price_fe_median - h7d.price_fe_median) / h7d.price_fe_median * 100)::REAL
            ELSE NULL
        END AS change_7d
    FROM aggregated_prices a
    LEFT JOIN LATERAL (
        SELECT ph.price_fe_median
        FROM price_history ph
        WHERE ph.config_base_id = a.config_base_id
          AND ph.season_id = p_season_id
          AND ph.hour_bucket <= NOW() - INTERVAL '23 hours'
        ORDER BY ph.hour_bucket DESC
        LIMIT 1
    ) h24 ON TRUE
    LEFT JOIN LATERAL (
        SELECT ph.price_fe_median
        FROM price_history ph
        WHERE ph.config_base_id = a.config_base_id
          AND ph.season_id = p_season_id
          AND ph.hour_bucket <= NOW() - INTERVAL '6 days 23 hours'
        ORDER BY ph.hour_bucket DESC
        LIMIT 1
    ) h7d ON TRUE
    WHERE a.season_id = p_season_id;
END;
$$;

-- 2. get_item_full_history(p_config_base_id, p_season_id, p_hours?)
--    Returns hourly price history for one item.
CREATE OR REPLACE FUNCTION get_item_full_history(
    p_config_base_id INTEGER,
    p_season_id INTEGER,
    p_hours INTEGER DEFAULT NULL
)
RETURNS TABLE (
    hour_bucket TIMESTAMPTZ,
    price_fe_median REAL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    submission_count INTEGER,
    unique_devices INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ph.hour_bucket,
        ph.price_fe_median,
        ph.price_fe_p10,
        ph.price_fe_p90,
        ph.submission_count,
        ph.unique_devices
    FROM price_history ph
    WHERE ph.config_base_id = p_config_base_id
      AND ph.season_id = p_season_id
      AND (p_hours IS NULL OR ph.hour_bucket >= NOW() - (p_hours || ' hours')::INTERVAL)
    ORDER BY ph.hour_bucket ASC;
END;
$$;

-- 3. get_available_seasons()
--    Returns seasons that have price data.
CREATE OR REPLACE FUNCTION get_available_seasons()
RETURNS TABLE (
    season_id INTEGER,
    item_count BIGINT,
    latest_update TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.season_id,
        COUNT(*)::BIGINT AS item_count,
        MAX(a.updated_at) AS latest_update
    FROM aggregated_prices a
    GROUP BY a.season_id
    ORDER BY a.season_id DESC;
END;
$$;

-- Grant execute to anon role (public read-only access)
GRANT EXECUTE ON FUNCTION get_economy_overview(INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_item_full_history(INTEGER, INTEGER, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_available_seasons() TO anon;
