# Quick Start Guide

## Get Started in 5 Minutes

### 1. Set Up Database (2 minutes)

```powershell
# Create database
psql -U postgres -c "CREATE DATABASE deforestation_db;"

# Load schema and sample data
psql -U postgres -d deforestation_db -f database\schema.sql
psql -U postgres -d deforestation_db -f database\seed.sql
```

### 2. Configure Environment (1 minute)

```powershell
# Copy and edit .env file
copy .env.example .env
notepad .env
```

**Minimum required changes**:
- Set `DB_PASSWORD` to your postgres password
- Set `NEXT_PUBLIC_MAPBOX_TOKEN` (get free token at mapbox.com)

### 3. Install Dependencies (2 minutes)

```powershell
# Backend API
cd backend-api
npm install

# Frontend
cd ..\frontend
npm install
```

### 4. Launch Application

**Terminal 1 - API**:
```powershell
cd backend-api
npm run dev
```

**Terminal 2 - Frontend**:
```powershell
cd frontend
npm run dev
```

**Access**: Open http://localhost:3000

---

## For Full System with SAR Processing

Follow the complete setup in [README.md](file:///d:/sample3/README.md)

**Additional requirements**:
- Python 3.9+ virtual environment
- Google Earth Engine account
- Twilio/SendGrid for notifications (optional)

See [walkthrough.md](file:///C:/Users/user/.gemini/antigravity/brain/2c81457d-a8ba-401e-85db-f7c37d5e62b4/walkthrough.md) for detailed implementation docs.
