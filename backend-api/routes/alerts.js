/**
 * Alert Management Endpoints
 */

const express = require('express');
const router = express.Router();
const pool = require('../db/connection');

/**
 * GET /api/alerts
 * Retrieve all alerts with optional filtering
 */
router.get('/', async (req, res) => {
    try {
        const { status, risk_tier, limit = 100, offset = 0 } = req.query;

        let query = `
      SELECT 
        a.id,
        a.detection_date,
        a.confidence_score,
        a.area_hectares,
        a.centroid_lat,
        a.centroid_lon,
        a.risk_tier,
        a.status,
        COALESCE(a.alt_vv_drop_db, 0) as alt_vv_drop_db,
        COALESCE(a.alt_vh_drop_db, 0) as alt_vh_drop_db,
        a.optical_score,
        a.combined_score,
        a.ndvi_drop,
        fb.name as boundary_name,
        fb.boundary_type,
        fb.name as boundary_name,
        fb.boundary_type,
        ST_AsGeoJSON(a.geom) as geojson
      FROM alert_candidate a
      LEFT JOIN forest_boundaries fb ON a.boundary_id = fb.id
      WHERE 1=1
    `;

        const params = [];
        let paramCount = 1;

        if (status) {
            query += ` AND a.status = $${paramCount++}`;
            params.push(status);
        }

        if (risk_tier) {
            query += ` AND a.risk_tier = $${paramCount++}`;
            params.push(risk_tier);
        }

        query += ` ORDER BY a.detection_date DESC LIMIT $${paramCount++} OFFSET $${paramCount++}`;
        params.push(parseInt(limit), parseInt(offset));

        const result = await pool.query(query, params);

        // Format response as GeoJSON FeatureCollection
        const features = result.rows.map(row => ({
            type: 'Feature',
            id: row.id,
            properties: {
                id: row.id,
                detection_date: row.detection_date,
                confidence_score: parseFloat(row.confidence_score),
                area_hectares: parseFloat(row.area_hectares),
                risk_tier: row.risk_tier,
                status: row.status,
                alt_vv_drop_db: parseFloat(row.alt_vv_drop_db),
                alt_vh_drop_db: parseFloat(row.alt_vh_drop_db),
                optical_score: row.optical_score ? parseFloat(row.optical_score) : null,
                combined_score: row.combined_score ? parseFloat(row.combined_score) : null,
                ndvi_drop: row.ndvi_drop ? parseFloat(row.ndvi_drop) : null,
                boundary_name: row.boundary_name,
                boundary_type: row.boundary_type,
                centroid: [parseFloat(row.centroid_lon), parseFloat(row.centroid_lat)]
            },
            geometry: row.geojson ? JSON.parse(row.geojson) : null
        }));

        res.json({
            type: 'FeatureCollection',
            features,
            metadata: {
                total: features.length,
                limit: parseInt(limit),
                offset: parseInt(offset)
            }
        });

    } catch (error) {
        console.error('Error fetching alerts:', error);
        console.error('Error stack:', error.stack);
        res.status(500).json({
            error: 'Failed to fetch alerts',
            message: error.message,
            details: process.env.NODE_ENV === 'development' ? error.stack : undefined
        });
    }
});

/**
 * GET /api/alerts/stats
 * Get dashboard statistics
 */
router.get('/stats', async (req, res) => {
    try {
        // Calculate stats directly from alert_candidate table
        const statsQuery = `
      SELECT 
        COUNT(*) as total_alerts,
        COUNT(*) FILTER (WHERE risk_tier = 'TIER_2') as tier2_alerts,
        COUNT(*) FILTER (WHERE status = 'VERIFIED') as verified_alerts,
        COUNT(*) FILTER (WHERE status = 'FALSE_POSITIVE') as false_positives,
        COALESCE(SUM(area_hectares), 0) as total_area_hectares,
        COUNT(*) FILTER (WHERE detection_date >= CURRENT_DATE - INTERVAL '7 days') as alerts_last_7_days,
        COUNT(*) FILTER (WHERE detection_date >= CURRENT_DATE - INTERVAL '30 days') as alerts_last_30_days
      FROM alert_candidate
    `;

        const result = await pool.query(statsQuery);
        const stats = result.rows[0];

        // Convert to numbers
        res.json({
            total_alerts: parseInt(stats.total_alerts) || 0,
            tier2_alerts: parseInt(stats.tier2_alerts) || 0,
            verified_alerts: parseInt(stats.verified_alerts) || 0,
            false_positives: parseInt(stats.false_positives) || 0,
            total_area_hectares: parseFloat(stats.total_area_hectares) || 0,
            alerts_last_7_days: parseInt(stats.alerts_last_7_days) || 0,
            alerts_last_30_days: parseInt(stats.alerts_last_30_days) || 0
        });
    } catch (error) {
        console.error('Error fetching stats:', error);
        res.status(500).json({ error: 'Failed to fetch statistics', details: error.message });
    }
});

/**
 * GET /api/alerts/:id
 * Get specific alert details
 */
router.get('/:id', async (req, res) => {
    try {
        const { id } = req.params;

        const query = `
      SELECT 
        a.*,
        fb.name as boundary_name,
        fb.boundary_type,
        fb.official_code,
        ST_AsGeoJSON(a.geom) as geojson
      FROM alert_candidate a
      LEFT JOIN forest_boundaries fb ON a.boundary_id = fb.id
      WHERE a.id = $1
    `;

        const result = await pool.query(query, [id]);

        if (result.rows.length === 0) {
            return res.status(404).json({ error: 'Alert not found' });
        }

        const alert = result.rows[0];
        alert.geom = JSON.parse(alert.geojson);
        delete alert.geojson;

        res.json(alert);

    } catch (error) {
        console.error('Error fetching alert:', error);
        res.status(500).json({ error: 'Failed to fetch alert' });
    }
});

/**
 * PUT /api/alerts/:id/status
 * Update alert status (verified, false_positive, etc.)
 */
router.put('/:id/status', async (req, res) => {
    try {
        const { id } = req.params;
        const { status, notes, verified_by } = req.body;

        const validStatuses = ['PENDING', 'VERIFIED', 'FALSE_POSITIVE', 'INVESTIGATING'];

        if (!validStatuses.includes(status)) {
            return res.status(400).json({ error: 'Invalid status' });
        }

        const query = `
      UPDATE alert_candidate
      SET status = $1,
          verification_notes = $2,
          verified_by = $3,
          verification_date = CURRENT_TIMESTAMP,
          updated_at = CURRENT_TIMESTAMP
      WHERE id = $4
      RETURNING *
    `;

        const result = await pool.query(query, [status, notes || null, verified_by || null, id]);

        if (result.rows.length === 0) {
            return res.status(404).json({ error: 'Alert not found' });
        }

        res.json({
            message: 'Alert status updated successfully',
            alert: result.rows[0]
        });

    } catch (error) {
        console.error('Error updating alert:', error);
        res.status(500).json({ error: 'Failed to update alert' });
    }
});

module.exports = router;
