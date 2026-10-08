import os
import secrets
import time
import sqlite3
from datetime import date
from rag_engine import search_knowledge

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# SQLITE DEMO DATABASE
# ============================================================

SQLITE_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "habit.db"
)


def sqlite_connection():
    return sqlite3.connect(SQLITE_DB)


def create_sqlite_tables():
    conn = sqlite_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            target TEXT,
            status TEXT,
            user_id INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            habit_id INTEGER,
            log_date TEXT,
            status TEXT,
            duration INTEGER,
            note TEXT,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()


def sync_user_to_sqlite(user):

    create_sqlite_tables()

    conn = sqlite_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO users
        (id, name, email, password)
        VALUES (?, ?, ?, ?)
    """, (
        user.id,
        user.name,
        user.email,
        user.password
    ))

    conn.commit()
    conn.close()


def sync_habit_to_sqlite(habit):

    create_sqlite_tables()

    conn = sqlite_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO habits
        (id, name, category, target, status, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        habit.id,
        habit.name,
        habit.category,
        habit.target,
        habit.status,
        habit.user_id
    ))

    conn.commit()
    conn.close()


def ensure_sqlite_tables():

    conn = sqlite_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            target TEXT,
            status TEXT,
            user_id INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            habit_id INTEGER,
            log_date TEXT,
            status TEXT,
            duration INTEGER,
            note TEXT,
            date TEXT
        )
    """)

    cur.execute("PRAGMA table_info(habit_logs)")

    columns = {
        row[1]
        for row in cur.fetchall()
    }

    if "user_id" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN user_id INTEGER"
        )

    if "habit_id" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN habit_id INTEGER"
        )

    if "log_date" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN log_date TEXT"
        )

    if "status" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN status TEXT"
        )

    if "duration" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN duration INTEGER DEFAULT 0"
        )

    if "note" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN note TEXT"
        )

    if "date" not in columns:
        cur.execute(
            "ALTER TABLE habit_logs ADD COLUMN date TEXT"
        )

    conn.commit()
    conn.close()


def sync_log_to_sqlite(log):

    ensure_sqlite_tables()

    conn = sqlite_connection()
    cur = conn.cursor()

    log_date_value = getattr(
        log,
        "log_date",
        None
    )

    date_value = getattr(
        log,
        "date",
        None
    )

    if log_date_value is None:
        log_date_value = date_value

    cur.execute("""
        INSERT OR REPLACE INTO habit_logs
        (
            id,
            user_id,
            habit_id,
            log_date,
            status,
            duration,
            note,
            date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log.id,
        log.user_id,
        log.habit_id,
        str(log_date_value)
        if log_date_value is not None
        else "",
        log.status,
        log.duration
        if log.duration is not None
        else 0,
        getattr(log, "note", "") or "",
        str(date_value)
        if date_value is not None
        else ""
    ))

    conn.commit()
    conn.close()


def sync_all_to_sqlite():

    conn = None
    db = None

    try:

        ensure_sqlite_tables()

        db = SessionLocal()

        users = db.query(
            model.User
        ).all()

        habits = db.query(
            model.Habit
        ).all()

        logs = db.query(
            model.HabitLog
        ).all()

        conn = sqlite_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM users")
        cur.execute("DELETE FROM habits")
        cur.execute("DELETE FROM habit_logs")

        conn.commit()

        conn.close()
        conn = None

        for user in users:
            sync_user_to_sqlite(user)

        for habit in habits:
            sync_habit_to_sqlite(habit)

        for log in logs:
            sync_log_to_sqlite(log)

        print(
            f"SQLite sync completed: "
            f"{len(users)} users, "
            f"{len(habits)} habits, "
            f"{len(logs)} habit logs"
        )

    except Exception as e:

        print(
            "SQLite sync error:",
            str(e)
        )

    finally:

        if conn is not None:
            conn.close()

        if db is not None:
            db.close()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD"
)


# ============================================================
# FASTAPI
# ============================================================

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Header
)

from fastapi.middleware.cors import (
    CORSMiddleware
)


# ============================================================
# DATABASE
# ============================================================

from sqlalchemy.orm import Session
from sqlalchemy import text

from database import (
    SessionLocal,
    engine
)

import model
import schemas


# ============================================================
# DATABASE MIGRATION
# ============================================================

def migrate_database():

    try:

        print(
            "Checking SQLite database migration..."
        )

        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name = 'habit_logs'
                """)
            )

            table_exists = result.fetchone()

            # ------------------------------------------------
            # CREATE TABLE IF NOT EXISTS
            # ------------------------------------------------

            if not table_exists:

                print(
                    "Creating habit_logs table..."
                )

                conn.execute(
                    text("""
                        CREATE TABLE habit_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            habit_id INTEGER,
                            log_date TEXT,
                            status TEXT,
                            duration INTEGER DEFAULT 0,
                            note TEXT,
                            date TEXT
                        )
                    """)
                )

                print(
                    "habit_logs table created successfully"
                )

            # ------------------------------------------------
            # CHECK EXISTING TABLE
            # ------------------------------------------------

            else:

                result = conn.execute(
                    text(
                        "PRAGMA table_info(habit_logs)"
                    )
                )

                columns = {
                    row[1]
                    for row in result.fetchall()
                }

                print(
                    "Existing habit_logs columns:",
                    columns
                )

                if "user_id" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN user_id INTEGER
                        """)
                    )

                if "habit_id" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN habit_id INTEGER
                        """)
                    )

                if "log_date" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN log_date TEXT
                        """)
                    )

                if "status" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN status TEXT
                        """)
                    )

                if "duration" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN duration INTEGER DEFAULT 0
                        """)
                    )

                if "note" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN note TEXT
                        """)
                    )

                if "date" not in columns:

                    conn.execute(
                        text("""
                            ALTER TABLE habit_logs
                            ADD COLUMN date TEXT
                        """)
                    )

        print(
            "DATABASE MIGRATION COMPLETED"
        )

    except Exception as e:

        print(
            "DATABASE MIGRATION ERROR:",
            str(e)
        )


