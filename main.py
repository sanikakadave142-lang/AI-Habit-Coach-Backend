
import os
import secrets
import time
import sqlite3
from datetime import date
from rag_engine import search_knowledge, get_vector_store

from dotenv import load_dotenv

load_dotenv()

# ============================================================
# SQLITE DEMO DATABASE
# ============================================================

SQLITE_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habit.db")

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
        "[stored in MySQL]"
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
    columns = {row[1] for row in cur.fetchall()}

    if "date" not in columns:
        cur.execute("ALTER TABLE habit_logs ADD COLUMN date TEXT")

    if "log_date" not in columns:
        cur.execute("ALTER TABLE habit_logs ADD COLUMN log_date TEXT")

    if "note" not in columns:
        cur.execute("ALTER TABLE habit_logs ADD COLUMN note TEXT")

    conn.commit()
    conn.close()


def sync_log_to_sqlite(log):
    ensure_sqlite_tables()
    conn = sqlite_connection()
    cur = conn.cursor()

    log_date_value = getattr(log, "log_date", None)
    date_value = getattr(log, "date", None)

    if log_date_value is None:
        log_date_value = date_value

    cur.execute("""
        INSERT OR REPLACE INTO habit_logs
        (id, user_id, habit_id, log_date, status, duration, note, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log.id,
        log.user_id,
        log.habit_id,
        str(log_date_value) if log_date_value is not None else "",
        log.status,
        log.duration if log.duration is not None else 0,
        getattr(log, "note", "") or "",
        str(date_value) if date_value is not None else ""
    ))

    conn.commit()
    conn.close()


def sync_all_to_sqlite():
    """Mirror all current MySQL data into the local SQLite demo database."""
    conn = None
    db = None

    try:
        create_sqlite_tables()

        # SessionLocal and model are imported below this block,
        # but this function is called only after those imports exist.
        db = SessionLocal()
        users = db.query(model.User).all()
        habits = db.query(model.Habit).all()
        logs = db.query(model.HabitLog).all()

        conn = sqlite_connection()
        cur = conn.cursor()

        # Rebuild the mirror so deleted MySQL records do not remain in SQLite.
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
            f"SQLite sync completed: {len(users)} users, "
            f"{len(habits)} habits, {len(logs)} habit logs"
        )

    except Exception as e:
        print("SQLite sync error:", str(e))

    finally:
        if conn is not None:
            conn.close()
        if db is not None:
            db.close()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# ============================================================
# FASTAPI
# ============================================================

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Header
)

from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# DATABASE
# ============================================================

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from database import SessionLocal, engine
import model
import schemas


# ============================================================
# DATABASE MIGRATION
# ============================================================

def migrate_database():

    try:

        print("Checking database migration...")

        with engine.begin() as conn:

            # ------------------------------------------------
            # Check whether habit_logs table exists
            # ------------------------------------------------

            table_result = conn.execute(
                text("SHOW TABLES LIKE 'habit_logs'")
            )

            table_exists = table_result.fetchone()

            # ------------------------------------------------
            # If table does not exist, create tables first
            # ------------------------------------------------

            if not table_exists:

                print(
                    "habit_logs table not found. "
                    "Creating database tables..."
                )

                model.Base.metadata.create_all(
                    bind=engine
                )

            else:

                # --------------------------------------------
                # Get existing columns
                # --------------------------------------------

                result = conn.execute(
                    text("SHOW COLUMNS FROM habit_logs")
                )

                columns = {
                    row[0]
                    for row in result.fetchall()
                }

                print(
                    "Existing habit_logs columns:",
                    columns
                )

                # --------------------------------------------
                # Add user_id if missing
                # --------------------------------------------

                if "user_id" not in columns:

                    print(
                        "Adding missing column: user_id"
                    )

                    conn.execute(
                        text(
                            """
                            ALTER TABLE habit_logs
                            ADD COLUMN user_id INT NOT NULL DEFAULT 1
                            """
                        )
                    )

                # --------------------------------------------
                # Add habit_id if missing
                # --------------------------------------------

                if "habit_id" not in columns:

                    print(
                        "Adding missing column: habit_id"
                    )

                    conn.execute(
                        text(
                            """
                            ALTER TABLE habit_logs
                            ADD COLUMN habit_id INT NOT NULL DEFAULT 1
                            """
                        )
                    )

                # --------------------------------------------
                # Add date if missing
                # --------------------------------------------

                if "date" not in columns:

                    print(
                        "Adding missing column: date"
                    )

                    conn.execute(
                        text(
                            """
                            ALTER TABLE habit_logs
                            ADD COLUMN date DATE NOT NULL
                            DEFAULT '2026-01-01'
                            """
                        )
                    )

                # --------------------------------------------
                # Add status if missing
                # --------------------------------------------

                if "status" not in columns:

                    print(
                        "Adding missing column: status"
                    )

                    conn.execute(
                        text(
                            """
                            ALTER TABLE habit_logs
                            ADD COLUMN status VARCHAR(50)
                            NOT NULL DEFAULT 'Pending'
                            """
                        )
                    )

                # --------------------------------------------
                # Add duration if missing
                # --------------------------------------------

                if "duration" not in columns:

                    print(
                        "Adding missing column: duration"
                    )

                    conn.execute(
                        text(
                            """
                            ALTER TABLE habit_logs
                            ADD COLUMN duration INT
                            DEFAULT 0
                            """
                        )
                    )

        print(
            "DATABASE MIGRATION COMPLETED"
        )

    except Exception as e:

        print(
            "DATABASE MIGRATION ERROR:",
            str(e)
        )

        # Do not stop server completely.
        # create_all() below can still create
        # missing tables.



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

    # Create/update the local SQLite mirror with all existing MySQL data.
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

    return password_hash.hash(password)


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

    allow_origins=[
        "*"
    ],

    allow_credentials=False,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
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

        sync_user_to_sqlite(new_user)

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

        sync_habit_to_sqlite(new_habit)

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

    sync_habit_to_sqlite(habit)

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

    # Full sync removes the deleted habit and its old logs from the mirror.
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

        # ----------------------------------------
        # CHECK USER
        # ----------------------------------------

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

        # ----------------------------------------
        # CHECK HABIT
        # ----------------------------------------

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

        # ----------------------------------------
        # CREATE LOG
        # ----------------------------------------

        new_log = model.HabitLog(

            user_id=log.user_id,

            habit_id=log.habit_id,

            date=log.date,

            status=log.status,

            duration=(
                log.duration
                if log.duration is not None
                else 0
            )
        )

        db.add(new_log)

        db.commit()

        db.refresh(new_log)

        # ----------------------------------------
        # UPDATE HABIT STATUS
        # ----------------------------------------

        if log.status.lower() == "completed":

            habit.status = "Completed"

            db.commit()

        sync_all_to_sqlite()

        # ----------------------------------------
        # RESPONSE
        # ----------------------------------------

        return {

            "success": True,

            "message": "Habit log added successfully",

            "log": {

                "id": new_log.id,

                "user_id": new_log.user_id,

                "habit_id": new_log.habit_id,

                "date": str(new_log.date),

                "status": new_log.status,

                "duration": (
                    new_log.duration
                    if new_log.duration is not None
                    else 0
                )
            }
        }

    except HTTPException:

        raise

    except SQLAlchemyError as e:

        db.rollback()

        print(
            "HABIT LOG DATABASE ERROR:",
            str(e)
        )