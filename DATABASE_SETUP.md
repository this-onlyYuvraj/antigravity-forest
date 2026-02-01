# Database Setup Instructions

## Step 1: Create the Database

Open a **new PowerShell terminal** and run:

```powershell
# Connect to PostgreSQL (it will ask for your postgres password)
psql -U postgres

# In the psql prompt, run:
CREATE DATABASE deforestation_db;

# Verify it was created:
\l

# Connect to the new database:
\c deforestation_db

# Enable PostGIS extension:
CREATE EXTENSION IF NOT EXISTS postgis;

# Exit psql:
\q
```

## Step 2: Load the Schema

```powershell
# Load the database schema
psql -U postgres -d deforestation_db -f database\schema.sql

# Load sample data
psql -U postgres -d deforestation_db -f database\seed.sql
```

## Step 3: Verify Setup

```powershell
# Connect to database
psql -U postgres -d deforestation_db

# Check tables exist:
\dt

# You should see:
# - forest_boundaries
# - processed_images
# - alert_candidate
# - backscatter_timeseries

# Exit:
\q
```

## Alternative: One-Line Setup (if psql is in PATH)

```powershell
psql -U postgres -c "CREATE DATABASE deforestation_db;"
psql -U postgres -d deforestation_db -c "CREATE EXTENSION postgis;"
psql -U postgres -d deforestation_db -f database\schema.sql
psql -U postgres -d deforestation_db -f database\seed.sql
```

---

After running these commands, **restart your API server**:
- Press Ctrl+C in the `backend-api` terminal
- Run `npm run dev` again
- You should see: `✅ Database connected`
