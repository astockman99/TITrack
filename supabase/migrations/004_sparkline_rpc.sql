-- Migration: Add get_sparkline_data RPC for 7-day daily closing prices
-- Used by TITrack Economy website for inline sparkline charts

CREATE OR REPLACE FUNCTION get_sparkline_data(p_season_id INTEGER)
RETURNS TABLE (config_base_id INTEGER, day_bucket DATE, close_price REAL)
LANGUAGE sql STABLE
AS $$
  SELECT sub.config_base_id, sub.day_bucket, sub.price_fe_median
  FROM (
    SELECT DISTINCT ON (ph.config_base_id, DATE(ph.hour_bucket))
      ph.config_base_id,
      DATE(ph.hour_bucket) AS day_bucket,
      ph.price_fe_median
    FROM price_history ph
    WHERE ph.season_id = p_season_id
      AND ph.hour_bucket >= NOW() - INTERVAL '7 days'
    ORDER BY ph.config_base_id, DATE(ph.hour_bucket), ph.hour_bucket DESC
  ) sub
  ORDER BY sub.config_base_id, sub.day_bucket;
$$;

GRANT EXECUTE ON FUNCTION get_sparkline_data(INTEGER) TO anon;
