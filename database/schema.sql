-- Deforestation Monitoring System - Database Schema
-- PostgreSQL 15+ with PostGIS Extension

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Drop existing tables if re-running
DROP TABLE IF EXISTS backscatter_timeseries CASCADE;
DROP TABLE IF EXISTS alert_candidate CASCADE;
DROP TABLE IF EXISTS forest_boundaries CASCADE;
DROP TABLE IF EXISTS processed_images CASCADE;

-- ============================================================================
-- 1. Forest Boundaries Table
-- Stores official shapefiles (Indigenous Territories, Conservation Units, Municipal Boundaries)
-- ============================================================================

CREATE TABLE forest_boundaries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    boundary_type VARCHAR(50) NOT NULL, -- 'MUNICIPALITY', 'INDIGENOUS_TERRITORY', 'CONSERVATION_UNIT'
    official_code VARCHAR(50), -- IBGE code for municipalities, official registry for protected areas
    description TEXT,
    risk_tier VARCHAR(20) NOT NULL DEFAULT 'TIER_1', -- 'TIER_1' (Standard) or 'TIER_2' (Priority/Protected)
    area_hectares NUMERIC(12, 2),
    state VARCHAR(2), -- Brazilian state code (e.g., 'PA' for Pará)
    geom GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index for fast intersection queries
CREATE INDEX idx_forest_boundaries_geom ON forest_boundaries USING GIST(geom);
CREATE INDEX idx_forest_boundaries_type ON forest_boundaries(boundary_type);
CREATE INDEX idx_forest_boundaries_tier ON forest_boundaries(risk_tier);

-- ============================================================================
-- 2. Processed Images Table
-- Tracks which Sentinel-1 tiles have been analyzed to prevent reprocessing
-- ============================================================================

CREATE TABLE processed_images (
    id SERIAL PRIMARY KEY,
    image_id VARCHAR(255) UNIQUE NOT NULL, -- GEE image ID (e.g., 'COPERNICUS/S1_GRD/S1A_IW_GRDH_...')
    acquisition_date TIMESTAMP NOT NULL,
    processing_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    polarization VARCHAR(20), -- 'VV', 'VH', 'VV+VH'
    orbit_direction VARCHAR(20), -- 'ASCENDING' or 'DESCENDING'
    platform VARCHAR(20), -- 'Sentinel-1A' or 'Sentinel-1B'
    status VARCHAR(50) DEFAULT 'COMPLETED', -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    error_message TEXT,
    num_alerts_generated INTEGER DEFAULT 0,
    processing_time_seconds INTEGER,
    geom GEOMETRY(MULTIPOLYGON, 4326) -- Footprint of the processed image
);

CREATE INDEX idx_processed_images_date ON processed_images(acquisition_date DESC);
CREATE INDEX idx_processed_images_status ON processed_images(status);
CREATE INDEX idx_processed_images_geom ON processed_images USING GIST(geom);

-- ============================================================================
-- 3. Alert Candidate Table
-- Stores vectorized alert polygons with confidence scores and risk classifications
-- ============================================================================

