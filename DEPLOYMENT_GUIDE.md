# ☁️ Deployment Guide: groww-factor

This guide explains how to deploy the **groww-factor** 3-tier architecture to the cloud for free using Render and Vercel.

---

## 1. Backend Deployment (Render)

### Step 1: Create a New Web Service
1. Sign in to [Render.com](https://render.com/).
2. Click **New +** > **Web Service**.
3. Connect your GitHub repository (`Milestone_1`).

### Step 2: Configure Settings
- **Name:** `groww-rag-api`
- **Language:** `Python 3`
- **Branch:** `main`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `./render_start.sh`

### Step 3: Add Environment Variables
Click **Environment** and add the following:
- `GOOGLE_API_KEY`: (Your Google AI Studio Key)
- `PYTHONUNBUFFERED`: `1`

> [!NOTE]
> Render will automatically assign a `PORT`. Our `render_start.sh` script is already configured to detect and use it.

---

## 2. Frontend Deployment (Vercel)

### Step 1: Import Project
1. Sign in to [Vercel](https://vercel.com/).
2. Click **Add New** > **Project**.
3. Import the `Milestone_1` repository.

### Step 2: Configure the Sub-directory
1. In the **Framework Preset**, select **Next.js**.
2. **Root Directory:** Set this to `frontend_next_js`.

### Step 3: Add Environment Variables
1. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL`: `https://your-render-service-url.onrender.com`
2. Click **Deploy**.

---

## 🛠️ Maintenance & Troubleshooting

### Why is the first request slow?
On Render's free tier, the service spins down after 15 minutes of inactivity. When a user first visits:
1. Render wakes up the machine (~15s).
2. Our `render_start.sh` runs a fresh data ingestion (~10s).
3. The API goes online.
**Expect a ~25s wait for the very first "cold" visit.**

### Checking Logs
- **Backend:** Check the Render dashboard logs to see the Stage 1/3 ingestion progress.
- **Frontend:** Use the Vercel deployment logs to troubleshoot connection issues.

### Daily Schedule
The `orchestrator/scheduler.py` runs automatically in the background on Render. As long as the service is "awake", it will trigger the job every day at 09:30 AM IST.
