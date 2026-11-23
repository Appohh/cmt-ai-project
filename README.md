# cmt-ai-project

Conference Management Tool: React frontend, FastAPI backend, MySQL database.

## Requirements

- Docker Desktop
- Python
- Node.js

## Getting started

**1. Environment variables**

```bash
cp .env.example .env
```

Fill in your own passwords in `.env`.

**2. Database**

```bash
docker compose up -d
```

Using TablePlus can be helpful: https://tableplus.com/

**3. Backend** → http://127.0.0.1:8000/docs

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi dev app/main.py
```

**4. Frontend** → http://localhost:5173 (in a new terminal)

```bash
cd frontend
npm install
npm run dev
```