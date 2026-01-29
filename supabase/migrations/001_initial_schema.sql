-- TITrack Cloud Sync - Supabase Schema
-- Run this in Supabase SQL Editor (https://supabase.com/dashboard/project/YOUR_PROJECT/sql)

-- ============================================================================
-- TABLES
-- ============================================================================

-- Device registry - tracks devices for rate limiting and flagging
CREATE TABLE IF NOT EXISTS device_registry (
    device_id UUID PRIMARY KEY,
    first_seen_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submission_count INTEGER NOT NULL DEFAULT 0,
    flagged BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reason TEXT
);

-- Price submissions - raw submissions from users (7-day retention)
CREATE TABLE IF NOT EXISTS price_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES device_registry(device_id),
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    price_fe REAL NOT NULL,
    prices_array JSONB NOT NULL,
    submission_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for price_submissions
CREATE INDEX IF NOT EXISTS idx_submissions_item
    ON price_submissions(config_base_id, season_id);
CREATE INDEX IF NOT EXISTS idx_submissions_device
    ON price_submissions(device_id);
CREATE INDEX IF NOT EXISTS idx_submissions_cleanup
    ON price_submissions(created_at);
CREATE INDEX IF NOT EXISTS idx_submissions_ts
    ON price_submissions(submission_ts);

-- Aggregated prices - current median prices (computed every 5 min)
CREATE TABLE IF NOT EXISTS aggregated_prices (
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    price_fe_median REAL NOT NULL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    submission_count INTEGER NOT NULL DEFAULT 0,
    unique_devices INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (config_base_id, season_id)
);

-- Index for delta sync
CREATE INDEX IF NOT EXISTS idx_aggregated_updated
    ON aggregated_prices(updated_at);

-- Price history - hourly snapshots (permanent storage)
CREATE TABLE IF NOT EXISTS price_history (
    config_base_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    hour_bucket TIMESTAMPTZ NOT NULL,
    price_fe_median REAL NOT NULL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    submission_count INTEGER NOT NULL DEFAULT 0,
    unique_devices INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (config_base_id, season_id, hour_bucket)
);

-- Index for history queries
CREATE INDEX IF NOT EXISTS idx_history_lookup
    ON price_history(season_id, hour_bucket);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function: Submit a price observation
-- Rate limited to 100 submissions per device per hour
CREATE OR REPLACE FUNCTION submit_price(
    p_device_id UUID,
    p_config_base_id INTEGER,
    p_season_id INTEGER,
    p_price_fe REAL,
    p_prices_array JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_recent_count INTEGER;
    v_is_flagged BOOLEAN;
BEGIN
    -- Upsert device registry
    INSERT INTO device_registry (device_id, first_seen_ts, last_seen_ts, submission_count)
    VALUES (p_device_id, NOW(), NOW(), 1)
    ON CONFLICT (device_id) DO UPDATE SET
        last_seen_ts = NOW(),
        submission_count = device_registry.submission_count + 1;

    -- Check if device is flagged
    SELECT flagged INTO v_is_flagged
    FROM device_registry
    WHERE device_id = p_device_id;

    IF v_is_flagged THEN
        RETURN jsonb_build_object('success', false, 'error', 'device_flagged');
    END IF;

    -- Check rate limit (100 per hour)
    SELECT COUNT(*) INTO v_recent_count
    FROM price_submissions
    WHERE device_id = p_device_id
      AND created_at > NOW() - INTERVAL '1 hour';

    IF v_recent_count >= 100 THEN
        RETURN jsonb_build_object('success', false, 'error', 'rate_limited', 'rate_limited', true);
    END IF;

    -- Insert submission
    INSERT INTO price_submissions (
        device_id, config_base_id, season_id, price_fe, prices_array, submission_ts
    ) VALUES (
        p_device_id, p_config_base_id, p_season_id, p_price_fe, p_prices_array, NOW()
    );

    RETURN jsonb_build_object('success', true);
END;
$$;

-- Function: Aggregate prices from submissions
-- Computes median from last 24h, requires 3+ unique devices
CREATE OR REPLACE FUNCTION aggregate_prices()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_updated_count INTEGER := 0;
    v_item RECORD;
BEGIN
    -- Process each unique item/season combo from recent submissions
    FOR v_item IN
        SELECT DISTINCT config_base_id, season_id
        FROM price_submissions
        WHERE submission_ts > NOW() - INTERVAL '24 hours'
    LOOP
        -- Only aggregate if we have 3+ unique devices
        IF (
            SELECT COUNT(DISTINCT ps.device_id)
            FROM price_submissions ps
            JOIN device_registry dr ON ps.device_id = dr.device_id
            WHERE ps.config_base_id = v_item.config_base_id
              AND ps.season_id = v_item.season_id
              AND ps.submission_ts > NOW() - INTERVAL '24 hours'
              AND dr.flagged = FALSE
        ) >= 3 THEN
            -- Upsert aggregated price
            INSERT INTO aggregated_prices (
                config_base_id, season_id,
                price_fe_median, price_fe_p10, price_fe_p90,
                submission_count, unique_devices, updated_at
            )
            SELECT
                v_item.config_base_id,
                v_item.season_id,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_fe) AS median,
                PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY price_fe) AS p10,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY price_fe) AS p90,
                COUNT(*) AS submission_count,
                COUNT(DISTINCT ps.device_id) AS unique_devices,
                NOW()
            FROM price_submissions ps
            JOIN device_registry dr ON ps.device_id = dr.device_id
            WHERE ps.config_base_id = v_item.config_base_id
              AND ps.season_id = v_item.season_id
              AND ps.submission_ts > NOW() - INTERVAL '24 hours'
              AND dr.flagged = FALSE
            ON CONFLICT (config_base_id, season_id) DO UPDATE SET
                price_fe_median = EXCLUDED.price_fe_median,
                price_fe_p10 = EXCLUDED.price_fe_p10,
                price_fe_p90 = EXCLUDED.price_fe_p90,
                submission_count = EXCLUDED.submission_count,
                unique_devices = EXCLUDED.unique_devices,
                updated_at = NOW();

            v_updated_count := v_updated_count + 1;
        END IF;
    END LOOP;

    RETURN v_updated_count;
