# 🏀 PropStats - NBA Props Research Tool

A powerful, free NBA player props research tool with historical hit rates, game logs, and trend analysis.

![PropStats](https://img.shields.io/badge/PropStats-v1.0-violet)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- 🔍 **Player Search** - Search any active NBA player
- 📊 **Hit Rate Analysis** - L5, L10, L20, Season, Home/Away splits
- 📈 **Game Logs** - Detailed game-by-game breakdown
- 🎯 **Line Comparison** - Compare against any betting line
- 💡 **Recommendations** - AI-powered over/under suggestions
- ⚡ **Real-time Data** - Live sync from NBA.com

## Tech Stack

**Backend:**
- FastAPI (Python)
- SQLite database
- NBA.com API integration

**Frontend:**
- React 18 + Vite
- Tailwind CSS
- Lucide Icons

---

## 🚀 Quick Deploy

### Backend Deployment

#### Option 1: Railway (Recommended)

1. Fork this repo to your GitHub
2. Go to [Railway.app](https://railway.app) and create new project
3. Select "Deploy from GitHub repo"
4. Choose your forked repo
5. Set root directory: `backend`
6. Add environment variables:
   ```
   ADMIN_SECRET=your-secure-secret-here
   DATABASE_PATH=nba_props.db
   PORT=8000
   ```
7. Deploy! Railway will auto-detect the Dockerfile

#### Option 2: Render

1. Go to [Render.com](https://render.com)
2. New → Web Service → Connect GitHub
3. Root Directory: `backend`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables (same as above)

#### Option 3: Fly.io

```bash
cd backend
fly launch
fly secrets set ADMIN_SECRET=your-secret
fly deploy
```

### Frontend Deployment

#### Vercel (Recommended)

1. Go to [Vercel.com](https://vercel.com)
2. Import your GitHub repo
3. Set root directory: `frontend`
4. Add environment variable:
   ```
   VITE_API_URL=https://your-backend-url.railway.app
   ```
5. Deploy!

#### Netlify

1. Go to [Netlify.com](https://netlify.com)
2. Import repo, set base directory: `frontend`
3. Build command: `npm run build`
4. Publish directory: `dist`
5. Add env var: `VITE_API_URL=https://your-backend-url`

---

## 🔧 Initial Setup

After deploying the backend, you need to sync NBA players:

```bash
# Sync all active NBA players (run once)
curl -X POST "https://your-api-url/admin/sync-players?secret=your-admin-secret"
```

This populates the database with ~500 active NBA players. Player game logs are fetched on-demand when users search.

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status |
| `/health` | GET | Health check |
| `/players/search?q=lebron` | GET | Search players |
| `/players/{id}/analysis?stat=points&line=25.5` | GET | Get hit rate analysis |
| `/usage/check?ip=x.x.x.x` | GET | Check usage limits |
| `/admin/sync-players?secret=xxx` | POST | Sync all players |
| `/admin/sync-player/{id}?secret=xxx` | POST | Sync specific player |
| `/admin/stats?secret=xxx` | GET | Database stats |

### Supported Stats

- `points` - Points scored
- `rebounds` - Total rebounds
- `assists` - Assists
- `threes` - 3-pointers made
- `steals` - Steals
- `blocks` - Blocks
- `pra` - Points + Rebounds + Assists combined

---

## 🖥️ Local Development

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
python main.py
# or
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env

# Run dev server
npm run dev
```

---

## 📁 Project Structure

```
propstats/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── populate_data.py     # Data sync utilities
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile           # Container config
│   ├── Procfile            # Heroku/Railway
│   └── railway.json        # Railway config
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Main React component
│   │   ├── main.jsx        # Entry point
│   │   └── index.css       # Tailwind styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── vercel.json         # Vercel config
│
└── README.md
```

---

## 🎨 Customization

### Change Free Tier Limits

In `backend/main.py`:
```python
FREE_LIMIT = 10  # Change to desired number
```

### Add More Stats

1. Add to `STAT_OPTIONS` in `frontend/src/App.jsx`
2. Add column mapping in `backend/main.py` `stat_map`

### Custom Styling

Edit `frontend/src/index.css` or modify Tailwind classes in components.

---

## 📄 License

MIT License - feel free to use for personal or commercial projects.

---

## 🤝 Contributing

PRs welcome! Please open an issue first to discuss changes.

---

Built with ❤️ for the sports betting community