# ============================================================
# RUN DATABASE MIGRATION
# ============================================================

migrate_database()


# ============================================================
# CREATE TABLES
# ============================================================

try:

    model.Base.metadata.create_all(
        bind=engine
    )

    print(
        "DATABASE TABLES READY"
    )

    sync_all_to_sqlite()

except Exception as e:

    print(
        "DATABASE TABLE CREATION ERROR:",
        str(e)
    )


# ============================================================
# PASSWORD HASHING
# ============================================================

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str):

    return password_hash.hash(
        password
    )


def verify_password(
    password: str,
    hashed_password: str
):

    try:

        return password_hash.verify(
            password,
            hashed_password
        )

    except Exception:

        return False


# ============================================================
# GEMINI
# ============================================================

from google import genai

gemini_client = None

if GEMINI_API_KEY:

    try:

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print(
            "Gemini API loaded: True"
        )

    except Exception as e:

        print(
            "Gemini initialization error:",
            str(e)
        )

else:

    print(
        "Gemini API loaded: False"
    )


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="AI Habit Coach API",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=False,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()


# ============================================================
# ADMIN TOKENS
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
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    try:

        existing_user = (
            db.query(model.User)
            .filter(
                model.User.email == user.email
            )
            .first()
        )

        if existing_user:

            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        new_user = model.User(
            name=user.name,
            email=user.email,
            password=hash_password(
                user.password
            )
        )

        db.add(new_user)

        db.commit()

        db.refresh(new_user)

        sync_user_to_sqlite(
            new_user
        )

        return {
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": new_user.id,
                "name": new_user.name,
                "email": new_user.email
            }
        }

    except HTTPException:

        raise

    except Exception as e:

        db.rollback()

        print(
            "REGISTER ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Registration failed"
        )


# ============================================================
# LOGIN
# ============================================================

@app.post("/login")
def login(
    user: schemas.UserLogin,
    db: Session = Depends(get_db)
):

    existing_user = (
        db.query(model.User)
        .filter(
            model.User.email == user.email
        )
        .first()
    )

    if not existing_user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        user.password,
        existing_user.password
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {
        "success": True,
        "message": "Login successful",
        "user": {
            "id": existing_user.id,
            "name": existing_user.name,
            "email": existing_user.email
        }
    }


# ============================================================
# ADD HABIT
# ============================================================

