from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# Auth Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    user_id: Optional[int] = None


# Game Schemas
class Riddle(BaseModel):
    question: str
    answer: str


class AnswerRequest(BaseModel):
    answer: str


class StartResponse(BaseModel):
    question: str
    message: str = "Game started! Good luck!"


class AnswerResponse(BaseModel):
    correct: bool
    question: Optional[str] = None
    score: int
    total_answered: int
    correct_answers: int
    message: str


class ScoreResponse(BaseModel):
    score: int
    total_answered: int
    correct_answers: int
    success_rate: float
    active: bool
    current_question: Optional[str] = None


class EndResponse(BaseModel):
    final_score: int
    total_questions: int
    correct_answers: int
    success_rate: float
    message: str


class UserStatsResponse(BaseModel):
    total_games_played: int
    total_questions_answered: int
    total_correct_answers: int
    highest_score: int
    overall_success_rate: float


class GameHistoryResponse(BaseModel):
    session_id: str
    score: int
    total_questions: int
    correct_answers: int
    success_rate: float
    ended_at: datetime


# OAuth Schemas
class OAuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
