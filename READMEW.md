# cmt-ai-project

Conference Management Tool: React frontend, FastAPI backend, MySQL database.

## Requirements

- Docker Desktop (running Linux containers)
- Python 3.12
- Node.js 24 LTS (includes npm)

## Getting started

**1. Environment variables**

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Fill in your own passwords in `.env`.

**2. Database**

```powershell
docker compose up -d
```

Wait for MySQL to accept connections before starting the backend.

**3. Backend** → http://127.0.0.1:8000/docs

```powershell
cd backend
python3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\fastapi.exe dev app/main.py
```

**After every `git pull`, run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m alembic upgrade head` in `backend/`.**

**4. Frontend** → http://localhost:5173 (in a new terminal)

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

## Test data (local only)

In `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

Test users: `<role>@example.com` (author, reviewer, organizer, admin, guest), password `password`.

Reset and reseed (**deletes all data**):

```powershell
.\.venv\Scripts\python.exe -m alembic downgrade base
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
```

## Backend structure

```
backend/app/
├── main.py            # creates the app, connects the routers
├── seed.py            # local test data
├── core/              # database connection, config, security
├── models/models.py   # all database tables
├── conferences/       # example, copy this pattern
│   ├── router.py      # endpoints
│   └── schemas.py     # data the API accepts and returns
├── auth/
├── submissions/
├── reviews/
├── notifications/
└── ai/
```

New endpoints: add `router.py` and `schemas.py` to the folder, then connect the router in `main.py`.

**Why not return the model directly?** A model (`Conference`) is the database table with all columns. A schema (`ConferencePublic`) contains only the fields that may leave the API, so private data such as `password_hash` never leaks. Always set a schema as `response_model`.

## Changing the database

1. Add or edit a table in `backend/app/models/models.py`
2. In `backend/`, generate a migration:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe your change"
```

3. Review the new file in `alembic/versions/`
4. Run it, then commit the model and migration together:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Never edit a migration that has been pushed; create a new one.

**After every `git pull`, run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m alembic upgrade head` in `backend/`.**
