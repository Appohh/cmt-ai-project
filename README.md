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
alembic upgrade head
fastapi dev app/main.py
```

**After every `git pull`, run `pip install -r requirements.txt` and `alembic upgrade head` in `backend/` (venv active).**

**4. Frontend** → http://localhost:5173 (in a new terminal)

```bash
cd frontend
npm install
npm run dev
```

## Changing the database

1. Add or edit a table in `backend/app/models/models.py`
2. In `backend/` (venv active), generate a migration:

```bash
alembic revision --autogenerate -m "describe your change"
```

3. Review the new file in `alembic/versions/`
4. Run it, then commit the model and migration together:

```bash
alembic upgrade head
```

Never edit a migration that has been pushed; create a new one.

**After every `git pull`, run `pip install -r requirements.txt` and `alembic upgrade head` in `backend/` (venv active).**