@app.post("/habits")
def add_habit(
    habit: schemas.HabitCreate,
    db: Session = Depends(get_db)
):

    try:

        user = (
            db.query(model.User)
            .filter(
                model.User.id == habit.user_id
            )
            .first()
        )

        if not user:

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        new_habit = model.Habit(
            name=habit.name,
            category=habit.category,
            target=habit.target,
            status="Pending",
            user_id=habit.user_id
        )

        db.add(new_habit)

        db.commit()

        db.refresh(new_habit)

        sync_habit_to_sqlite(
            new_habit
        )

        return {
            "success": True,
            "message": "Habit added successfully",
            "habit": {
                "id": new_habit.id,
                "name": new_habit.name,
                "category": new_habit.category,
                "target": new_habit.target,
                "status": new_habit.status,
                "user_id": new_habit.user_id
            }
        }

    except HTTPException:

        raise

    except Exception as e:

        db.rollback()

        print(
            "ADD HABIT ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to add habit"
        )


# ============================================================
# GET HABITS
# ============================================================

@app.get("/habits")
def get_habits(
    user_id: int,
    db: Session = Depends(get_db)
):

    try:

        habits = (
            db.query(model.Habit)
            .filter(
                model.Habit.user_id == user_id
            )
            .all()
        )

        return {
            "success": True,
            "habits": [
                {
                    "id": habit.id,
                    "name": habit.name,
                    "category": habit.category,
                    "target": habit.target,
                    "status": habit.status,
                    "user_id": habit.user_id
                }
                for habit in habits
            ]
        }

    except Exception as e:

        print(
            "GET HABITS ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to get habits"
        )


# ============================================================
# UPDATE HABIT
# ============================================================

@app.put("/habits/{habit_id}")
def update_habit(
    habit_id: int,
    habit_data: schemas.HabitUpdate,
    db: Session = Depends(get_db)
):

    habit = (
        db.query(model.Habit)
        .filter(
            model.Habit.id == habit_id
        )
        .first()
    )

    if not habit:

        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    if habit_data.name is not None:
        habit.name = habit_data.name

    if habit_data.category is not None:
        habit.category = habit_data.category

    if habit_data.target is not None:
        habit.target = habit_data.target

    if habit_data.status is not None:
        habit.status = habit_data.status

    db.commit()

    db.refresh(habit)

    sync_habit_to_sqlite(
        habit
    )

    return {
        "success": True,
        "message": "Habit updated successfully",
        "habit": {
            "id": habit.id,
            "name": habit.name,
            "category": habit.category,
            "target": habit.target,
            "status": habit.status,
            "user_id": habit.user_id
        }
    }


# ============================================================
# DELETE HABIT
# ============================================================

