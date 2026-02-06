-- ============================================================================
-- Migration 002: Add RPC function for filtered price history downloads
-- ============================================================================
-- Instead of clients fetching ALL price history rows (192K+) and filtering
-- locally, this function accepts a list of item IDs and returns only their
-- history. Reduces bandwidth from ~38MB to ~1-5MB per user per sync.
-- ============================================================================

CREATE OR REPLACE FUNCTION get_price_history_for_items(
    p_season_id INTEGER,
    p_config_base_ids INTEGER[],
    p_hours INTEGER DEFAULT 72
)
RETURNS TABLE (
    config_base_id INTEGER,
    season_id INTEGER,
    hour_bucket TIMESTAMPTZ,
    price_fe_median DOUBLE PRECISION,
    price_fe_p10 DOUBLE PRECISION,
    price_fe_p90 DOUBLE PRECISION,
    submission_count INTEGER,
    unique_devices INTEGER
)
LANGUAGE sql STABLE
AS $$
    SELECT
        ph.config_base_id,
        ph.season_id,
        ph.hour_bucket,
        ph.price_fe_median,
        ph.price_fe_p10,
        ph.price_fe_p90,
        ph.submission_count,
        ph.unique_devices
    FROM price_history ph
    WHERE ph.season_id = p_season_id
    AND ph.config_base_id = ANY(p_config_base_ids)
    AND ph.hour_bucket > NOW() - (p_hours || ' hours')::INTERVAL
    ORDER BY ph.hour_bucket ASC;
$$;

-- Allow anonymous access (same as other read endpoints)
GRANT EXECUTE ON FUNCTION get_price_history_for_items(INTEGER, INTEGER[], INTEGER) TO anon;
