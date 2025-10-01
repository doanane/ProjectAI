import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from fastapi import FastAPI, HTTPException, Depends, status, Cookie, Response
from fastapi.middleware.cors import CORSMiddleware

from database import get_db, engine, Base
from models import User, GameSession, RiddleHistory, UserStats
from schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    AnswerRequest,
    StartResponse,
    AnswerResponse,
    ScoreResponse,
    EndResponse,
    UserStatsResponse,
)
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from game_service import (
    generate_riddle,
    create_anonymous_session,
    get_anonymous_session,
    update_anonymous_session,
    anonymous_sessions,
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Programming Riddle Game")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Test database connection on startup
@app.on_event("startup")
async def startup_event():
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================


@app.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = (
        db.query(User)
        .filter((User.email == user_data.email) | (User.username == user_data.username))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_verified=True,
    )

    db.add(user)
    db.flush()

    # Create user stats
    user_stats = UserStats(user_id=user.id)
    db.add(user_stats)

    db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
        ),
    )


@app.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
        ),
    )


@app.get("/me", response_model=UserResponse)
async def get_current_user(current_user: User = Depends(get_current_active_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
    )


@app.delete("/delete-account")
async def delete_account(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Delete user account and all associated data"""
    try:
        # Delete user stats
        user_stats = (
            db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
        )
        if user_stats:
            db.delete(user_stats)

        # Delete game sessions and riddle history
        game_sessions = (
            db.query(GameSession).filter(GameSession.user_id == current_user.id).all()
        )
        for session in game_sessions:
            # Delete riddle history for this session
            riddles = (
                db.query(RiddleHistory)
                .filter(RiddleHistory.game_session_id == session.id)
                .all()
            )
            for riddle in riddles:
                db.delete(riddle)
            db.delete(session)

        # Finally delete the user
        db.delete(current_user)
        db.commit()

        return {"message": "Account and all data deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete account: {str(e)}"
        )


# ============================================================================
# ANONYMOUS GAME ENDPOINTS (No login required)
# ============================================================================


@app.post("/start", response_model=StartResponse)
async def start_game(response: Response):
    """Start a game without creating an account"""
    session_id = create_anonymous_session()
    riddle = await generate_riddle()

    # Initialize session with first riddle
    update_anonymous_session(
        session_id,
        {
            "current_riddle": {"question": riddle.question, "answer": riddle.answer},
            "questions_history": [
                {
                    "question": riddle.question,
                    "user_answer": None,
                    "correct": None,
                    "correct_answer": riddle.answer,
                }
            ],
        },
    )

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=3600 * 24,
        samesite="lax",
    )

    return StartResponse(question=riddle.question)


@app.post("/answer", response_model=AnswerResponse)
async def submit_answer(req: AnswerRequest, session_id: Optional[str] = Cookie(None)):
    if not session_id:
        raise HTTPException(status_code=400, detail="No active game session.")

    session = get_anonymous_session(session_id)
    if not session or not session.get("is_anonymous"):
        raise HTTPException(status_code=400, detail="Invalid or inactive session.")

    correct_answer = session["current_riddle"]["answer"].strip().lower()
    user_answer = req.answer.strip().lower()

    # Update stats
    session["total_answered"] += 1
    is_correct = user_answer == correct_answer

    if is_correct:
        session["score"] += 1
        session["correct_answers"] += 1

    # Generate new riddle
    new_riddle = await generate_riddle()
    session["current_riddle"] = {
        "question": new_riddle.question,
        "answer": new_riddle.answer,
    }

    # Add to history
    session["questions_history"].append(
        {
            "question": new_riddle.question,
            "user_answer": None,
            "correct": None,
            "correct_answer": new_riddle.answer,
        }
    )

    success_message = (
        "✅ Correct! Here's your next riddle."
        if is_correct
        else f"❌ Wrong! The correct answer was '{correct_answer}'. Try this next one!"
    )

    return AnswerResponse(
        correct=is_correct,
        question=new_riddle.question,
        score=session["score"],
        total_answered=session["total_answered"],
        correct_answers=session["correct_answers"],
        message=success_message,
    )


@app.get("/score", response_model=ScoreResponse)
async def get_score(session_id: Optional[str] = Cookie(None)):
    if not session_id:
        raise HTTPException(status_code=400, detail="No active game session.")

    session = get_anonymous_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Session not found.")

    # Calculate success rate
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


@app.post("/end", response_model=EndResponse)
async def end_game(session_id: Optional[str] = Cookie(None), response: Response = None):
    if not session_id:
        raise HTTPException(status_code=400, detail="No active game session.")

    session = get_anonymous_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Session not found.")

    # Mark session as inactive
    session["active"] = False

    # Calculate success rate
    success_rate = 0.0
    if session["total_answered"] > 0:
        success_rate = round(
            (session["correct_answers"] / session["total_answered"]) * 100, 2
        )

    # Clear cookie
    if response:
        response.delete_cookie("session_id")

    return EndResponse(
        final_score=session["score"],
        total_questions=session["total_answered"],
        correct_answers=session["correct_answers"],
        success_rate=success_rate,
        message="Game ended successfully! Thanks for playing!",
    )


# ============================================================================
# USER STATISTICS ENDPOINTS (Require login)
# ============================================================================


@app.get("/my-stats", response_model=UserStatsResponse)
async def get_my_stats(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    user_stats = (
        db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    )

    if not user_stats:
        user_stats = UserStats(user_id=current_user.id)
        db.add(user_stats)
        db.commit()
        db.refresh(user_stats)

    overall_success_rate = 0.0
    if user_stats.total_questions_answered > 0:
        overall_success_rate = round(
            (user_stats.total_correct_answers / user_stats.total_questions_answered)
            * 100,
            2,
        )

    return UserStatsResponse(
        total_games_played=user_stats.total_games_played,
        total_questions_answered=user_stats.total_questions_answered,
        total_correct_answers=user_stats.total_correct_answers,
        highest_score=user_stats.highest_score,
        overall_success_rate=overall_success_rate,
    )


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================


@app.get("/health")
async def health_check():
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": db_status,
        "anonymous_sessions": len(anonymous_sessions),
    }


@app.get("/")
async def root():
    return {
        "message": "🎯 AI Programming Riddle Game",
        "description": "Test your programming knowledge with AI-generated riddles!",
        "features": [
            "Play without creating an account",
            "Track your progress and statistics",
            "Create an account to save your stats",
            "AI-powered programming riddles",
        ],
        "endpoints": {
            "game": {
                "start": "POST /start",
                "answer": "POST /answer",
                "score": "GET /score",
                "end": "POST /end",
            },
            "auth": {
                "register": "POST /register",
                "login": "POST /login",
                "profile": "GET /me",
                "delete_account": "DELETE /delete-account",
            },
            "stats": {"my_stats": "GET /my-stats (requires login)"},
        },
    }
