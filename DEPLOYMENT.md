# 🚀 Revival Scanner - Railway Deployment Guide

Complete guide to deploying your Revival Scanner to Railway.app for 24/7 operation.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Variables Setup](#environment-variables-setup)
3. [Railway Deployment Steps](#railway-deployment-steps)
4. [Gmail App Password Setup](#gmail-app-password-setup)
5. [Verification & Monitoring](#verification--monitoring)
6. [Data Backup](#data-backup)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you start, make sure you have:

- ✅ Railway.app account (free to sign up at [railway.app](https://railway.app))
- ✅ GitHub account with this repo pushed
- ✅ BirdEye API key (`BIRDEYE_API_KEY`)
- ✅ Helius RPC endpoint (`RPC_ENDPOINT`)
- ✅ Gmail App Password for email notifications (see [Gmail Setup](#gmail-app-password-setup))
- ✅ Other AI API keys (OpenAI, Anthropic, Groq, etc.) - optional

---

## Environment Variables Setup

### 🔒 Security First!

**NEVER commit your `.env` file to GitHub!** It's already in `.gitignore`, but double-check:

```bash
# Verify .env is not tracked
git status

# If .env appears, add it to .gitignore
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Ensure .env is ignored"
```

### 📝 Required Environment Variables

Railway will need these environment variables (set in Railway dashboard, NOT in code):

#### **Critical APIs (Required)**
```bash
BIRDEYE_API_KEY=your_birdeye_api_key_here
RPC_ENDPOINT=your_helius_rpc_url_here
```

#### **Email Notifications (Recommended)**
```bash
EMAIL_PASSWORD=your_gmail_app_password_here
PAPER_TRADING_EMAIL_ADDRESS=your-email@gmail.com
PAPER_TRADING_EMAIL_USERNAME=your-email@gmail.com
```

#### **Production Settings (Recommended)**
```bash
WEB_APP_BASE_URL=https://your-app.up.railway.app
FLASK_ENV=production
FLASK_DEBUG=False
```

#### **AI Services (Optional - for other agents)**
```bash
OPENAI_KEY=your_openai_key_here
ANTHROPIC_KEY=your_anthropic_key_here
GROQ_API_KEY=your_groq_key_here
DEEPSEEK_KEY=your_deepseek_key_here
```

---

## Railway Deployment Steps

### Step 1: Connect GitHub Repo

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `moon-dev-ai-agents` repository
5. Railway will detect the `Dockerfile` automatically

### Step 2: Configure Environment Variables

1. In your Railway project, click **"Variables"** tab
2. Click **"+ New Variable"**
3. Add each variable from the list above:
   - Click **"+ New Variable"**
   - Enter `BIRDEYE_API_KEY` in the key field
   - Paste your BirdEye API key in the value field
   - Click **"Add"**
   - Repeat for all other variables

**⚠️ Important:** Railway encrypts these variables - they're never visible in your code or logs.

### Step 3: Add Persistent Volume

Your paper trading data needs to survive restarts:

1. In Railway project, go to **"Volumes"** tab
2. Click **"+ New Volume"**
3. Set mount path: `/app/src/data`
4. Click **"Add Volume"**

This ensures your paper trading positions, trades, and scan results persist across deployments.

### Step 4: Deploy!

1. Click **"Deploy"** in the Railway dashboard
2. Railway will:
   - Build your Docker image (takes 3-5 minutes first time)
   - Run health checks
   - Assign a public URL (like `your-app.up.railway.app`)

3. Monitor the build in **"Deployments"** tab

### Step 5: Update Base URL

Once deployed, update the base URL environment variable:

1. Go to **"Variables"** tab
2. Find `WEB_APP_BASE_URL`
3. Update it to your Railway URL: `https://your-app.up.railway.app`
4. Railway will auto-redeploy

Now email notifications will have working links!

---

## Gmail App Password Setup

For paper trading email notifications, you need a Gmail App Password (NOT your regular Gmail password).

### Why App Password?

Gmail requires app-specific passwords for security when using SMTP from third-party apps.

### Steps to Create Gmail App Password:

1. **Enable 2-Factor Authentication** (required first):
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Click **"2-Step Verification"**
   - Follow prompts to enable (use your phone)

2. **Generate App Password**:
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Select **"Mail"** and **"Other (Custom name)"**
   - Enter name: `Revival Scanner`
   - Click **"Generate"**
   - Google shows a 16-character password (e.g., `abcd efgh ijkl mnop`)

3. **Copy App Password** (remove spaces):
   - Copy: `abcdefghijklmnop` (no spaces)
   - Paste into Railway variable `EMAIL_PASSWORD`

4. **Test Email Notifications**:
   ```bash
   # After deployment, check Railway logs for:
   "✅ Email sent successfully to your-email@gmail.com"
   ```

### Troubleshooting Email:

- **"Authentication failed"**: Double-check App Password (no spaces)
- **"Connection timeout"**: Check `PAPER_TRADING_EMAIL_SMTP_SERVER=smtp.gmail.com`
- **"No emails received"**: Check spam folder, verify `PAPER_TRADING_EMAIL_ADDRESS`

---

## Verification & Monitoring

### ✅ Verify Deployment

1. **Check Health:**
   ```bash
   curl https://your-app.up.railway.app/api/status
   # Should return: {"status": "ok", "scanner_running": true}
   ```

2. **View Dashboard:**
   - Open `https://your-app.up.railway.app` in browser
   - Should see Revival Scanner dashboard
   - Check **Live Activity** for scan progress

3. **Check Logs:**
   - In Railway dashboard, go to **"Deployments"** tab
   - Click **"View Logs"**
   - Look for:
     ```
     🌙 Moon Dev's Revival Scanner Web Dashboard
     📊 Starting background scanner thread...
     🚀 Web dashboard running at http://0.0.0.0:8080
     ```

### 📊 Monitor Performance

**Railway Dashboard:**
- **CPU Usage**: Should be <50% most of the time
- **Memory**: ~200-500 MB during scans
- **Network**: ~100-500 MB/day (API calls)

**Cost Estimate:**
- **Hobby Plan**: ~$5-10/month (500 MB RAM, light usage)
- **Pro Plan**: ~$10-20/month (1 GB RAM, heavier usage)

Railway charges based on resource usage, not uptime!

---

## Data Backup

### Automated Backup Script

Use the included backup script to download your paper trading data:

```bash
# From your local machine
./scripts/backup_data.sh https://your-app.up.railway.app
```

This creates a timestamped backup in `backups/YYYYMMDD_HHMMSS/` with:
- `positions.json` - Active paper trading positions
- `trades.json` - Historical trades
- `portfolio.json` - Portfolio snapshots
- `metrics.json` - Performance metrics
- `scan_results.json` - Latest scan results

### Manual Backup via Railway CLI

Install Railway CLI:
```bash
npm install -g @railway/cli
railway login
```

Download data from volume:
```bash
# List files in volume
railway volumes ls

# Download specific file
railway volumes cp /app/src/data/paper_trading/positions.csv ./local-backup/

# Download entire directory
railway volumes cp /app/src/data/paper_trading/ ./local-backup/
```

### Backup Schedule

**Recommended:**
- **Daily**: Automated backups before major decisions
- **Weekly**: Full data export for archival
- **Before updates**: Always backup before code changes

---

## Troubleshooting

### ❌ Build Fails

**Error: "requirements not found"**
- Solution: Ensure `requirements-production.txt` exists
- Check: File is committed to Git and pushed

**Error: "ta-lib installation failed"**
- Solution: The Dockerfile installs `gcc` for ta-lib compilation
- If still fails, try removing `ta-lib>=0.4.0` from `requirements-production.txt`

### ❌ App Crashes on Startup

**Error: "No module named 'anthropic'"**
- Solution: Check `requirements-production.txt` includes all dependencies
- Rebuild: Push an empty commit to trigger rebuild
  ```bash
  git commit --allow-empty -m "Rebuild"
  git push
  ```

**Error: "BIRDEYE_API_KEY not found"**
- Solution: Add `BIRDEYE_API_KEY` in Railway Variables tab
- Verify: No typos in variable name (case-sensitive!)

### ❌ Scans Not Running

**Symptoms**: Dashboard shows "Scanner not running"

1. **Check Logs**:
   - Railway dashboard → "Deployments" → "View Logs"
   - Look for errors in background scanner thread

2. **Verify APIs**:
   ```bash
   # Test BirdEye API
   curl "https://public-api.birdeye.so/defi/v3/token/meme/list?sort_by=liquidity&sort_type=desc&offset=0&limit=10" \
     -H "X-API-KEY: your_birdeye_api_key_here"
   ```

3. **Check Health Endpoint**:
   ```bash
   curl https://your-app.up.railway.app/api/status
   # Should show "scanner_running": true
   ```

### ❌ Email Notifications Not Working

**Check these in order:**

1. **App Password**: Verify it's correct (no spaces)
2. **2FA Enabled**: Gmail requires 2-factor authentication
3. **Variables Set**:
   - `EMAIL_PASSWORD`
   - `PAPER_TRADING_EMAIL_ADDRESS`
   - `PAPER_TRADING_EMAIL_USERNAME`
4. **Test Manually**: Check Railway logs for SMTP errors

### ❌ High Memory Usage

**Memory >1 GB consistently:**

1. **Check for memory leaks**:
   - Restart app via Railway dashboard
   - Monitor memory over 24 hours

2. **Optimize settings**:
   - Reduce scan frequency (if needed)
   - Clear caches periodically

3. **Upgrade plan**:
   - Railway Pro plan for more resources
   - Or optimize code (contact for help)

### 🆘 Still Having Issues?

1. **Check Railway Status**: [status.railway.app](https://status.railway.app)
2. **Review Logs**: Railway dashboard → "Deployments" → "View Logs"
3. **GitHub Issues**: Open an issue with logs and error details
4. **Discord**: Join Moon Dev community for real-time help

---

## Post-Deployment Checklist

- [ ] Railway deployment successful
- [ ] Health check passing (`/api/status`)
- [ ] Dashboard accessible via Railway URL
- [ ] Environment variables set (especially `BIRDEYE_API_KEY`, `RPC_ENDPOINT`)
- [ ] `WEB_APP_BASE_URL` updated to Railway URL
- [ ] Email notifications working (test with paper trade)
- [ ] Persistent volume attached (`/app/src/data`)
- [ ] First scan completed successfully
- [ ] Paper trading positions tracked
- [ ] Backup script tested locally
- [ ] Monitoring set up (Railway dashboard alerts)

---

## Next Steps

Once deployed:

1. **Monitor First Scan**: Watch Live Activity for first scan cycle (~10-15 minutes)
2. **Test Paper Trading**: Wait for Revival Scanner to find a token with score ≥ 0.4
3. **Verify Emails**: Check inbox for position opened notification
4. **Set Alerts**: Configure Railway alerts for CPU/memory thresholds
5. **Schedule Backups**: Set calendar reminder for weekly backups

---

## 💰 Cost Breakdown

**Estimated Monthly Costs:**

| Item | Cost | Notes |
|------|------|-------|
| Railway Hosting | $5-20 | Based on resource usage |
| BirdEye API | $0 | Free tier (1 req/sec) |
| Helius RPC | $0 | Free tier (10 req/sec) |
| Other APIs | $0-10 | Optional (OpenAI, etc.) |
| **Total** | **$5-30/month** | Cheaper than a lunch! 🌙 |

---

## 🎉 You're Deployed!

Your Revival Scanner is now running 24/7 in the cloud!

- **Dashboard**: `https://your-app.up.railway.app`
- **Auto-scans**: Every 1-2 hours
- **Paper trading**: Automatic position tracking
- **Emails**: Real-time notifications

**Welcome to the cloud, Moon Dev! 🚀🌙**

---

## 📚 Additional Resources

- **Railway Docs**: https://docs.railway.app
- **Railway CLI**: https://docs.railway.app/develop/cli
- **Railway Volumes**: https://docs.railway.app/guides/volumes
- **BirdEye API**: https://docs.birdeye.so
- **Helius RPC**: https://docs.helius.dev

---

*Built with ❤️ by Moon Dev's AI Assistant*
