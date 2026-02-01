# Deforestation Monitoring System Documentation 🌳🛰️

## 1. System Overview
The **Deforestation Monitoring System** is a full-stack application designed to detect, validate, and visualize illegal deforestation activity in near real-time. It focuses on the **Novo Progresso, Pará** region in the Brazilian Amazon, leveraging Synthetic Aperture Radar (SAR) data from Sentinel-1 satellites to detect changes through cloud cover.

### High-Level Architecture
The system consists of three main components:
1.  **Data Processing Pipeline (Python)**: Fetches satellite data, runs detection algorithms, and stores results.
2.  **REST API (Node.js/Express)**: Serves data to the frontend and handles business logic.
3.  **Frontend Dashboard (Next.js/React)**: visualizes alerts on an interactive map for end-users.

---

## 2. Data Processing Pipeline (`backend-python`)
This is the core engine of the system. It runs on a schedule (e.g., daily) to process new satellite imagery.

### 2.1 Data Source: Sentinel-1 (C-band SAR)
-   **Why SAR?**: Unlike optical satellites (LandSat/Sentinel-2), SAR (Synthetic Aperture Radar) can "see" through clouds, smoke, and rain, which is critical for the Amazon rainforest.
-   **Observation**: We use Ground Range Detected (GRD) products, measuring **VV** (Vertical-Vertical) and **VH** (Vertical-Horizontal) polarization backscatter.
-   **Integration**: Google Earth Engine (GEE) Python API is used to fetch and preprocess this massive dataset.

### 2.2 Detection Algorithm: Adaptive Linear Thresholding (ALT)
Detecting deforestation in SAR images relies on identifying significant **drops in backscatter intensity** (forests reflect more radar energy than bare ground).

The **ALT Algorithm** (`models/alt_detector.py`) works as follows:
1.  **Baseline Calculation**: For every grid cell (approx 100x100m), we calculate a historical baseline of "normal" forest behavior over the last 6 months.
2.  **Change Detection**: When a new image arrives, we compare its backscatter values against the baseline.
3.  **Adaptive Thresholds**: instead of a fixed cutoff, the threshold adapts based on:
    -   **Natural Variability**: Areas with naturally high variance get looser thresholds.
    -   **Proximity to Clearings**: Areas near existing deforestation get stricter (more sensitive) thresholds, as expanding clearings are common.
4.  **Anomaly Identification**: If the drop in backscatter (dB) exceeds the calculated threshold (e.g., `-3.0 dB`), it is flagged as a potential alert.

### 2.3 Validation: MLP Neural Network
To reduce false positives (caused by seasonal moisture changes or sensor noise), we use a secondary validation step.
-   **Model**: A Multi-Layer Perceptron (MLP) Neural Network (`models/mlp_model.py`).
-   **Input**: Normalized backscatter time-series history of the candidate pixel.
-   **Logic**: The model recognizes the temporal signature of deforestation (a sharp, sustained drop) vs. noise (random spikes).
-   **Output**: A confidence score (0-1). Alerts > 85% confidence are marked "High Confidence".

---

## 3. Backend API (`backend-api`)
The API acts as the bridge between the database and the user interface.

### 3.1 Technology
-   **Node.js & Express**: Lightweight, fast REST API.
-   **PostgreSQL**: Relational database for structured data.
-   **PostGIS**: Spatial extension for handling geometric data (polygons, points, intersections).

### 3.2 Key Endpoints
-   **`GET /api/alerts`**: Fetches deforestation alerts. Supports filtering by date, status, and risk tier. returns GeoJSON.
-   **`GET /api/boundaries`**: Returns municipal and protected area boundaries as GeoJSON layers.
-   **`GET /api/alerts/stats`**: Aggregates data for the dashboard counters (Total Area, Recent Alerts, etc.).

### 3.3 Spatial Analysis (PostGIS)
The system automatically classifies the **Risk Tier** of an alert using spatial joins:
-   **Tier 1 (Standard)**: Deforestation on private or unclaimed land.
-   **Tier 2 (High Priority)**: Deforestation inside **Protected Areas** (Conservation Units or Indigenous Territories).
-   **Mechanism**: The database checks `ST_Intersects(alert.geom, boundary.geom)` to assign these tiers automatically.

---

## 4. Frontend Dashboard (`frontend`)
The user interface designed for environmental monitors and authorities.

### 4.1 Technology
-   **Next.js 15**: React framework for production-grade apps.
-   **Leaflet.js**: Lightweight interactive maps.
-   **Tailwind CSS**: Modern utility-first styling.

### 4.2 Features
-   **Interactive Map**:
    -   Displays alerts as colored polygons (Red = Tier 2, Orange = Tier 1).
    -   **Municipal Overlay**: Displays the dashed amber boundary of the monitoring zone (Novo Progresso).
    -   **Popup Details**: Clicking an alert shows hectarage, confidence score, and detection date.
-   **Live Statistics**: Real-time counters updating as new data comes in.
-   **Notification System**: On-screen toasts alert users when high-priority detection occurs (polling every 12 hours).

