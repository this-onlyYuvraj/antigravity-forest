# Project Structure & File Details

This document provides a detailed overview of the **Deforestation Monitoring System**, outlining the purpose and functionality of each major file and directory in the project.

## 📂 Root Directory
The control center for the entire project.

- **`package.json`**: The master orchestration file. It contains scripts to run the entire stack.
  - `npm run dev`: Runs both the Backend API and Frontend simultaneously.
  - `npm run start:pipeline`: Manually runs the Python analysis pipeline.
- **`docker-compose.yml`**: Defines your database infrastructure. It spins up a **PostgreSQL** database with the **PostGIS** extension (required for storing map/geographic data).
- **`database/`**:
  - `schema.sql`: Creates the database tables (`processed_images`, `alerts`, `boundaries`, etc.).
  - `seed.sql`: Populates the database with initial test data.

## 🐍 Backend Python (`/backend-python`)
**The "Brain".** This is where the actual science happens. It processes satellite imagery to find deforestation.

- **`pipeline.py`**: The main script that runs the analysis. It is currently set up as an MVP (Minimum Viable Product):
    1.  **Queries Earth Engine** for new Sentinel-1 satellite images.
    2.  **Preprocesses** the images (removing noise).
    3.  **Detects Anomalies** using the ALT (Adaptive Linear Thresholding) algorithm.
    4.  **Validates** these anomalies using a Machine Learning (MLP) model.
    5.  **Stores Alerts** in the database for the web app to verify.
    *   *Note: It currently uses a function `generate_mock_grid_observations` to generate synthetic test data for the grid cells.*

- **`config.py`**: Stores global settings like the Area of Interest (AOI) coordinates (currently set to Novo Progresso), logging paths, and database credentials.
- **`db_utils.py`**: A helper that handles all connections to the PostgreSQL database (saving alerts, reading history).
- **`services/`**: Contains `gee_service` (Google Earth Engine), which handles the communication with satellite data providers.
- **`models/`**: Contains the logic for the detection algorithms (`alt_detector`) and validation models (`mlp_model`).

## 🌐 Backend API (`/backend-api`)
**The "Bridge".** This Node.js app connects your database to the frontend.

- **`server.js`**: The entry point for the API. It starts an Express web server (likely on port 3001 or 5000).
- **`routes/`**: Defines the URL endpoints the frontend talks to (e.g., `GET /api/alerts` to fetch the latest deforestation alerts).

## 💻 Frontend (`/frontend`)
**The "Face".** A Next.js web application for visualizing the data.

- **`app/page.tsx`**: The main dashboard. This is the code for the home page you see in the browser.
- **`app/layout.tsx`**: The "shell" of your website. It defines the common structure (HTML tags, global fonts) shared by all pages.
- **`app/globals.css`**: The global stylesheet. This controls the look and feel (colors, fonts, Tailwind usage).
- **`components/`**: Likely contains reusable parts of your UI, such as:
    - **Map Component**: For displaying the Leaflet map and alerts.
    - **Sidebar/Dashboard**: For showing statistics and lists.

## 🚀 How they work together
1.  **Python Pipeline** runs, fetches satellite data, detects deforestation, and saves **Alerts** to the **Database**.
2.  **Backend API** reads these **Alerts** from the **Database** and serves them as JSON.
3.  **Frontend** calls the **Backend API** and displays the **Alerts** as polygons on the interactive Map.
