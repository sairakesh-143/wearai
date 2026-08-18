# 🏭 WearAI — Intelligent AI Warehouse Management Platform

[![GitHub repo](https://img.shields.io/badge/GitHub-sairakesh--143%2Fwearai-indigo.svg?style=flat&logo=github)](https://github.com/sairakesh-143/wearai)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python)](https://python.org)
[![TailwindCSS](https://img.shields.io/badge/UI-TailwindCSS%20%2B%20Lucide-38B2AC.svg?style=flat&logo=tailwind-css)](https://tailwindcss.com)
[![Vercel](https://img.shields.io/badge/Deploy-Vercel-black.svg?style=flat&logo=vercel)](https://vercel.com)
[![Author](https://img.shields.io/badge/Author-Sai%20Rakesh-orange.svg?style=flat)](https://github.com/sairakesh-143)

> **WearAI** is a modern, autonomous AI-powered Warehouse Management & Optimization Platform designed to eliminate fulfillment bottlenecks, automate stock conflict resolutions, optimize picking routes, and provide end-to-end visibility across warehouse operations.

---

## 👨‍💻 Author & Project Lead
- **Lead Developer**: Sai Rakesh
- **GitHub**: [@sairakesh-143](https://github.com/sairakesh-143)
- **Repository**: [sairakesh-143/wearai](https://github.com/sairakesh-143/wearai)

---

## 🌟 Key Features

- 🧠 **AI Smart Decisions & Conflict Allocation Engine**: Automatically detects stock contention between VIP and standard orders, reallocating critical units to maximize on-time delivery SLAs.
- 📦 **End-to-End Order Lifecycle**: Complete tracking across *New → Confirmed → Picking → Packing → Quality Check → Ready for Dispatch → Dispatched*.
- 📊 **Real-Time Warehouse Analytics**: Live KPIs for fulfillment percentage, bottleneck detection, zone utilization, and average cycle times.
- 🗺️ **Intelligent Route & Zone Optimization**: Generates optimized pick paths across warehouse zones (A, B, C, D) to reduce worker travel time.
- ⚠️ **Automated Exception Management**: Instant handling for missing items, damaged packaging, inventory mismatches, and picking delays with automated recommendations.
- ⚡ **Live Operations Feed**: Real-time event stream simulating warehouse floor activities and stock status updates.
- 🔐 **Role-Based Access Control**: Preconfigured roles for Administrator, Warehouse Manager, and Operations Staff.

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/sairakesh-143/wearai.git
cd wearai
```

### 2. Standalone Frontend (Instant Run)
You can directly open `index.html` in any modern web browser or run a lightweight HTTP server:
```bash
# Python HTTP Server
python -m http.server 8000
```
Then visit `http://localhost:8000`.

### 3. Full-Stack Setup (FastAPI + MongoDB)
```bash
# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload --port 8000
```
- Open UI: `http://localhost:8000/`
- Interactive API Docs (Swagger): `http://localhost:8000/docs`

---

## 🔑 Demo Login Credentials

| Role | Name | Email | Password |
|---|---|---|---|
| **Admin** | **Sai Rakesh** | `rakesh@wearai.io` | `demo1234` |
| **Manager** | Vikram Patel | `vikram@wearai.io` | `demo1234` |
| **Staff** | Arjun Mehta | `arjun@wearai.io` | `demo1234` |

*(Quick login buttons are also available directly on the login screen!)*

---

## 📁 Project Structure

```
wearhouse.ai/
├── main.py              # FastAPI application & MongoDB backend
├── index.html           # Full dynamic Single-Page Application (SPA)
├── requirements.txt     # Python backend dependencies
├── vercel.json          # Vercel serverless deployment configuration
├── DEPLOYMENT.md        # Step-by-step production deployment guide
├── api/
│   └── index.py         # Vercel serverless entry point
├── public/
│   └── index.html       # Static distribution
└── README.md            # Project documentation & overview
```

---

## ☁️ Deployment (Vercel & Cloud)

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions on deploying to **Vercel** with MongoDB Atlas.

---

## 📄 License
Created and maintained with ❤️ by **Sai Rakesh** ([@sairakesh-143](https://github.com/sairakesh-143)).
