# PropStats — Personal MLB Analysis Tool

Personal MLB prop betting and fantasy analysis tool. Local use only.

## Running locally

### Backend
```bash
cd propstats/backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend
```bash
cd propstats/frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```
