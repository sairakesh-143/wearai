# 🚀 WearAI — Deployment Guide

Guide for deploying **WearAI** (Intelligent Warehouse Operations Platform) to Vercel and MongoDB Atlas.

---

## 📋 Prerequisites
- **GitHub Repository**: [sairakesh-143/wearai](https://github.com/sairakesh-143/wearai)
- **Vercel Account**: [vercel.com](https://vercel.com) (Free tier supported)
- **MongoDB Atlas Cluster**: [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)

---

## 🏗️ Architecture on Vercel

```
wearai/
├── api/
│   └── index.py        # Serverless backend (FastAPI)
├── public/
│   └── index.html      # Static Single-Page App (SPA)
├── requirements.txt    # Python packages
└── vercel.json         # Route mappings & build config
```

---

## 📦 Step-by-Step Deployment

### 1. Push Latest Code to GitHub
```powershell
git add .
git commit -m "Update project branding to WearAI by Sai Rakesh"
git push origin main
```

### 2. Set Up MongoDB Atlas
1. Sign in to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create a free shared cluster (e.g. M0 tier).
3. Under **Database Access**, create a user (e.g. `wearai_admin`).
4. Under **Network Access**, add IP `0.0.0.0/0` (allow all incoming traffic for serverless functions).
5. Copy your connection string:
   ```
   mongodb+srv://wearai_admin:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

### 3. Deploy on Vercel
1. Go to [vercel.com/new](https://vercel.com/new).
2. Import the `sairakesh-143/wearai` repository.
3. In the **Environment Variables** section, add:

| Variable Name | Description | Example Value |
|---|---|---|
| `MONGO_URI` | MongoDB Atlas Connection String | `mongodb+srv://...` |
| `DB_NAME` | Database Name | `wearai_db` |
| `SECRET_KEY` | JWT Secret Key | `wearai-production-secret-key-2026` |
| `ALGORITHM` | Algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token Lifetime | `1440` |

4. Click **Deploy**.

---

## 🔍 Verification

Once deployed:
- **Web App**: `https://<your-app>.vercel.app`
- **Swagger Docs**: `https://<your-app>.vercel.app/docs`
- **Health Check**: `https://<your-app>.vercel.app/api/health`

---

## 👨‍💻 Maintainer
**Sai Rakesh** ([@sairakesh-143](https://github.com/sairakesh-143))
