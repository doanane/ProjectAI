# from fastapi import FastAPI
# from uuid import UUID
# from pydantic import BaseModel, Field
# # from typing import List, Optional
# # import httpx


# app = FastAPI(
#     title="AI Programming Riddle Game",
#     description="A game where AI generates programming riddles for you to solve!",
#     version="1.0.0",
# )

# # print("FastAPI Riddle Game Server Starting Up...")


# class Riddle(BaseModel):
#     question: str = Field(max_length=255)
#     answer: str = Field(max_length=255)


# class AnswerSubmission(BaseModel):
#     session_id: UUID
#     answer: str = Field(max_length=255)


# class GameSession(BaseModel):
#     session_id: UUID
#     # riddles: List[Riddle]
#     current_riddle_index: int = 0
#     score: int = 0
#     active: bool = True


# @app.get("/")
# def session():
#     return {"message": "Welcome to the AI Programming Riddle Game!"}


# @app.post("/start_session", response_model=GameSession)
# def start_session():
#     # Logic to create a new game session
#     pass


# app/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
import os
import json
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("❌ OPENAI_API_KEY not found in .env")

app = FastAPI(title="AI Programming Riddle Game")


class Riddle(BaseModel):
    question: str
    answer: str


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class StartResponse(BaseModel):
    session_id: str
    question: str


class AnswerResponse(BaseModel):
    correct: bool
    question: str | None = None
    score: int
    message: str


class EndResponse(BaseModel):
    session_id: str
    final_score: int
    message: str


# ----------------------------
# Game Sessions (in-memory)
# ----------------------------
game_sessions: dict = {}

# ----------------------------
# AI Riddle Generator (via httpx)
# ----------------------------


async def generate_riddle() -> Riddle:
    """
    Calls OpenAI API using httpx to generate a programming riddle.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AI API error: {resp.text}")

        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"].strip()

    try:
        riddle_data = json.loads(raw_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid AI response: {raw_text}")

    return Riddle(**riddle_data)


# ----------------------------
# API Endpoints
# ----------------------------


@app.post("/start", response_model=StartResponse)
async def start_game():
    """
    Start a new game session and return the first riddle.
    """
    session_id = str(uuid.uuid4())
    riddle = await generate_riddle()

    game_sessions[session_id] = {
        "score": 0,
        "active": True,
        "current_riddle": riddle.dict(),
    }

    return StartResponse(session_id=session_id, question=riddle.question)


@app.post("/answer", response_model=AnswerResponse)
async def submit_answer(req: AnswerRequest):
    """
    Submit an answer for the current riddle.
    """
    session = game_sessions.get(req.session_id)

    if not session or not session["active"]:
        raise HTTPException(status_code=400, detail="Invalid or inactive session.")

    correct_answer = session["current_riddle"]["answer"].strip().lower()
    user_answer = req.answer.strip().lower()

    if user_answer == correct_answer:
        session["score"] += 1
        new_riddle = await generate_riddle()
        session["current_riddle"] = new_riddle.dict()

        return AnswerResponse(
            correct=True,
            question=new_riddle.question,
            score=session["score"],
            message="✅ Correct! Here's your next riddle.",
        )
    else:
        session["active"] = False
        return AnswerResponse(
            correct=False,
            score=session["score"],
            message=f"❌ Wrong! The correct answer was '{correct_answer}'. Game Over.",
        )


@app.post("/end", response_model=EndResponse)
async def end_game(req: AnswerRequest):
    """
    End the game session and return the final score.
    """
    session = game_sessions.get(req.session_id)

    if not session:
        raise HTTPException(status_code=400, detail="Invalid session.")

    session["active"] = False
    return EndResponse(
        session_id=req.session_id,
        final_score=session["score"],
        message="Game ended successfully.",
    )
