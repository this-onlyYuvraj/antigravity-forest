# Deforestation Monitoring System 🌳🛰️

A full-stack web application for detecting and monitoring deforestation using Sentinel-1 SAR data, Google Earth Engine, and Deep Learning.

## 🚀 Quick Start

### 1. Prerequisites
- Node.js & npm
- PostgreSQL with PostGIS extension
- Python 3.9+

### 2. Database Setup
Ensure you have PostgreSQL 15+ installed and running locally.

```powershell
# Create database and enable PostGIS
# (If psql is not in your PATH, use pgAdmin or the SQL Shell)
createdb -U postgres deforestation_db
psql -U postgres -d deforestation_db -c "CREATE EXTENSION postgis;"

# Load Schema & Seed Data
psql -U postgres -d deforestation_db -f database/schema.sql
psql -U postgres -d deforestation_db -f database/seed.sql
```

### 3. Run Backend API
```powershell
cd backend-api
npm install
npm run dev
# Server running on http://localhost:3001
```

### 4. Run Frontend
```powershell
cd frontend
npm install
npm run dev
# Dashboard at http://localhost:3000
```

## 🛠️ Tech Stack
- **Frontend**: Next.js 15, React 18, Leaflet, Tailwind CSS
- **Backend API**: Node.js, Express, PostgreSQL/PostGIS
- **Data Pipeline**: Python, Google Earth Engine API, TensorFlow/Keras

## ✅ Features
- Near real-time deforestation alerts
- Interactive map visualization
- Risk tier classification (Protected Areas vs Standard)
- Dashboard statistics
- On-screen notifications system
