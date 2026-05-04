# AgilePM Task Generator — AI Endpoint

A FastAPI service that uses Groq (LLaMA3) to automatically generate development tasks from AgilePM user stories.

---

## Setup

### 1. Create and activate the virtual environment
```bash
python -m venv venv
venv/Scripts/activate      # Windows
```

### 2. Install dependencies
```bash
venv/Scripts/pip install fastapi uvicorn psycopg2-binary openai python-dotenv langchain langchain-openai langchain-groq groq
```

### 3. Configure environment variables
Create a `.env` file in the project root (already included — do not commit):
```
DB_HOST=ur host 
DB_PORT=ur db port
DB_NAME=ur db name
DB_USER=ur user name
DB_PASSWORD=<password>

GROQ_API_KEY=<your_groq_api_key>
```

Get a free Groq API key at https://console.groq.com

### 4. Start the server
```bash
venv/Scripts/uvicorn endpoint:app --reload --port 8000
```

---

## Endpoints

### `GET /health`
Health check.

**Response:**
```json
{ "status": "ok" }
```

---

### `POST /generate-tasks`
Generate tasks from a manually provided user story (no DB required).

**Request body:**
```json
{
  "title": "string",
  "description": "string",
  "acceptance_criteria": "string"
}
```

**curl example:**
```bash
curl -X POST http://localhost:8000/generate-tasks \
  -H "Content-Type: application/json" \
  -d @test_body.json
```

**Response:**
```json
{
  "title": "...",
  "tasks": ["Task 1", "Task 2", "..."],
  "task_count": 10
}
```

---

### `GET /generate-tasks/{story_id}`
Pull a user story directly from the AgilePm database by its UUID and generate tasks. **Nothing is written back to the database.**

**Path parameter:** `story_id` — UUID of the user story (from `projectmanagement.user_stories.id`)

**curl example:**
```bash
curl http://localhost:8000/generate-tasks/d705c1e8-f732-451d-b962-90424b248bab
```

**Response:**
```json
{
  "story_id": "d705c1e8-f732-451d-b962-90424b248bab",
  "document_no": "UST0000001826",
  "story": "As a project manager...",
  "tasks": ["Task 1", "Task 2", "..."],
  "task_count": 12
}
```

---

## Database

| Setting  | Value            |
|----------|-----------------|
| Host     | 4.210.74.237    |
| Port     | 7392            |
| Database | AgilePm         |
| Schema   | projectmanagement |
| Table    | user_stories    |

---

## Files

| File | Purpose |
|------|---------|
| `endpoint.py` | FastAPI application |
| `.env` | DB + API credentials (not committed) |
| `test_body.json` | Sample request body for POST endpoint |
| `inspect_db.py` | Utility script for DB exploration |
| `venv/` | Python virtual environment |
