import os
import secrets
import time
from datetime import date
from typing import List

from dotenv import load_dotenv

# ============================================================
# LOAD .ENV
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# ============================================================
# FASTAPI IMPORTS
# ============================================================

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

from pydantic import BaseModel

from pwdlib import PasswordHash

from google import genai


# ============================================================
# LOCAL IMPORTS
# ============================================================

from database import Base, engine, get_db

from model import User, Habit, HabitLog

from schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    HabitCreate,
    HabitUpdate,
    HabitResponse,
    HabitLogCreate,
    HabitLogResponse
)


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="AI Habit Coach API",
    description="Backend API for AI Habit Coach Application",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# PASSWORD HASHING
# ============================================================

password_hash = PasswordHash.recommended()


# ============================================================
# GEMINI AI
# ============================================================

gemini_client = None

if GEMINI_API_KEY:

    try:

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print("Gemini client initialized successfully.")

    except Exception as e:

        print(
            "Gemini initialization error:",
            e
        )


# ============================================================
# ADMIN CONFIGURATION
# ============================================================

ADMIN_TOKENS = set()


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "success": True,
        "message": "AI Habit Coach Backend is Running",
        "version": "1.0.0"
    }


# ============================================================
# REGISTER
# ============================================================

@app.post("/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):

    existing_user = (
        db.query(User)
        .filter(
            User.email == data.email
        )
        .first()
    )

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_password = password_hash.hash(
        data.password
    )

    user = User(
        name=data.name,
        email=data.email,
        password=hashed_password
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return {
        "success": True,
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(
            User.email == data.email
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    try:

        valid_password = password_hash.verify(
            data.password,
            user.password
        )

    except Exception:

        valid_password = False

    if not valid_password:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }


# ============================================================
# CREATE HABIT
# ============================================================

@app.post(
    "/habits",
    response_model=HabitResponse
)
def create_habit(
    data: HabitCreate,
    user_id: int,
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    habit = Habit(
        name=data.name,
        category=data.category,
        target=data.target,
        status="Pending",
        user_id=user_id
    )

    db.add(habit)

    db.commit()

    db.refresh(habit)

    return habit


# ============================================================
# GET ALL HABITS OF USER
# ============================================================

@app.get(
    "/habits",
    response_model=List[HabitResponse]
)
def get_habits(
    user_id: int,
    db: Session = Depends(get_db)
):

    habits = (
        db.query(Habit)
        .filter(
            Habit.user_id == user_id
        )
        .all()
    )

    return habits


# ============================================================
# GET SINGLE HABIT
# ============================================================

@app.get(
    "/habits/{habit_id}",
    response_model=HabitResponse
)
def get_habit(
    habit_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):

    habit = (
        db.query(Habit)
        .filter(
            Habit.id == habit_id,
            Habit.user_id == user_id
        )
        .first()
    )

    if not habit:

        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    return habit


# ============================================================
# UPDATE HABIT
# ============================================================

@app.put(
    "/habits/{habit_id}",
    response_model=HabitResponse
)
def update_habit(
    habit_id: int,
    data: HabitUpdate,
    user_id: int,
    db: Session = Depends(get_db)
):

    habit = (
        db.query(Habit)
        .filter(
            Habit.id == habit_id,
            Habit.user_id == user_id
        )
        .first()
    )

    if not habit:

        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    if data.name is not None:
        habit.name = data.name

    if data.category is not None:
        habit.category = data.category

    if data.target is not None:
        habit.target = data.target

    if data.status is not None:
        habit.status = data.status

    db.commit()

    db.refresh(habit)

    return habit


# ============================================================
# DELETE HABIT
# ============================================================

@app.delete("/habits/{habit_id}")
def delete_habit(
    habit_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):

    habit = (
        db.query(Habit)
        .filter(
            Habit.id == habit_id,
            Habit.user_id == user_id
        )
        .first()
    )

    if not habit:

        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    db.delete(habit)

    db.commit()

    return {
        "success": True,
        "message": "Habit deleted successfully"
    }


# ============================================================
# CREATE HABIT LOG
# ============================================================

@app.post(
    "/habit-log",
    response_model=HabitLogResponse
)
def create_habit_log(
    data: HabitLogCreate,
    user_id: int,
    db: Session = Depends(get_db)
):

    habit = (
        db.query(Habit)
        .filter(
            Habit.id == data.habit_id,
            Habit.user_id == user_id
        )
        .first()
    )

    if not habit:

        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    log = HabitLog(
        habit_id=data.habit_id,
        user_id=user_id,
        log_date=data.log_date or date.today(),
        status=data.status,
        duration=data.duration,
        note=data.note
    )

    db.add(log)

    # Update habit status
    habit.status = data.status

    db.commit()

    db.refresh(log)

    return log


# ============================================================
# GET HABIT LOGS
# ============================================================

@app.get(
    "/habit-log",
    response_model=List[HabitLogResponse]
)
def get_habit_logs(
    user_id: int,
    db: Session = Depends(get_db)
):

    logs = (
        db.query(HabitLog)
        .filter(
            HabitLog.user_id == user_id
        )
        .order_by(
            HabitLog.log_date.desc()
        )
        .all()
    )

    return logs


# ============================================================
# PROGRESS
# ============================================================

@app.get("/progress")
def get_progress(
    user_id: int,
    db: Session = Depends(get_db)
):

    logs = (
        db.query(HabitLog)
        .filter(
            HabitLog.user_id == user_id
        )
        .all()
    )

    total_logs = len(logs)

    completed = sum(
        1
        for log in logs
        if log.status
        and log.status.lower() == "completed"
    )

    missed = sum(
        1
        for log in logs
        if log.status
        and log.status.lower() == "missed"
    )

    pending = (
        total_logs
        - completed
        - missed
    )

    if total_logs > 0:

        completion_percentage = (
            completed / total_logs
        ) * 100

    else:

        completion_percentage = 0

    return {
        "success": True,
        "user_id": user_id,
        "completed": completed,
        "missed": missed,
        "pending": pending,
        "total_logs": total_logs,
        "completion_percentage": round(
            completion_percentage,
            2
        )
    }


# ============================================================
# AI ADVICE REQUEST MODEL
# ============================================================

class AIAdviceRequest(BaseModel):

    question: str

    user_id: int | None = None


# ============================================================
# GEMINI MODELS
# ============================================================

AI_MODELS = [

    "gemini-3.8-flash",

    "gemini-3.7-flash",

    "gemini-3.6-flash",

    "gemini-3.5-flash"

]


# ============================================================
# AI ADVICE
# ============================================================

@app.post("/ai/advice")
def ai_advice(
    data: AIAdviceRequest
):

    # --------------------------------------------------------
    # CHECK GEMINI
    # --------------------------------------------------------

    if not gemini_client:

        raise HTTPException(
            status_code=500,
            detail="Gemini API is not configured"
        )


    # --------------------------------------------------------
    # CHECK QUESTION
    # --------------------------------------------------------

    if not data.question:

        raise HTTPException(
            status_code=400,
            detail="Question is required"
        )


    question = data.question.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )


    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------

    prompt = f"""
You are an AI Habit Coach.

Give simple, practical and motivating advice
to help a user build and maintain good habits.

User question:
{question}

Rules:
- Keep the answer easy to understand.
- Give practical steps.
- Be positive and supportive.
- Avoid medical diagnosis.
- Keep the answer concise.
- Use simple language.
"""


    last_error = None


    # ========================================================
    # TRY MODELS
    # ========================================================

    for model_name in AI_MODELS:

        for attempt in range(2):

            try:

                print(
                    "Trying Gemini model:",
                    model_name,
                    "Attempt:",
                    attempt + 1
                )


                response = (
                    gemini_client
                    .models
                    .generate_content(
                        model=model_name,
                        contents=prompt
                    )
                )


                advice = getattr(
                    response,
                    "text",
                    None
                )


                if advice and advice.strip():

                    print(
                        "Gemini success:",
                        model_name
                    )

                    return {
                        "success": True,
                        "question": question,
                        "advice": advice.strip(),
                        "user_id": data.user_id,
                        "model": model_name
                    }


                last_error = (
                    f"{model_name} returned "
                    "an empty response"
                )


            except Exception as e:

                last_error = str(e)

                print(
                    "Gemini error:",
                    model_name,
                    str(e)
                )


                error_text = (
                    str(e).lower()
                )


                # ------------------------------------------------
                # TEMPORARY 503 / HIGH DEMAND
                # ------------------------------------------------

                if (
                    "503" in error_text
                    or "unavailable" in error_text
                    or "high demand" in error_text
                    or "overloaded" in error_text
                ):

                    if attempt == 0:

                        time.sleep(2)

                        continue


                # Other errors:
                # move to next model

                break


    # ========================================================
    # ALL MODELS FAILED
    # ========================================================

    raise HTTPException(
        status_code=503,
        detail=(
            "AI service is temporarily unavailable. "
            "Please try again after a few seconds. "
            f"Last error: {last_error}"
        )
    )


# ============================================================
# ADMIN LOGIN MODEL
# ============================================================

class AdminLoginRequest(BaseModel):

    email: str

    password: str


# ============================================================
# ADMIN TOKEN CHECK
# ============================================================

def check_admin_token(
    x_admin_token: str | None = Header(
        default=None
    )
):

    if not x_admin_token:

        raise HTTPException(
            status_code=401,
            detail="Admin token required"
        )

    if x_admin_token not in ADMIN_TOKENS:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired admin token"
        )

    return True


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.post("/admin/login")
def admin_login(
    data: AdminLoginRequest
):

    if (
        not ADMIN_EMAIL
        or not ADMIN_PASSWORD
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                "Admin credentials are "
                "not configured in .env"
            )
        )

    if (
        data.email != ADMIN_EMAIL
        or data.password != ADMIN_PASSWORD
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid admin email or password"
        )

    token = secrets.token_urlsafe(32)

    ADMIN_TOKENS.add(token)

    return {
        "success": True,
        "message": "Admin login successful",
        "token": token
    }


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.post("/admin/logout")
def admin_logout(
    x_admin_token: str | None = Header(
        default=None
    )
):

    if x_admin_token:

        ADMIN_TOKENS.discard(
            x_admin_token
        )

    return {
        "success": True,
        "message": "Admin logout successful"
    }


# ============================================================
# ADMIN STATS
# ============================================================

@app.get("/admin/stats")
def admin_stats(
    _: bool = Depends(check_admin_token),
    db: Session = Depends(get_db)
):

    users = db.query(User).all()

    habits = db.query(Habit).all()

    logs = db.query(HabitLog).all()


    completed_habits = sum(
        1
        for habit in habits
        if habit.status
        and habit.status.lower()
        == "completed"
    )


    pending_habits = sum(
        1
        for habit in habits
        if habit.status
        and habit.status.lower()
        == "pending"
    )


    completed_logs = sum(
        1
        for log in logs
        if log.status
        and log.status.lower()
        == "completed"
    )


    missed_logs = sum(
        1
        for log in logs
        if log.status
        and log.status.lower()
        == "missed"
    )


    completion_percentage = (
        completed_logs
        / len(logs)
        * 100
        if logs
        else 0
    )


    return {

        "success": True,

        "total_users": len(users),

        "total_habits": len(habits),

        "completed_habits":
            completed_habits,

        "pending_habits":
            pending_habits,

        "total_logs": len(logs),

        "completed_logs":
            completed_logs,

        "missed_logs":
            missed_logs,

        "completion_percentage":
            round(
                completion_percentage,
                2
            )
    }


# ============================================================
# ADMIN - ALL USERS
# ============================================================

@app.get("/admin/users")
def admin_users(
    _: bool = Depends(check_admin_token),
    db: Session = Depends(get_db)
):

    users = (
        db.query(User)
        .order_by(
            User.id.desc()
        )
        .all()
    )


    result = []


    for user in users:

        habits = (
            db.query(Habit)
            .filter(
                Habit.user_id == user.id
            )
            .all()
        )


        logs = (
            db.query(HabitLog)
            .filter(
                HabitLog.user_id == user.id
            )
            .all()
        )


        completed_habits = sum(
            1
            for habit in habits
            if habit.status
            and habit.status.lower()
            == "completed"
        )


        pending_habits = sum(
            1
            for habit in habits
            if habit.status
            and habit.status.lower()
            == "pending"
        )


        completed_logs = sum(
            1
            for log in logs
            if log.status
            and log.status.lower()
            == "completed"
        )


        missed_logs = sum(
            1
            for log in logs
            if log.status
            and log.status.lower()
            == "missed"
        )


        completion_percentage = (

            completed_logs
            / len(logs)
            * 100

            if logs

            else 0
        )


        habit_data = []


        for habit in habits:

            habit_data.append({

                "id": habit.id,

                "name": habit.name,

                "category":
                    habit.category,

                "target":
                    habit.target,

                "status":
                    habit.status
            })


        log_data = []


        for log in logs:

            habit = (
                db.query(Habit)
                .filter(
                    Habit.id
                    == log.habit_id
                )
                .first()
            )


            log_data.append({

                "id": log.id,

                "habit_id":
                    log.habit_id,

                "habit_name": (
                    habit.name
                    if habit
                    else "Unknown"
                ),

                "log_date": (
                    str(log.log_date)
                    if log.log_date
                    else None
                ),

                "status":
                    log.status,

                "duration":
                    log.duration,

                "note":
                    log.note
            })


        result.append({

            "user_id":
                user.id,

            "name":
                user.name,

            "email":
                user.email,

            "total_habits":
                len(habits),

            "completed_habits":
                completed_habits,

            "pending_habits":
                pending_habits,

            "total_logs":
                len(logs),

            "completed_logs":
                completed_logs,

            "missed_logs":
                missed_logs,

            "completion_percentage":
                round(
                    completion_percentage,
                    2
                ),

            "habits":
                habit_data,

            "logs":
                log_data
        })


    return {

        "success": True,

        "total_users":
            len(result),

        "users":
            result
    }


# ============================================================
# ADMIN - SINGLE USER DETAILS
# ============================================================

@app.get(
    "/admin/users/{user_id}"
)
def admin_user_details(
    user_id: int,
    _: bool = Depends(check_admin_token),
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )


    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


    habits = (
        db.query(Habit)
        .filter(
            Habit.user_id == user_id
        )
        .all()
    )


    logs = (
        db.query(HabitLog)
        .filter(
            HabitLog.user_id == user_id
        )
        .all()
    )


    return {

        "success": True,

        "user": {

            "id":
                user.id,

            "name":
                user.name,

            "email":
                user.email
        },


        "habits": [

            {

                "id":
                    habit.id,

                "name":
                    habit.name,

                "category":
                    habit.category,

                "target":
                    habit.target,

                "status":
                    habit.status

            }

            for habit in habits
        ],


        "logs": [

            {

                "id":
                    log.id,

                "habit_id":
                    log.habit_id,

                "log_date":
                    str(log.log_date),

                "status":
                    log.status,

                "duration":
                    log.duration,

                "note":
                    log.note

            }

            for log in logs
        ]
    }


# ============================================================
# SERVER START MESSAGE
# ============================================================

print(
    "=========================================="
)

print(
    " AI HABIT COACH BACKEND"
)

print(
    "=========================================="
)

print(
    "Environment file:",
    ENV_PATH
)

print(
    "Admin email loaded:",
    bool(ADMIN_EMAIL)
)

print(
    "Admin password loaded:",
    bool(ADMIN_PASSWORD)
)

print(
    "Gemini API loaded:",
    bool(GEMINI_API_KEY)
)

print(
    "=========================================="
)