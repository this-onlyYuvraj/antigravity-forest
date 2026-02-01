-- Seed Data for Deforestation Monitoring System
-- Novo Progresso, Pará, Brazil - IBGE Code: 1505304

-- ============================================================================
-- 1. Insert Novo Progresso Municipal Boundary
-- ============================================================================

-- Note: The actual geometry will be fetched from IBGE API by the backend script
-- This is a placeholder rectangle approximating Novo Progresso's extent
-- Real boundary will be loaded via: backend-python/scripts/load_novo_progresso.py

INSERT INTO forest_boundaries (
    name,
    boundary_type,
    official_code,
    description,
    risk_tier,
    state,
    geom
) VALUES (
    'Novo Progresso',
    'MUNICIPALITY',
    '1505304',
    'Municipality of Novo Progresso, Pará, Brazil. Critical frontier within the deforestation arch, known for rapid clear-cut activities driven by cattle industry.',
    'TIER_1', -- Standard tier for municipal boundary; specific protected areas within will be TIER_2
    'PA',
    ST_GeomFromText(
        'MULTIPOLYGON(((-55.5 -7.3, -55.5 -6.8, -54.8 -6.8, -54.8 -7.3, -55.5 -7.3)))',
        4326
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- 2. Sample Protected Areas (Example - replace with real data)
-- ============================================================================

-- Example: Jamanxim National Forest (real protected area near Novo Progresso)
INSERT INTO forest_boundaries (
    name,
    boundary_type,
    official_code,
    description,
    risk_tier,
    state,
    geom
) VALUES (
    'Floresta Nacional do Jamanxim',
    'CONSERVATION_UNIT',
    'UC_JAMANXIM',
    'Jamanxim National Forest - Federal conservation unit under pressure from illegal deforestation',
    'TIER_2', -- Priority tier for protected areas
    'PA',
    ST_GeomFromText(
        'MULTIPOLYGON(((-55.4 -7.0, -55.4 -6.9, -55.2 -6.9, -55.2 -7.0, -55.4 -7.0)))',
        4326
    )
) ON CONFLICT DO NOTHING;

-- Example: Indigenous Territory (mock data - replace with official FUNAI boundaries)
INSERT INTO forest_boundaries (
    name,
    boundary_type,
    official_code,
    description,
    risk_tier,
    state,
    geom
) VALUES (
    'Terra Indígena Baú',
    'INDIGENOUS_TERRITORY',
    'TI_BAU',
    'Baú Indigenous Territory - Kayapó people',
    'TIER_2', -- Priority tier for Indigenous lands
    'PA',
    ST_GeomFromText(
        'MULTIPOLYGON(((-55.3 -7.1, -55.3 -7.0, -55.1 -7.0, -55.1 -7.1, -55.3 -7.1)))',
        4326
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- 3. Sample Baseline Backscatter Time Series
-- ============================================================================

-- Generate synthetic historical baseline for testing
-- Real data will be populated by the GEE pipeline

DO $$
DECLARE
    grid_id VARCHAR(100);
    obs_date DATE;
    lat NUMERIC;
    lon NUMERIC;
BEGIN
    -- Create sample grid cells in Novo Progresso area
    FOR lat IN SELECT generate_series(-7.2, -6.9, 0.02) LOOP
        FOR lon IN SELECT generate_series(-55.4, -55.0, 0.02) LOOP
            grid_id := 'grid_' || REPLACE(lat::TEXT, '.', '_') || '_' || REPLACE(lon::TEXT, '.', '_');
            
            -- Generate 30 historical observations (simulating 6-day repeat cycle over ~6 months)
            FOR obs_date IN SELECT generate_series(
                CURRENT_DATE - INTERVAL '180 days',
                CURRENT_DATE - INTERVAL '6 days',
                INTERVAL '6 days'
            )::DATE LOOP
                INSERT INTO backscatter_timeseries (
                    grid_cell_id,
                    observation_date,
                    vv_mean,
                    vv_std,
                    vv_mmd,
                    vv_median,
                    vh_mean,
                    vh_std,
                    vh_mmd,
                    vh_median,
                    pixel_count,
                    source_image_id,
                    geom
                ) VALUES (
                    grid_id,
                    obs_date,
                    -- Stable forest backscatter: VV ~ -10 to -12 dB (in linear: ~0.1)
                    0.095 + (random() * 0.02),
                    0.015 + (random() * 0.005),
                    0.008 + (random() * 0.003),
                    0.093 + (random() * 0.02),
                    -- VH ~ -17 to -19 dB (in linear: ~0.015)
                    0.014 + (random() * 0.004),
                    0.003 + (random() * 0.001),
                    0.002 + (random() * 0.001),
                    0.013 + (random() * 0.004),
                    100,
                    'SYNTHETIC_BASELINE_' || obs_date::TEXT,
                    ST_SetSRID(ST_MakePoint(lon, lat), 4326)
                ) ON CONFLICT (grid_cell_id, observation_date, source_image_id) DO NOTHING;
            END LOOP;
        END LOOP;
    END LOOP;
END $$;

-- ============================================================================
-- 4. Sample Alert (for UI testing)
-- ============================================================================

-- Insert a sample historical alert
INSERT INTO alert_candidate (
    detection_date,
    confidence_score,
    area_hectares,
    risk_tier,
    status,
    alt_vv_drop_db,
    alt_vh_drop_db,
    source_image_id,
    notification_sent,
    geom
) VALUES (
    CURRENT_TIMESTAMP - INTERVAL '2 days',
    0.92,
    1.8,
    'TIER_1',
    'PENDING',
    -2.1,
    -2.4,
    'SAMPLE_IMAGE_001',
    FALSE,
    ST_GeomFromText('POLYGON((-55.25 -7.05, -55.25 -7.04, -55.24 -7.04, -55.24 -7.05, -55.25 -7.05))', 4326)
);

-- Insert a high-priority alert in protected area
INSERT INTO alert_candidate (
    detection_date,
    confidence_score,
    area_hectares,
    risk_tier,
    boundary_id,
    status,
    alt_vv_drop_db,
    alt_vh_drop_db,
    source_image_id,
    notification_sent,
    geom
) VALUES (
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    0.88,
    2.3,
    'TIER_2',
    (SELECT id FROM forest_boundaries WHERE official_code = 'TI_BAU' LIMIT 1),
    'PENDING',
    -2.3,
    -2.6,
    'SAMPLE_IMAGE_002',
    TRUE,
    ST_GeomFromText('POLYGON((-55.22 -7.08, -55.22 -7.07, -55.21 -7.07, -55.21 -7.08, -55.22 -7.08))', 4326)
);

-- ============================================================================
-- 5. Verify Data Loading
-- ============================================================================

SELECT 'Seed data loaded successfully' AS status;
SELECT COUNT(*) AS boundary_count FROM forest_boundaries;
SELECT COUNT(*) AS timeseries_count FROM backscatter_timeseries;
SELECT COUNT(*) AS alert_count FROM alert_candidate;
