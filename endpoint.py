import os
import re
import json
import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

load_dotenv(override=True)

app = FastAPI(title="AgilePM Task Generator")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()



class StoryInput(BaseModel):
    title: str
    description: str
    acceptance_criteria: str


def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


@app.get("/stories/generate")
def get_story_and_generate_tasks(offset: int = Query(default=0, ge=0)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, document_no, story, description, acceptance_criteria
            FROM projectmanagement.user_stories
            WHERE deleted IS NOT TRUE
            ORDER BY created_date
            LIMIT 1 OFFSET %s
            """,
            (offset,)
        )
        row = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) FROM projectmanagement.user_stories WHERE deleted IS NOT TRUE"
        )
        total = cur.fetchone()[0]
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No story found at this offset")

    story_id, document_no, story_title, description, acceptance_criteria = row
    clean_criteria = strip_html(acceptance_criteria)
    clean_description = strip_html(description)

    prompt = f"""You are an agile project manager. Given a user story, break it down into concrete development tasks.

User Story: {story_title or ''}

Description:
{clean_description or '(no description provided)'}

Acceptance Criteria:
{clean_criteria or '(no acceptance criteria provided)'}

Return ONLY a valid JSON array of 3 to 7 tasks. Each object must have exactly these fields:
- "title": short, actionable task name (max 10 words)
- "description": one sentence explaining what needs to be done
- "estimated_days": a number (0.5, 1, 2, etc.) for how long the task will take

Example format:
[
  {{"title": "Create role detection service", "description": "Implement backend service that identifies user role on login and exposes it via API.", "estimated_days": 2}},
  {{"title": "Build help content filter", "description": "Create a component that filters help articles based on the current user role.", "estimated_days": 1}}
]

Return only the JSON array, no extra text."""

    try:
        load_dotenv(override=True)
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are an experienced agile project manager. Always respond with valid JSON only, no markdown, no extra text."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        raw_response = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)}")

    if raw_response.startswith("```"):
        raw_response = re.sub(r"^```[a-zA-Z]*\n?", "", raw_response)
        raw_response = re.sub(r"```$", "", raw_response).strip()

    try:
        tasks = json.loads(raw_response)
        if not isinstance(tasks, list):
            raise ValueError("Expected a JSON array")
        normalised = [
            {
                "title": t.get("title", ""),
                "description": t.get("description", ""),
                "estimated_days": t.get("estimated_days", 1),
            }
            for t in tasks
        ]
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"AI returned invalid JSON: {str(e)}. Raw: {raw_response[:300]}")

    return {
        "offset": offset,
        "total": total,
        "has_next": offset + 1 < total,
        "next_offset": offset + 1 if offset + 1 < total else None,
        "story": {
            "id": str(story_id),
            "document_no": document_no,
            "story": story_title,
        },
        "tasks": normalised,
        "task_count": len(normalised),
    }


@app.get("/stories")
def get_story(offset: int = Query(default=0, ge=0)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, document_no, story, description, acceptance_criteria
            FROM projectmanagement.user_stories
            WHERE deleted IS NOT TRUE
            ORDER BY created_date
            LIMIT 1 OFFSET %s
            """,
            (offset,)
        )
        row = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) FROM projectmanagement.user_stories WHERE deleted IS NOT TRUE"
        )
        total = cur.fetchone()[0]
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No story found at this offset")

    story_id, document_no, story, description, acceptance_criteria = row

    return {
        "offset": offset,
        "total": total,
        "has_next": offset + 1 < total,
        "next_offset": offset + 1 if offset + 1 < total else None,
        "story": {
            "id": str(story_id),
            "document_no": document_no,
            "story": story,
            "description": description,
            "acceptance_criteria": strip_html(acceptance_criteria),
        }
    }


@app.post("/generate-tasks")
def generate_tasks(story: StoryInput):
    prompt = f"""You are an agile project manager. Given a user story, break it down into concrete development tasks.

User Story Title: {story.title}

Description:
{story.description}

Acceptance Criteria:
{story.acceptance_criteria}

Return a numbered list of specific, actionable development tasks needed to complete this user story. Each task should be concise and clear."""

    try:
        load_dotenv(override=True)
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are an experienced agile project manager who breaks user stories into clear development tasks."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        raw_tasks = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)}")

    tasks = []
    for line in raw_tasks.splitlines():
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            task_text = line.lstrip("0123456789.-) ").strip()
            if task_text:
                tasks.append(task_text)

    return {
        "title": story.title,
        "tasks": tasks,
        "task_count": len(tasks),
    }


@app.get("/generate-tasks/{story_id}")
def generate_tasks_from_db(story_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT document_no, story, description, acceptance_criteria
            FROM projectmanagement.user_stories
            WHERE id = %s AND deleted IS NOT TRUE
            """,
            (story_id,)
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"User story '{story_id}' not found")

    document_no, story_title, description, acceptance_criteria = row
    clean_criteria = strip_html(acceptance_criteria)
    clean_description = strip_html(description)

    prompt = f"""You are an agile project manager. Given a user story, break it down into concrete development tasks.

User Story: {story_title or ''}

Description:
{clean_description or '(no description provided)'}

Acceptance Criteria:
{clean_criteria or '(no acceptance criteria provided)'}

Return ONLY a valid JSON array of task objects. Each object must have exactly these fields:
- "title": short, actionable task name (max 10 words)
- "description": one sentence explaining what needs to be done
- "estimated_days": a number (0.5, 1, 2, etc.) for how long the task will take

Example format:
[
  {{"title": "Create role detection service", "description": "Implement backend service that identifies user role on login and exposes it via API.", "estimated_days": 2}},
  {{"title": "Build help content filter", "description": "Create a component that filters help articles based on the current user role.", "estimated_days": 1}}
]

Return only the JSON array, no extra text."""

    try:
        load_dotenv(override=True)
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are an experienced agile project manager. Always respond with valid JSON only, no markdown, no extra text."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        raw_response = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)}")

    # Strip markdown code fences if the model wraps the JSON
    if raw_response.startswith("```"):
        raw_response = re.sub(r"^```[a-zA-Z]*\n?", "", raw_response)
        raw_response = re.sub(r"```$", "", raw_response).strip()

    try:
        tasks = json.loads(raw_response)
        if not isinstance(tasks, list):
            raise ValueError("Expected a JSON array")
        # Normalise each task to ensure required fields exist
        normalised = []
        for t in tasks:
            normalised.append({
                "title": t.get("title", ""),
                "description": t.get("description", ""),
                "estimated_days": t.get("estimated_days", 1),
            })
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"AI returned invalid JSON: {str(e)}. Raw: {raw_response[:300]}")

    return {
        "story_id": story_id,
        "document_no": document_no,
        "story": story_title,
        "tasks": normalised,
        "task_count": len(normalised),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