@app.delete("/habits/{habit_id}")
def delete_habit(
    habit_id: int,
    db: Session = Depends(get_db)
):

    habit = (
        db.query(model.Habit)
        .filter(
            model.Habit.id == habit_id
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

    sync_all_to_sqlite()

    return {
        "success": True,
        "message": "Habit deleted successfully"
    }


# ============================================================
# ADD HABIT LOG
# ============================================================

@app.post("/habit-log")
def add_habit_log(
    log: schemas.HabitLogCreate,
    db: Session = Depends(get_db)
):

    try:

        print(
            "HABIT LOG REQUEST:",
            log.model_dump()
        )

        # ------------------------------------------------
        # CHECK USER
        # ------------------------------------------------

        user = (
            db.query(model.User)
            .filter(
                model.User.id == log.user_id
            )
            .first()
        )

        if not user:

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # ------------------------------------------------
        # CHECK HABIT
        # ------------------------------------------------

        habit = (
            db.query(model.Habit)
            .filter(
                model.Habit.id == log.habit_id,
                model.Habit.user_id == log.user_id
            )
            .first()
        )

        if not habit:

            raise HTTPException(
                status_code=404,
                detail="Habit not found for this user"
            )

        # ------------------------------------------------
        # DATE
        # ------------------------------------------------

        log_date = str(
            log.date
        )

        # ------------------------------------------------
        # ENSURE TABLE AND COLUMNS EXIST
        # ------------------------------------------------

        ensure_sqlite_tables()

        # ------------------------------------------------
        # INSERT HABIT LOG
        # ------------------------------------------------

        db.execute(
            text("""
                INSERT INTO habit_logs
                (
                    user_id,
                    habit_id,
                    log_date,
                    status,
                    duration,
                    note,
                    date
                )
                VALUES
                (
                    :user_id,
                    :habit_id,
                    :log_date,
                    :status,
                    :duration,
                    :note,
                    :date
                )
            """),
            {
                "user_id": log.user_id,
                "habit_id": log.habit_id,
                "log_date": log_date,
                "status": log.status,
                "duration": (
                    log.duration
                    if log.duration is not None
                    else 0
                ),
                "note": "",
                "date": log_date
            }
        )

        # ------------------------------------------------
        # UPDATE HABIT STATUS
        # ------------------------------------------------

        if log.status.lower() == "completed":

            habit.status = "Completed"

        db.commit()

        print(
            "HABIT LOG SAVED SUCCESSFULLY"
        )

        return {
            "success": True,
            "message": "Habit log added successfully",
            "log": {
                "user_id": log.user_id,
                "habit_id": log.habit_id,
                "date": log_date,
                "status": log.status,
                "duration": (
                    log.duration
                    if log.duration is not None
                    else 0
                )
            }
        }

    except HTTPException:

        raise

    except Exception as e:

        db.rollback()

        print(
            "HABIT LOG DATABASE ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Database error while saving habit log"
        )


# ============================================================
# GET HABIT LOG
# ============================================================

@app.get("/habit-log")
def get_habit_logs(
    user_id: int,
    db: Session = Depends(get_db)
):

    try:

        logs = (
            db.query(model.HabitLog)
            .filter(
                model.HabitLog.user_id == user_id
            )
            .order_by(
                model.HabitLog.id.desc()
            )
            .all()
        )

        return {
            "success": True,
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "habit_id": log.habit_id,
                    "date": str(log.date),
                    "status": log.status,
                    "duration": (
                        log.duration
                        if log.duration is not None
                        else 0
                    )
                }
                for log in logs
            ]
        }

    except Exception as e:

        print(
            "GET HABIT LOG ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to get habit logs"
        )


# ============================================================
# PROGRESS
# ============================================================

@app.get("/progress")
def get_progress(
    user_id: int,
    db: Session = Depends(get_db)
):

    logs = (
        db.query(model.HabitLog)
        .filter(
            model.HabitLog.user_id == user_id
        )
        .all()
    )

    total_logs = len(logs)

    completed = sum(
        1
        for log in logs
        if str(log.status).lower()
        == "completed"
    )

    missed = sum(
        1
        for log in logs
        if str(log.status).lower()
        == "missed"
    )

    completion_percentage = (
        round(
            (
                completed /
                total_logs
            ) * 100,
            2
        )
        if total_logs > 0
        else 0
    )

    return {
        "success": True,
        "completed": completed,
        "total_logs": total_logs,
        "completion_percentage":
            completion_percentage,
        "missed": missed
    }


# ============================================================
# AI FALLBACK
# ============================================================

def get_fallback_advice(
    question: str
):

    q = question.lower()

    if any(
        word in q
        for word in [
            "study",
            "exam",
            "college",
            "education",
            "learn"
        ]
    ):

        return (
            "Create a simple study routine and "
            "focus on one task at a time. "
            "Study for 25 to 30 minutes, "
            "take a short break, and continue. "
            "Track your progress every day."
        )

    if any(
        word in q
        for word in [
            "exercise",
            "workout",
            "fitness",
            "gym"
        ]
    ):

        return (
            "Start with a realistic daily exercise goal. "
            "Even 20 to 30 minutes of walking "
            "or exercise is useful. "
            "Increase your activity gradually."
        )

    if any(
        word in q
        for word in [
            "sleep",
            "rest",
            "routine"
        ]
    ):

        return (
            "Maintain a consistent sleep and daily routine. "
            "Try to sleep and wake up at similar times "
            "every day."
        )

    if any(
        word in q
        for word in [
            "water",
            "drink"
        ]
    ):

        return (
            "Keep a simple water reminder throughout "
            "the day and drink water regularly."
        )

    return (
        "Start with a small and realistic habit. "
        "Set a clear daily goal, track your progress, "
        "and focus on consistency. "
        "If you miss one day, start again the next day."
    )


