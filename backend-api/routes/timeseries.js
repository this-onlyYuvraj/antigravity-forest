/**
 * Time Series Data Endpoints
 */

const express = require('express');
const router = express.Router();
const pool = require('../db/connection');

/**
 * GET /api/timeseries/:gridId
 * Get backscatter time series for a specific grid cell
 */
router.get('/:gridId', async (req, res) => {
    try {
        const { gridId } = req.params;
        const { days = 180 } = req.query;

        const query = `
      SELECT 
        observation_date,
        vv_mean, vv_std, vv_median, vv_min, vv_max,
        vh_mean, vh_std, vh_median, vh_min, vh_max,
        pixel_count,
        source_image_id
      FROM backscatter_timeseries
      WHERE grid_cell_id = $1
        AND observation_date >= CURRENT_DATE - INTERVAL '${parseInt(days)} days'
      ORDER BY observation_date ASC
    `;

        const result = await pool.query(query, [gridId]);

        // Format for charting
        const timeseries = result.rows.map(row => ({
            date: row.observation_date,
            vv: {
                mean: parseFloat(row.vv_mean),
                std: parseFloat(row.vv_std),
                median: parseFloat(row.vv_median),
                min: parseFloat(row.vv_min),
                max: parseFloat(row.vv_max)
            },
            vh: {
                mean: parseFloat(row.vh_mean),
                std: parseFloat(row.vh_std),
                median: parseFloat(row.vh_median),
                min: parseFloat(row.vh_min),
                max: parseFloat(row.vh_max)
            },
            pixel_count: row.pixel_count,
            source: row.source_image_id
        }));

        res.json({
            grid_cell_id: gridId,
            observations: timeseries,
            count: timeseries.length
        });

    } catch (error) {
        console.error('Error fetching time series:', error);
        res.status(500).json({ error: 'Failed to fetch time series data' });
    }
});

/**
 * GET /api/timeseries/:gridId/profile
 * Get backscatter profile formatted for chart display
 */
router.get('/:gridId/profile', async (req, res) => {
    try {
        const { gridId } = req.params;

        const query = `
      SELECT 
        observation_date,
        vv_median, vh_median
      FROM backscatter_timeseries
      WHERE grid_cell_id = $1
        AND observation_date >= CURRENT_DATE - INTERVAL '1 year'
      ORDER BY observation_date ASC
    `;

        const result = await pool.query(query, [gridId]);

        // Convert to dB for visualization
        const profile = result.rows.map(row => ({
            date: row.observation_date,
            vv_db: row.vv_median > 0 ? 10 * Math.log10(row.vv_median) : -40,
            vh_db: row.vh_median > 0 ? 10 * Math.log10(row.vh_median) : -40
        }));

        res.json({
            grid_cell_id: gridId,
            profile,
            count: profile.length
        });

    } catch (error) {
        console.error('Error fetching profile:', error);
        res.status(500).json({ error: 'Failed to fetch backscatter profile' });
    }
});

module.exports = router;
