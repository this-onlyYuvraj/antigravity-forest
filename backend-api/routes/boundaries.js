const express = require('express');
const router = express.Router();
const db = require('../db/connection');

// Get all municipal boundaries or specific one
router.get('/', async (req, res) => {
    try {
        const { type } = req.query;
        let query = `
            SELECT 
                id, name, boundary_type, official_code,
                ST_AsGeoJSON(geom) as geojson
            FROM forest_boundaries
        `;
        let params = [];

        if (type) {
            query += ` WHERE boundary_type = $1`;
            params.push(type.toUpperCase());
        }

        const result = await db.query(query, params);

        const features = result.rows.map(row => ({
            type: 'Feature',
            id: row.id,
            properties: {
                name: row.name,
                type: row.boundary_type,
                code: row.official_code
            },
            geometry: JSON.parse(row.geojson)
        }));

        res.json({
            type: 'FeatureCollection',
            features: features
        });
    } catch (err) {
        console.error('Error fetching boundaries:', err);
        res.status(500).json({ error: 'Failed to fetch boundaries' });
    }
});

module.exports = router;