# ============================================================
# AI ADVICE REQUEST
# ============================================================

class AIAdviceRequest(
    schemas.BaseModel
):

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
    request: AIAdviceRequest
):

    question = request.question.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question is required"
        )

    fallback = get_fallback_advice(
        question
    )

    if gemini_client is None:

        return {
            "success": True,
            "question": question,
            "advice": fallback,
            "user_id": request.user_id,
            "model": "fallback",
            "source": "Habit Coach"
        }

    prompt = f"""
You are an AI Habit Coach.

Give short, practical, positive advice
in simple language.

Answer in 2-3 sentences.

User question:
{question}

Do not give dangerous medical advice.
"""

    for model_name in AI_MODELS:

        try:

            response = (
                gemini_client
                .models
                .generate_content(
                    model=model_name,
                    contents=prompt
                )
            )

            if response and response.text:

                return {
                    "success": True,
                    "question": question,
                    "advice":
                        response.text.strip(),
                    "user_id":
                        request.user_id,
                    "model":
                        model_name,
                    "source":
                        "Gemini AI"
                }

        except Exception as e:

            error_text = str(e).lower()

            print(
                f"Gemini error "
                f"({model_name}):",
                str(e)
            )

            if any(
                word in error_text
                for word in [
                    "429",
                    "quota",
                    "resource_exhausted",
                    "rate limit"
                ]
            ):

                break

            if any(
                word in error_text
                for word in [
                    "503",
                    "unavailable",
                    "overloaded",
                    "high demand"
                ]
            ):

                time.sleep(1)

                continue

            continue

    return {
        "success": True,
        "question": question,
        "advice": fallback,
        "user_id": request.user_id,
        "model": "fallback",
        "source": "Habit Coach"
    }


# ============================================================
# AI PREDICTION
# ============================================================

@app.post("/ai/predict")
def ai_predict(
    data: dict
):

    completion_rate = float(
        data.get(
            "completion_rate",
            0
        )
    )

    missed_days = int(
        data.get(
            "missed_days",
            0
        )
    )

    current_streak = int(
        data.get(
            "current_streak",
            0
        )
    )

    frequency = int(
        data.get(
            "frequency",
            7
        )
    )

    if (
        completion_rate >= 80
        and current_streak >= 5
    ):

        prediction = (
            "Likely to Complete"
        )

        confidence = 100.0

        recommendation = (
            "Keep following your "
            "current habit routine."
        )

    elif completion_rate >= 60:

        prediction = (
            "Moderately Likely to Complete"
        )

        confidence = 80.0

        recommendation = (
            "Maintain a regular routine "
            "and reduce missed days."
        )

    else:

        prediction = (
            "Needs Improvement"
        )

        confidence = 70.0

        recommendation = (
            "Start with a smaller goal "
            "and focus on consistency."
        )

    return {
        "success": True,
        "prediction": prediction,
        "confidence": confidence,
        "recommendation": recommendation,
        "completion_rate": completion_rate,
        "missed_days": missed_days,
        "current_streak": current_streak,
        "frequency": frequency
    }


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.post("/admin/login")
def admin_login(
    data: dict
):

    email = data.get(
        "email"
    )

    password = data.get(
        "password"
    )

    if (
        not ADMIN_EMAIL
        or not ADMIN_PASSWORD
    ):

        raise HTTPException(
            status_code=500,
            detail="Admin credentials are not configured"
        )

    if (
        email != ADMIN_EMAIL
        or password != ADMIN_PASSWORD
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials"
        )

    token = secrets.token_hex(
        32
    )

    ADMIN_TOKENS.add(
        token
    )

    return {
        "success": True,
        "message":
            "Admin login successful",
        "token": token
    }


# ============================================================
# ADMIN TOKEN VERIFY
# ============================================================

def verify_admin_token(
    token: str
):

    if not token:

        raise HTTPException(
            status_code=401,
            detail="Admin token required"
        )

    if token not in ADMIN_TOKENS:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired admin token"
        )

    return True


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.post("/admin/logout")
def admin_logout(
    data: dict
):

    token = data.get(
        "token"
    )

    if token in ADMIN_TOKENS:

        ADMIN_TOKENS.remove(
            token
        )

    return {
        "success": True,
        "message":
            "Admin logout successful"
    }


