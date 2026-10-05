from pydantic import BaseModel
from typing import Optional


# ============================================================
# USER SCHEMAS
# ============================================================

class UserCreate(BaseModel):
    name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


# ============================================================
# HABIT SCHEMAS
# ============================================================

class HabitCreate(BaseModel):
    name: str
    category: str
    target: str
    user_id: int


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    target: Optional[str] = None
    status: Optional[str] = None


# ============================================================
# HABIT LOG SCHEMA
# ============================================================

class HabitLogCreate(BaseModel):
    user_id: int
    habit_id: int
    date: str
    status: str
    duration: Optional[int] = 0


# ============================================================
# AI ADVICE SCHEMA
# ============================================================

class AIAdviceRequest(BaseModel):
    user_id: Optional[int] = None
    habit_id: Optional[int] = None
    question: Optional[str] = None


# ============================================================
# AI PREDICTION SCHEMA
# ============================================================

class PredictionRequest(BaseModel):
    completion_rate: float
    missed_days: int
    current_streak: int
    frequency: int