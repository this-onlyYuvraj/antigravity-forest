
/**
 * Layers API
 * Generate satellite map tiles via Python/GEE
 */
const express = require('express');
const router = express.Router();
const { spawn } = require('child_process');
const path = require('path');
const pool = require('../db/connection');

// Cache structure (Simple in-memory cache)
// Key: alertId, Value: { timestamp, data }
const layerCache = new Map();
const CACHE_DURATION = 1000 * 60 * 60 * 4; // 4 Hours (Approx GEE Token validity)

/**
 * GET /api/layers/:alertId
 */
router.get('/:alertId', async (req, res) => {
    const { alertId } = req.params;

    // Check Cache
    if (layerCache.has(alertId)) {
        const cached = layerCache.get(alertId);
        if (Date.now() - cached.timestamp < CACHE_DURATION) {
            return res.json(cached.data);
        }
    }

    try {
        // 1. Fetch alert details for location/date
        const alertQuery = `SELECT detection_date, centroid_lat, centroid_lon FROM alert_candidate WHERE id = $1`;
        const result = await pool.query(alertQuery, [alertId]);

        if (result.rows.length === 0) {
            return res.status(404).json({ error: 'Alert not found' });
        }

        const alert = result.rows[0];
        const dateStr = new Date(alert.detection_date).toISOString().split('T')[0];

        // 2. Call Python Script
        const scriptPath = path.resolve(__dirname, '../../backend-python/generate_layers.py');
        const pythonProcess = spawn('python', [
            scriptPath,
            alert.centroid_lat,
            alert.centroid_lon,
            dateStr
        ]);

        let dataString = '';
        let errorString = '';

        pythonProcess.stdout.on('data', (data) => {
            dataString += data.toString();
        });

        pythonProcess.stderr.on('data', (data) => {
            errorString += data.toString();
        });

        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                console.error(`Python script error: ${errorString}`);
                return res.status(500).json({ error: 'Layer generation failed', details: errorString });
            }

            try {
                const urls = JSON.parse(dataString);

                // Update Cache
                layerCache.set(alertId, {
                    timestamp: Date.now(),
                    data: urls
                });

                res.json(urls);
            } catch (e) {
                console.error('JSON Parse error:', e);
                res.status(500).json({ error: 'Failed to parse layer data' });
            }
        });

    } catch (error) {
        console.error('Server error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
