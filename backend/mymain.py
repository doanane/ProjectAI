import json
import os
import uuid
from fastapi import FastAPI, HTTPException, Cookie, Response
from typing import Optional
import httpx
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

app = FastAPI(title="AI Programming Riddle Game")


# Add this after creating your FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Riddle(BaseModel):
    question: str
    answer: str


# SIMPLIFIED - User only sends the answer, no session_id!
class AnswerRequest(BaseModel):
    answer: str


class StartResponse(BaseModel):
    question: str  # Remove session_id from response - user doesn't need to see it
    message: str = "Game started! Good luck!"


class AnswerResponse(BaseModel):
    correct: bool
    question: str | None = None  # Next question if correct
    score: int
    total_answered: int  # New: Track how many questions answered
    correct_answers: int  # New: Track correct answers count
    message: str


class ScoreResponse(BaseModel):
    score: int
    total_answered: int
    correct_answers: int
    success_rate: float  # Percentage of correct answers
    active: bool
    current_question: str | None = None


class EndResponse(BaseModel):
    final_score: int
    total_questions: int
    correct_answers: int
    success_rate: float
    message: str


game_sessions: dict = {}


async def generate_riddle() -> Riddle:
    """
    Calls AI API to generate a programming riddle.
    """
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

        # Clean the response - sometimes AI adds markdown code blocks
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        riddle_data = json.loads(raw_text)
        return Riddle(**riddle_data)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid AI response: {raw_text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/")
async def root():
    """Welcome message"""
    return {
        "message": "Welcome to AI Programming Riddle Game!",
        "instructions": {
            "start": "POST /start - Begin a new game",
            "answer": "POST /answer - Submit your answer (only need to send 'answer')",
            "score": "GET /score - Check your current progress",
            "end": "POST /end - Finish the game and see final results",
        },
    }


@app.post("/start", response_model=StartResponse)
async def start_game(response: Response):
    """
    Start a new game session and return the first riddle.
    Automatically sets a cookie with the session_id.
    """
    session_id = str(uuid.uuid4())
    riddle = await generate_riddle()

    # Initialize game session with comprehensive tracking
    game_sessions[session_id] = {
        "score": 0,
        "active": True,
        "current_riddle": riddle.dict(),
        "total_answered": 0,  # Track total questions attempted
        "correct_answers": 0,  # Track correct answers
        "questions_history": [],  # Track all questions asked
    }

    # Add first question to history
    game_sessions[session_id]["questions_history"].append(
        {
            "question": riddle.question,
            "user_answer": None,
            "correct": None,
            "correct_answer": riddle.answer,
        }
    )

    # SET COOKIE - This tells the browser to remember the session_id
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=3600 * 24,  # Cookie expires in 24 hours
        samesite="lax",
    )

    return StartResponse(question=riddle.question)