END;
$$;

-- Function: Snapshot current prices to history
-- Should run hourly
CREATE OR REPLACE FUNCTION snapshot_price_history()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_hour_bucket TIMESTAMPTZ;
    v_inserted INTEGER;
BEGIN
    -- Round to current hour
    v_hour_bucket := DATE_TRUNC('hour', NOW());

    -- Insert current aggregated prices into history
    INSERT INTO price_history (
        config_base_id, season_id, hour_bucket,
        price_fe_median, price_fe_p10, price_fe_p90,
        submission_count, unique_devices
    )
    SELECT
        config_base_id, season_id, v_hour_bucket,
        price_fe_median, price_fe_p10, price_fe_p90,
        submission_count, unique_devices
    FROM aggregated_prices
    ON CONFLICT (config_base_id, season_id, hour_bucket) DO UPDATE SET
        price_fe_median = EXCLUDED.price_fe_median,
        price_fe_p10 = EXCLUDED.price_fe_p10,
        price_fe_p90 = EXCLUDED.price_fe_p90,
        submission_count = EXCLUDED.submission_count,
        unique_devices = EXCLUDED.unique_devices;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RETURN v_inserted;
END;
$$;

-- Function: Clean up old submissions (>7 days)
CREATE OR REPLACE FUNCTION cleanup_old_submissions()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM price_submissions
    WHERE created_at < NOW() - INTERVAL '7 days';

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE device_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE aggregated_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;

-- Device registry: No direct access (service role only)
-- (No policies = no access for anon/authenticated)

-- Price submissions: No direct access (use RPC only)
-- (No policies = no access for anon/authenticated)

-- Aggregated prices: Public read
CREATE POLICY "Public read access for aggregated_prices"
    ON aggregated_prices
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Price history: Public read
CREATE POLICY "Public read access for price_history"
    ON price_history
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- ============================================================================
-- GRANTS
-- ============================================================================

-- Grant execute on RPC functions to anon (for unauthenticated clients)
GRANT EXECUTE ON FUNCTION submit_price TO anon;
GRANT EXECUTE ON FUNCTION submit_price TO authenticated;

-- Note: aggregate_prices, snapshot_price_history, cleanup_old_submissions
-- should only be called by scheduled jobs (pg_cron) or service role

-- ============================================================================
-- SCHEDULED JOBS (pg_cron)
-- ============================================================================
-- Note: pg_cron must be enabled in your Supabase project settings
-- Go to Database > Extensions and enable pg_cron

-- Run aggregation every 5 minutes
SELECT cron.schedule(
    'aggregate-prices',
    '*/5 * * * *',
    $$SELECT aggregate_prices()$$
);

-- Run history snapshot every hour
SELECT cron.schedule(
    'snapshot-price-history',
    '0 * * * *',
    $$SELECT snapshot_price_history()$$
);

-- Run cleanup daily at 3 AM UTC
SELECT cron.schedule(
    'cleanup-old-submissions',
    '0 3 * * *',
    $$SELECT cleanup_old_submissions()$$
);

-- ============================================================================
-- VERIFICATION QUERIES (run these to verify setup)
-- ============================================================================
-- SELECT * FROM cron.job;  -- View scheduled jobs
-- SELECT aggregate_prices();  -- Test aggregation (should return 0 initially)
-- SELECT snapshot_price_history();  -- Test history snapshot
