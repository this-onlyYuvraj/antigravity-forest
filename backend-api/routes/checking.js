/**
 * Checking / Demo Mode Endpoints
 */

const express = require('express');
const router = express.Router();
const pool = require('../db/connection');
const { spawn } = require('child_process');
const path = require('path');

/**
 * POST /api/checking/run
 * Trigger the historical demo pipeline
 */
router.post('/run', async (req, res) => {
    try {
        const targetDate = '2023-08-26';

        // Spawn Python process
        const pythonScript = path.join(__dirname, '../../backend-python/pipeline_demo.py');
        const pythonProcess = spawn('python', [pythonScript, '--date', targetDate], {
            cwd: path.join(__dirname, '../../backend-python')
        });

        // We do not wait for the process to finish for the response
        // But for a demo, maybe we should? The user requirements say "Returns execution status"
        // It's better to return "Running" and let the frontend poll or wait?
        // Requirement 5: "Does not require user input ... Returns execution status"
        // Since it might take a minute, let's return immediate success and let frontend poll.

        // However, for simplicity and since it's a "Run Button -> Disabled while running -> Results",
        // we can try streaming or just fire and forget. 
        // Best approach for "Run Button": Fire request, get "Job Started", then Frontend polls status.
        // But we don't have a job queue.
        // So we will just trust the process runs.

        pythonProcess.stdout.on('data', (data) => {
            console.log(`[DEMO] ${data}`);
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error(`[DEMO ERR] ${data}`);
        });

        res.json({ status: 'started', message: 'Demo pipeline triggered', target_date: targetDate });

    } catch (error) {
        console.error('Failed to trigger demo:', error);
        res.status(500).json({ error: 'Failed to start demo pipeline' });
    }
});

/**
 * GET /api/checking/alerts
 * Retrieve only demo alerts
 */
router.get('/alerts', async (req, res) => {
    try {
        const query = `
      SELECT 
        a.id,
        a.detection_date,
        a.confidence_score,
        a.area_hectares,
        a.risk_tier,
        a.status,
        a.alt_vv_drop_db,
        a.optical_score,
        a.combined_score,
        a.ndvi_drop,
        fb.name as boundary_name,
        ST_AsGeoJSON(a.geom) as geojson
      FROM alert_candidate a
      LEFT JOIN forest_boundaries fb ON a.boundary_id = fb.id
      WHERE a.is_demo = TRUE
      ORDER BY a.detection_date DESC
    `;

        const result = await pool.query(query);

        const features = result.rows.map(row => ({
            type: 'Feature',
            id: row.id,
            properties: {
                ...row,
                confidence_score: parseFloat(row.confidence_score),
                area_hectares: parseFloat(row.area_hectares)
            },
            geometry: JSON.parse(row.geojson)
        }));

        res.json({
            type: 'FeatureCollection',
            features,
            metadata: {
                total: features.length,
                is_demo: true
            }
        });

    } catch (error) {
        console.error('Error fetching demo alerts:', error);
        res.status(500).json({ error: 'Failed to fetch demo alerts' });
    }
});

module.exports = router;
