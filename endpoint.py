import os
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

load_dotenv(override=True)

app = FastAPI(title="AgilePM Task Generator")


class StoryInput(BaseModel):
    title: str
    description: str
    acceptance_criteria: str


def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 7392)),
            dbname=os.getenv("DB_NAME", "AgilePm"),
            user=os.getenv("DB_USER", "dev"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


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

    prompt = f"""You are an agile project manager. Given a user story, break it down into concrete development tasks.

User Story: {story_title or ''}

Description:
{description or '(no description provided)'}

Acceptance Criteria:
{acceptance_criteria or '(no acceptance criteria provided)'}

Return a numbered list of specific, actionable development tasks needed to complete this user story. Each task should be concise and clear."""

    try:
        load_dotenv(override=True)
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama3-8b-8192",
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
        "story_id": story_id,
        "document_no": document_no,
        "story": story_title,
        "tasks": tasks,
        "task_count": len(tasks),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
