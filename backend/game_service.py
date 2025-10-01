import json
import os
import uuid
from typing import Dict, Any
import httpx
from dotenv import load_dotenv
from fastapi import HTTPException
from schemas import Riddle

load_dotenv()

# In-memory storage for anonymous games
anonymous_sessions: Dict[str, Any] = {}


async def generate_riddle() -> Riddle:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    url = "https://ai-api.amalitech-dev.net/api/v2/"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Provider": "openai",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a programming riddle generator."},
            {
                "role": "user",
                "content": """
Generate a short programming riddle in strict JSON format:
{
  "question": "...",
  "answer": "..."
}
The 'answer' must be only 1-3 words. No explanation, no extra text.
""",
            },
        ],
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=body, timeout=30.0)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=500, detail=f"AI API error: {resp.text}"
                )

            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"].strip()

        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        riddle_data = json.loads(raw_text)
        return Riddle(**riddle_data)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid AI response: {raw_text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


def create_anonymous_session() -> str:
    session_id = str(uuid.uuid4())
    anonymous_sessions[session_id] = {
        "score": 0,
        "active": True,
        "current_riddle": None,
        "total_answered": 0,
        "correct_answers": 0,
        "questions_history": [],
        "is_anonymous": True,
    }
    return session_id


def get_anonymous_session(session_id: str):
    return anonymous_sessions.get(session_id)


def update_anonymous_session(session_id: str, updates: dict):
    if session_id in anonymous_sessions:
        anonymous_sessions[session_id].update(updates)
        return True
    return False


def delete_anonymous_session(session_id: str):
    if session_id in anonymous_sessions:
        del anonymous_sessions[session_id]
        return True
    return False