# ============================================================
# ADMIN STATS
# ============================================================

@app.get("/admin/stats")
def admin_stats(

    token: str = Header(
        None,
        alias="X-Admin-Token"
    ),

    db: Session = Depends(
        get_db
    )
):

    verify_admin_token(
        token
    )

    users_count = (
        db.query(
            model.User
        ).count()
    )

    habits_count = (
        db.query(
            model.Habit
        ).count()
    )

    logs_count = (
        db.query(
            model.HabitLog
        ).count()
    )

    completed_count = (
        db.query(
            model.HabitLog
        )
        .filter(
            model.HabitLog.status
            == "Completed"
        )
        .count()
    )

    return {
        "success": True,
        "users": users_count,
        "habits": habits_count,
        "habit_logs": logs_count,
        "completed": completed_count
    }


# ============================================================
# ADMIN USERS
# ============================================================

@app.get("/admin/users")
def admin_users(

    token: str = Header(
        None,
        alias="X-Admin-Token"
    ),

    db: Session = Depends(
        get_db
    )
):

    verify_admin_token(
        token
    )

    users = (
        db.query(
            model.User
        ).all()
    )

    result = []

    for user in users:

        habits = (
            db.query(
                model.Habit
            )
            .filter(
                model.Habit.user_id
                == user.id
            )
            .all()
        )

        result.append({

            "id": user.id,

            "name": user.name,

            "email": user.email,

            "habits": [

                {
                    "id": habit.id,
                    "name": habit.name,
                    "category": habit.category,
                    "target": habit.target,
                    "status": habit.status,
                    "user_id": habit.user_id
                }

                for habit in habits
            ]
        })

    return {
        "success": True,
        "users": result
    }


# ============================================================
# ADMIN DELETE USER
# ============================================================

@app.delete("/admin/users/{user_id}")
def admin_delete_user(

    user_id: int,

    token: str = Header(
        None,
        alias="X-Admin-Token"
    ),

    db: Session = Depends(
        get_db
    )
):

    verify_admin_token(
        token
    )

    user = (
        db.query(
            model.User
        )
        .filter(
            model.User.id == user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    db.query(
        model.HabitLog
    ).filter(
        model.HabitLog.user_id
        == user_id
    ).delete(
        synchronize_session=False
    )

    db.query(
        model.Habit
    ).filter(
        model.Habit.user_id
        == user_id
    ).delete(
        synchronize_session=False
    )

    db.delete(
        user
    )

    db.commit()

    sync_all_to_sqlite()

    return {
        "success": True,
        "message":
            "User deleted successfully",
        "user_id": user_id
    }


# ============================================================
# ADMIN USER DETAILS
# ============================================================

@app.get("/admin/users/{user_id}")
def admin_user_details(

    user_id: int,

    token: str = Header(
        None,
        alias="X-Admin-Token"
    ),

    db: Session = Depends(
        get_db
    )
):

    verify_admin_token(
        token
    )

    user = (
        db.query(
            model.User
        )
        .filter(
            model.User.id == user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    habits = (
        db.query(
            model.Habit
        )
        .filter(
            model.Habit.user_id
            == user_id
        )
        .all()
    )

    logs = (
        db.query(
            model.HabitLog
        )
        .filter(
            model.HabitLog.user_id
            == user_id
        )
        .all()
    )

    return {

        "success": True,

        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        },

        "habits": [

            {
                "id": h.id,
                "name": h.name,
                "category": h.category,
                "target": h.target,
                "status": h.status
            }

            for h in habits
        ],

        "logs": [

            {
                "id": l.id,
                "habit_id": l.habit_id,
                "date": str(l.date),
                "status": l.status,
                "duration":
                    l.duration
                    if l.duration is not None
                    else 0
            }

            for l in logs
        ]
    }


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    print(
        "======================================"
    )

    print(
        "AI Habit Coach Backend"
    )

    print(
        "Server starting..."
    )

    print(
        "======================================"
    )

    uvicorn.run(

        app,

        host="0.0.0.0",

        port=int(
            os.getenv(
                "PORT",
                8000
            )
        )
    )