CREATE TABLE alert_candidate (
    id SERIAL PRIMARY KEY,
    detection_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confidence_score NUMERIC(5, 4) NOT NULL, -- MLP output probability (0.0000 to 1.0000)
    area_hectares NUMERIC(10, 4) NOT NULL,
    centroid_lat NUMERIC(10, 7),
    centroid_lon NUMERIC(10, 7),
    risk_tier VARCHAR(20) NOT NULL DEFAULT 'TIER_1', -- 'TIER_1' or 'TIER_2'
    boundary_id INTEGER REFERENCES forest_boundaries(id), -- Foreign key to intersecting boundary
    status VARCHAR(50) DEFAULT 'PENDING', -- 'PENDING', 'VERIFIED', 'FALSE_POSITIVE', 'INVESTIGATING'
    verified_by VARCHAR(100),
    verification_date TIMESTAMP,
    verification_notes TEXT,
    
    -- Detection algorithm metadata
    alt_vv_drop_db NUMERIC(5, 2), -- VV backscatter drop in dB
    alt_vh_drop_db NUMERIC(5, 2), -- VH backscatter drop in dB
    source_image_id VARCHAR(255) REFERENCES processed_images(image_id),
    
    -- Optical Validation (Sentinel-2)
    optical_score NUMERIC(5, 4), -- 0.0 to 1.0 (1.0 = High Confidence Deforestation)
    combined_score NUMERIC(5, 4), -- Weighted confidence
    ndvi_drop NUMERIC(5, 4), -- Pre-Post NDVI difference
    
    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_date TIMESTAMP,
    notification_type VARCHAR(50), -- 'SMS', 'EMAIL', 'PUSH'
    
    -- Spatial data
    geom GEOMETRY(POLYGON, 4326) NOT NULL,

    -- Demo Mode Flags
    is_demo BOOLEAN DEFAULT FALSE,
    demo_date DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spatial index for map rendering and boundary intersection
CREATE INDEX idx_alert_candidate_geom ON alert_candidate USING GIST(geom);
CREATE INDEX idx_alert_candidate_date ON alert_candidate(detection_date DESC);
CREATE INDEX idx_alert_candidate_status ON alert_candidate(status);
CREATE INDEX idx_alert_candidate_tier ON alert_candidate(risk_tier);
CREATE INDEX idx_alert_candidate_confidence ON alert_candidate(confidence_score DESC);
CREATE INDEX idx_alert_candidate_is_demo ON alert_candidate(is_demo);

-- ============================================================================
-- 4. Backscatter Time Series Table
-- Stores aggregated statistical features (Mean, SD, MMD) per grid cell for profile charting
-- ============================================================================

CREATE TABLE backscatter_timeseries (
    id SERIAL PRIMARY KEY,
    grid_cell_id VARCHAR(100) NOT NULL, -- Unique identifier for 2-ha grid cell (e.g., 'lat_lon_hash')
    observation_date DATE NOT NULL,
    
    -- VV Polarization Statistics
    vv_mean NUMERIC(10, 6), -- Mean backscatter in linear units (not dB)
    vv_std NUMERIC(10, 6), -- Standard deviation
    vv_mmd NUMERIC(10, 6), -- Mean Median Difference
    vv_median NUMERIC(10, 6),
    vv_min NUMERIC(10, 6),
    vv_max NUMERIC(10, 6),
    
    -- VH Polarization Statistics
    vh_mean NUMERIC(10, 6),
    vh_std NUMERIC(10, 6),
    vh_mmd NUMERIC(10, 6),
    vh_median NUMERIC(10, 6),
    vh_min NUMERIC(10, 6),
    vh_max NUMERIC(10, 6),
    
    -- Metadata
    pixel_count INTEGER, -- Number of valid pixels in aggregation
    source_image_id VARCHAR(255) REFERENCES processed_images(image_id),
    
    -- Spatial reference (centroid of grid cell)
    geom GEOMETRY(POINT, 4326),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Composite index for time-series queries
CREATE INDEX idx_backscatter_grid_date ON backscatter_timeseries(grid_cell_id, observation_date DESC);
CREATE INDEX idx_backscatter_date ON backscatter_timeseries(observation_date DESC);
CREATE INDEX idx_backscatter_geom ON backscatter_timeseries USING GIST(geom);

-- Unique constraint to prevent duplicate observations
CREATE UNIQUE INDEX idx_backscatter_unique ON backscatter_timeseries(grid_cell_id, observation_date, source_image_id);

-- ============================================================================
-- Helper Views
-- ============================================================================

-- View: Active high-priority alerts
CREATE OR REPLACE VIEW active_priority_alerts AS
SELECT 
    a.*,
    fb.name AS boundary_name,
    fb.boundary_type,
    ST_AsGeoJSON(a.geom) AS geojson
FROM alert_candidate a
LEFT JOIN forest_boundaries fb ON a.boundary_id = fb.id
WHERE a.status IN ('PENDING', 'INVESTIGATING')
  AND a.risk_tier = 'TIER_2'
ORDER BY a.detection_date DESC;

-- View: Dashboard statistics
CREATE OR REPLACE VIEW alert_statistics AS
SELECT 
    COUNT(*) AS total_alerts,
    COUNT(*) FILTER (WHERE risk_tier = 'TIER_2') AS tier2_alerts,
    COUNT(*) FILTER (WHERE status = 'VERIFIED') AS verified_alerts,
    COUNT(*) FILTER (WHERE status = 'FALSE_POSITIVE') AS false_positives,
    COALESCE(SUM(area_hectares), 0) AS total_area_hectares,
    COUNT(*) FILTER (WHERE detection_date >= CURRENT_DATE - INTERVAL '7 days') AS alerts_last_7_days,
    COUNT(*) FILTER (WHERE detection_date >= CURRENT_DATE - INTERVAL '30 days') AS alerts_last_30_days
FROM alert_candidate;

-- ============================================================================
-- Functions
-- ============================================================================

-- Function: Update timestamp on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Auto-update updated_at for forest_boundaries
CREATE TRIGGER update_forest_boundaries_updated_at
BEFORE UPDATE ON forest_boundaries
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Trigger: Auto-update updated_at for alert_candidate
CREATE TRIGGER update_alert_candidate_updated_at
BEFORE UPDATE ON alert_candidate
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Function: Calculate centroid coordinates on insert/update
CREATE OR REPLACE FUNCTION update_alert_centroid()
RETURNS TRIGGER AS $$
BEGIN
    NEW.centroid_lon = ST_X(ST_Centroid(NEW.geom));
    NEW.centroid_lat = ST_Y(ST_Centroid(NEW.geom));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Auto-calculate centroid for alerts
CREATE TRIGGER calculate_alert_centroid
BEFORE INSERT OR UPDATE ON alert_candidate
FOR EACH ROW
EXECUTE FUNCTION update_alert_centroid();

-- ============================================================================
-- Grants (assuming postgres user has appropriate permissions)
-- ============================================================================

-- Grant permissions to application user (create this user in production)
-- CREATE USER deforestation_app WITH PASSWORD 'secure_password';
-- GRANT CONNECT ON DATABASE deforestation_db TO deforestation_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO deforestation_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO deforestation_app;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE forest_boundaries IS 'Official boundaries for spatial classification of alerts';
COMMENT ON TABLE processed_images IS 'Tracking table for Sentinel-1 image processing status';
COMMENT ON TABLE alert_candidate IS 'Detected deforestation alerts with validation status';
COMMENT ON TABLE backscatter_timeseries IS 'Historical SAR backscatter statistics for profile charting';

COMMENT ON COLUMN forest_boundaries.risk_tier IS 'TIER_2 for protected areas (Indigenous Territories, Conservation Units), TIER_1 for standard areas';
COMMENT ON COLUMN alert_candidate.confidence_score IS 'MLP model output probability (threshold: 0.85)';
COMMENT ON COLUMN alert_candidate.status IS 'Alert lifecycle: PENDING -> VERIFIED/FALSE\_POSITIVE';

-- Schema creation complete
SELECT 'Database schema initialized successfully' AS status;
