/**
 * Express Server - Deforestation Monitoring API
 */

const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
require('dotenv').config({ path: '../.env' });

const app = express();
const PORT = process.env.API_PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(morgan('dev'));

// Test database connection
require('./db/connection');

// Routes
const alertsRouter = require('./routes/alerts');
const timeseriesRouter = require('./routes/timeseries');

app.use('/api/alerts', alertsRouter);
app.use('/api/timeseries', timeseriesRouter);
app.use('/api/boundaries', require('./routes/boundaries'));
app.use('/api/layers', require('./routes/layers'));
app.use('/api/checking', require('./routes/checking'));

// Health check
app.get('/api/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: '1.0.0'
    });
});

// Root endpoint
app.get('/', (req, res) => {
    res.json({
        name: 'Deforestation Monitoring API',
        version: '1.0.0',
        endpoints: {
            alerts: '/api/alerts',
            timeseries: '/api/timeseries/:gridId',
            health: '/api/health'
        }
    });
});

// Error handler
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({
        error: 'Internal server error',
        message: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
});

// Start server
app.listen(PORT, () => {
    console.log('🚀 Deforestation Monitoring API');
    console.log(`📡 Server running on http://localhost:${PORT}`);
    console.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
});

module.exports = app;
