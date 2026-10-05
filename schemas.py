from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


# ============================================================
# USER
# ============================================================

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# HABIT
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


class HabitResponse(BaseModel):
    id: int
    name: str
    category: str
    target: str
    status: str
    user_id: int

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# HABIT LOG
# ============================================================

class HabitLogCreate(BaseModel):
    user_id: int
    habit_id: int
    date: date
    status: str
    duration: Optional[int] = 0


class HabitLogResponse(BaseModel):
    id: int
    user_id: int
    habit_id: int
    date: date
    status: str
    duration: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)