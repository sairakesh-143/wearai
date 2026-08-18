# SmartWMS Vercel Deployment Guide

## Prerequisites
- GitHub account with your repository pushed
- Vercel account (free at https://vercel.com)
- MongoDB Atlas account (for cloud database)

## Step-by-Step Deployment

### 1. **Prepare Your Repository**
✅ Project structure is already set up:
```
SmartWMS/
├── api/
│   ├── index.py (FastAPI backend)
│   └── requirements.txt
├── public/
│   └── index.html (Frontend)
├── vercel.json (Configuration)
├── .env.example (Environment variables template)
└── .gitignore
```

### 2. **Push to GitHub**
```powershell
cd C:\Users\grand\OneDrive\Desktop\SmartWMS
git add .
git commit -m "Set up for Vercel deployment"
git push origin main
```

### 3. **Set Up MongoDB Atlas (if not already done)**
1. Go to https://www.mongodb.com/cloud/atlas
2. Create a free cluster
3. Create a database user
4. Get your connection string (looks like: `mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority`)
5. Note this down - you'll need it for Vercel

### 4. **Deploy to Vercel**

#### Option A: Using Vercel Dashboard (Recommended)
1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your GitHub repository
4. Vercel auto-detects the configuration from `vercel.json`
5. Click "Environment Variables"
6. Add these variables:
   - **MONGO_URI**: Your MongoDB connection string
   - **SECRET_KEY**: A secure random key (generate one)
   - **DB_NAME**: `smart_wms`

7. Click "Deploy" ✅

#### Option B: Using Vercel CLI
```powershell
# Install Vercel CLI (if not already installed)
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod

# When prompted, add environment variables:
# - MONGO_URI
# - SECRET_KEY
```

### 5. **Environment Variables Setup in Vercel Dashboard**

1. Go to your project settings
2. Navigate to "Settings" → "Environment Variables"
3. Add:

| Variable | Value | Example |
|----------|-------|---------|
| `MONGO_URI` | Your MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority` |
| `SECRET_KEY` | A strong random string | Generate with: `openssl rand -hex 32` |
| `DB_NAME` | Database name | `smart_wms` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry | `1440` |

### 6. **Verify Your Deployment**

After deployment completes:
1. Your site is live at: `https://your-project-name.vercel.app`
2. Check API health: `https://your-project-name.vercel.app/api/health`
3. Check frontend: `https://your-project-name.vercel.app`

### 7. **Troubleshooting**

**Issue**: "Build failed"
- Check that all dependencies in `api/requirements.txt` are correct
- Ensure `api/index.py` exists with FastAPI app

**Issue**: "API endpoints not working"
- Verify `MONGO_URI` is correct and database is accessible
- Check environment variables are set in Vercel dashboard

**Issue**: "Module not found"
- Ensure `requirements.txt` is in the `api/` folder
- Restart deployment after fixing

### 8. **Update Code**
Simply push changes to GitHub, and Vercel auto-deploys:
```powershell
git add .
git commit -m "Your changes"
git push origin main
```

## Important Notes
- ⚠️ Never commit `.env` files to Git (it's in `.gitignore`)
- 🔐 Keep `SECRET_KEY` secret - use strong random strings
- 📝 Check `.env.example` for all required variables
- 🔄 Deployments auto-trigger on push to main branch

## API Base URL
Update your frontend API calls to use:
```javascript
const API_URL = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:8000/api';
```

## Need Help?
- Vercel Docs: https://vercel.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com/
- MongoDB Atlas: https://docs.atlas.mongodb.com/
