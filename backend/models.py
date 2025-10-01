from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(200))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # OAuth fields
    provider = Column(String(50), default="email")  # email, google, github, etc.
    provider_id = Column(String(255), unique=True, index=True)

    # Relationships
    game_sessions = relationship("GameSession", back_populates="user")
    user_stats = relationship("UserStats", back_populates="user", uselist=False)


class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(255), unique=True, index=True)
    score = Column(Integer, default=0)
    total_answered = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    current_riddle = Column(Text)  # Store as JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="game_sessions")
    riddles_history = relationship("RiddleHistory", back_populates="game_session")


class RiddleHistory(Base):
    __tablename__ = "riddles_history"

    id = Column(Integer, primary_key=True, index=True)
    game_session_id = Column(Integer, ForeignKey("game_sessions.id"))
    question = Column(Text, nullable=False)
    user_answer = Column(Text)
    correct_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean)
    asked_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game_session = relationship("GameSession", back_populates="riddles_history")


class UserStats(Base):
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    total_games_played = Column(Integer, default=0)
    total_questions_answered = Column(Integer, default=0)
    total_correct_answers = Column(Integer, default=0)
    highest_score = Column(Integer, default=0)
    total_play_time_seconds = Column(Integer, default=0)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="user_stats")