---

## 5. Database Schema (`database/schema.sql`)
The core tables that power the system:

1.  **`alert_candidate`**: Stores the detected deforestation events, coordinates, confidence scores, and status.
2.  **`forest_boundaries`**: Stores static administrative maps (Municipalities, Indigenous Lands) for spatial checking.
3.  **`backscatter_timeseries`**: Stores the raw history of radar signals for every grid cell (used for training and baselines).
4.  **`processed_images`**: Tracks which satellite images have already been analyzed to prevent duplication.

---

## 6. How It All Connects (Data Flow)
1.  **Satellite Pass**: Sentinel-1 flies over the Amazon.
2.  **Ingestion**: `pipeline.py` queries Google Earth Engine for the new image.
3.  **Detection**: The ALT algorithm scans the image and finds 50 candidate pixels dropping in signal.
4.  **Validation**: The MLP model reviews them and rejects 10 as noise. 40 are confirmed.
5.  **Classification**: PostGIS determines 5 of them are inside "Terra Indígena Baú".
6.  **Storage**: These 40 alerts are saved to Postgres, with the 5 inside the territory marked as **TIER 2**.
7.  **Visualization**: The Next.js frontend fetches these new rows and renders red polygons on the map.
8.  **Alert**: The dashboard shows a "Priority Alert" notification to the user.

---

---

## 7. Code Deep Dive (How the Logic Works) 🧠

This section explains exactly what happens inside the key files of the system.

### 🐍 `backend-python/` (The Brain)

#### 1. `models/mlp_model.py` (The Neural Network)
This file validates alerts to prevent false alarms.
-   **What it does**: It runs a TensorFlow/Keras **Multi-Layer Perceptron (MLP)**.
-   **The Input**: It takes **180 numbers** for every pixel. These numbers represent the last 30 satellite passes (Mean, Standard Deviation, and Median Difference for both VV and VH radar bands).
-   **The Logic**:
    -   It feeds these 180 numbers into a "Hidden Layer" of 40 neurons.
    -   Then into a second layer of 10 neurons.
    -   Finally, it outputs a single **Confidence Score** (0% to 100%).
-   **Why?**: Deforestation has a specific "signature" (sudden, permanent drop). Rain or wind has a "noisy" signature (spiky). The Neural Network learns this difference.

#### 2. `models/alt_detector.py` (The First Pass Detector)
This file does the initial scanning of the forest.
-   **What it does**: It runs the **Adaptive Linear Thresholding (ALT)** algorithm.
-   **The Logic**:
    -   It calculates a "Baseline" (What does this forest usually look like?) using the last 6 months of data.
    -   It compares the *new* image to this baseline.
    -   If the radar signal drops by more than **-2.0 dB** (VV band) or **-2.3 dB** (VH band), it flags it as a "Candidate Alert".
-   **Smart Feature**: It lowers the threshold if the pixel is near *other* deforestation, making it more sensitive to expanding frontiers.

#### 3. `pipeline.py` (The Conductor)
This script runs the whole show.
-   **Step 1**: It asks Google Earth Engine: *"Give me the latest Sentinel-1 image for Novo Progresso."*
-   **Step 2**: It cuts that image into small 100m grid cells.
-   **Step 3**: It passes each cell to `alt_detector.py` to find candidates.
-   **Step 4**: It passes candidates to `mlp_model.py` for validation.
-   **Step 5**: It saves the confirmed alerts to the PostgreSQL database.

---

### 🌐 `backend-api/` (The Messenger)

#### 1. `routes/alerts.js` (The Alert endpoint)
-   **Goal**: Deliver alerts to the map.
-   **Logic**:
    -   It runs a SQL query: `SELECT * FROM alert_candidate`.
    -   It converts the database rows into **GeoJSON** format (Standard map data format).
    -   It adds a "Risk Tier" property so the frontend knows whether to color it Red or Orange.

#### 2. `routes/boundaries.js` (The Map Layers)
-   **Goal**: Draw the Novo Progresso outline.
-   **Logic**:
    -   It queries the `forest_boundaries` table.
    -   It returns the massive polygon shape of the municipality so the frontend can draw the amber dashed line.

---

### 💻 `frontend/` (The Interface)

#### 1. `components/Map/AlertMap.tsx` (The Interactive Map)
-   **What it does**: Controls the Leaflet map.
-   **Key Logic**:
    -   **Fetching**: Every 12 hours (or on load), it calls `/api/alerts` to get new data.
    -   **Rendering**: It takes the GeoJSON and draws loops.
        -   *If Tier 2 (Protected Area)* -> Fill Red.
        -   *If Tier 1 (Standard)* -> Fill Orange.
    -   **Boundaries**: It draws the static Amber line for the municipality.

#### 2. `lib/api.ts` (The Phone Book)
-   **What it does**: Holds all the "Phone Numbers" (URLs) for the backend.
-   **Logic**: Instead of typing `fetch('http://localhost:3001/api/alerts')` everywhere, we just call `api.getAlerts()`. This keeps the code clean.