@app.post("/answer", response_model=AnswerResponse)
async def submit_answer(req: AnswerRequest, session_id: Optional[str] = Cookie(None)):
    """
    Submit an answer for the current riddle.
    User only needs to send their answer - no session_id!
    """
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="No active game session. Please POST to /start to begin a game.",
        )

    session = game_sessions.get(session_id)

    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Please POST to /start to begin a new game.",
        )

    if not session["active"]:
        raise HTTPException(
            status_code=400,
            detail="Game over! Please POST to /start to begin a new game.",
        )

    correct_answer = session["current_riddle"]["answer"].strip().lower()
    user_answer = req.answer.strip().lower()

    # Update the current question in history with user's attempt
    current_question = session["questions_history"][-1]
    current_question["user_answer"] = req.answer  # Store original answer
    current_question["correct"] = user_answer == correct_answer

    # Increment total questions answered
    session["total_answered"] += 1

    if user_answer == correct_answer:
        # Increment score and correct answers count
        session["score"] += 1
        session["correct_answers"] += 1

        # Generate new riddle for next question
        new_riddle = await generate_riddle()
        session["current_riddle"] = new_riddle.dict()

        # Add new question to history
        session["questions_history"].append(
            {
                "question": new_riddle.question,
                "user_answer": None,
                "correct": None,
                "correct_answer": new_riddle.answer,
            }
        )

        return AnswerResponse(
            correct=True,
            question=new_riddle.question,  # Send next question
            score=session["score"],
            total_answered=session["total_answered"],
            correct_answers=session["correct_answers"],
            message="✅ Correct! Here's your next riddle.",
        )
    else:
        # WRONG ANSWER - BUT GAME CONTINUES!
        # Generate new riddle so user can continue playing
        new_riddle = await generate_riddle()
        session["current_riddle"] = new_riddle.dict()

        # Add new question to history
        session["questions_history"].append(
            {
                "question": new_riddle.question,
                "user_answer": None,
                "correct": None,
                "correct_answer": new_riddle.answer,
            }
        )

        return AnswerResponse(
            correct=False,
            question=new_riddle.question,  # Still send next question!
            score=session["score"],
            total_answered=session["total_answered"],
            correct_answers=session["correct_answers"],
            message=f"❌ Wrong! The correct answer was '{correct_answer}'. But don't worry - try this next one!",
        )


@app.get("/score", response_model=ScoreResponse)
async def get_my_score(session_id: Optional[str] = Cookie(None)):
    """
    Get comprehensive score and progress for the user's session.
    """
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="No active game session. Please POST to /start to begin a game.",
        )

    session = game_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Please POST to /start to begin a new game.",
        )

    # Calculate success rate (percentage)
    success_rate = 0.0
    if session["total_answered"] > 0:
        success_rate = round(
            (session["correct_answers"] / session["total_answered"]) * 100, 2
        )

    return ScoreResponse(
        score=session["score"],
        total_answered=session["total_answered"],
        correct_answers=session["correct_answers"],
        success_rate=success_rate,
        active=session["active"],
        current_question=session["current_riddle"]["question"]
        if session["active"]
        else None,
    )


@app.get("/history")
async def get_game_history(session_id: Optional[str] = Cookie(None)):
    """
    Get complete history of all questions and answers for current session.
    """
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="No active game session. Please POST to /start to begin a game.",
        )

    session = game_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Please POST to /start to begin a new game.",
        )

    return {
        "session_id": session_id,
        "total_questions": len(session["questions_history"]),
        "questions_history": session["questions_history"],
    }


@app.post("/end", response_model=EndResponse)
async def end_game(session_id: Optional[str] = Cookie(None), response: Response = None):
    """
    End the game session voluntarily and return final results.
    Only ends when user explicitly requests it!
    """
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="No active game session. Please POST to /start to begin a game.",
        )

    session = game_sessions.get(session_id)

    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Please POST to /start to begin a new game.",
        )

    # Mark session as inactive
    session["active"] = False

    # Calculate final success rate
    success_rate = 0.0
    if session["total_answered"] > 0:
        success_rate = round(
            (session["correct_answers"] / session["total_answered"]) * 100, 2
        )

    # Clear the cookie when game ends
    if response:
        response.delete_cookie("session_id")

    return EndResponse(
        final_score=session["score"],
        total_questions=session["total_answered"],
        correct_answers=session["correct_answers"],
        success_rate=success_rate,
        message="Game ended successfully! Thanks for playing!",
    )


@app.delete("/reset")
async def reset_game(response: Response, session_id: Optional[str] = Cookie(None)):
    """
    Reset the current game session.
    """
    if session_id and session_id in game_sessions:
        del game_sessions[session_id]

    # Clear the cookie
    response.delete_cookie("session_id")

    return {"message": "Game reset successfully. Visit /start to begin a new game."}


# Debug endpoint - only for development
@app.get("/debug/session")
async def debug_session(session_id: Optional[str] = Cookie(None)):
    """Debug endpoint to see current session data"""
    return {
        "session_id": session_id,
        "session_data": game_sessions.get(session_id) if session_id else None,
    }
