# Startup Instructions

## ✅ Backend API is Running!
Your backend API is successfully connected to the database.

## 🚀 Start the Frontend

After `npm install` completes in the frontend directory, **restart the frontend server**:

```powershell
# In the frontend terminal, press Ctrl+C to stop the current process
# Then run:
npm run dev
```

The server should start successfully at **http://localhost:3000**

---

## What Was Fixed

1. ✅ **Backend API**: Connected to PostgreSQL database
2. ✅ **Autoprefixer**: Installed missing dependency
3. ✅ **Next.js Version**: Fixed from 16.1.6 back to 15.1.6 (v16 doesn't exist yet)
4. ✅ **TypeScript Config**: Fixed `jsx` setting from `react-jsx` to `preserve` for Next.js compatibility

---

## Access the Application

Once both servers are running:

- **Frontend Dashboard**: http://localhost:3000
- **API**: http://localhost:3001
- **API Health Check**: http://localhost:3001/api/health

You should see the interactive map with sample deforestation alerts! 🗺️
