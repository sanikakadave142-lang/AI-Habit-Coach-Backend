from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class HabitCreate(BaseModel):
    name: str
    category: Optional[str] = None
    target: Optional[str] = None


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    target: Optional[str] = None
    status: Optional[str] = None


class HabitResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    target: Optional[str]
    status: str
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class HabitLogCreate(BaseModel):
    habit_id: int
    log_date: Optional[date] = None
    status: str = "Completed"
    duration: Optional[int] = None
    note: Optional[str] = None


class HabitLogResponse(BaseModel):
    id: int
    habit_id: int
    user_id: int
    log_date: date
    status: str
    duration: Optional[int]
    note: Optional[str]

    model_config = ConfigDict(from_attributes=True)