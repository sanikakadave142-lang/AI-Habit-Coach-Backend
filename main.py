import os
import secrets
import time
from datetime import date
from typing import List

from dotenv import load_dotenv

load_dotenv()

# =========================
# ENVIRONMENT VARIABLES
# =========================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# =========================
# FASTAPI
# =========================

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =========================
# DATABASE
# =========================

from sqlalchemy.orm import Session

from database import SessionLocal, engine
import model
import schemas

# Create tables
model.Base.metadata.create_all(bind=engine)

# =========================
# PASSWORD HASHING
# =========================

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

# =========================
# GEMINI
# =========================

from google import genai

gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("Gemini API loaded: True")
    except Exception as e:
        print("Gemini initialization error:", e)
else:
    print("Gemini API loaded: False")


# =========================
# APP
# =========================

app = FastAPI(
    title="AI Habit Coach API",
    version="1.0.0"
)

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# DATABASE DEPENDENCY
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================
# PASSWORD FUNCTIONS
# =========================

def hash_password(password: str):
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str):
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


# =========================
# ADMIN TOKEN
# =========================

ADMIN_TOKENS = set()


# =========================
# ROOT
# =========================

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
    existing_user = (
        db.query(model.User)
        .filter(model.User.email == user.email)
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
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "success": True,
        "message": "Registration successful",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email
        }
    }


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
        .filter(model.User.email == user.email)
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


# ============================================================
# GET HABITS
# ============================================================

@app.get("/habits")
def get_habits(
    user_id: int,
    db: Session = Depends(get_db)
):
    habits = (
        db.query(model.Habit)
        .filter(model.Habit.user_id == user_id)
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
        .filter(model.Habit.id == habit_id)
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
        .filter(model.Habit.id == habit_id)
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
# HABIT LOG
# ============================================================

@app.post("/habit-log")
def add_habit_log(
    log: schemas.HabitLogCreate,
    db: Session = Depends(get_db)
):
    new_log = model.HabitLog(
        user_id=log.user_id,
        habit_id=log.habit_id,
        date=log.date,
        status=log.status,
        duration=log.duration
    )

    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return {
        "success": True,
        "message": "Habit log added successfully",
        "log": {
            "id": new_log.id,
            "user_id": new_log.user_id,
            "habit_id": new_log.habit_id,
            "date": str(new_log.date),
            "status": new_log.status,
            "duration": new_log.duration
        }
    }


# ============================================================
# GET HABIT LOG
# ============================================================

@app.get("/habit-log")
def get_habit_logs(
    user_id: int,
    db: Session = Depends(get_db)
):
    logs = (
        db.query(model.HabitLog)
        .filter(model.HabitLog.user_id == user_id)
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
                "duration": log.duration
            }
            for log in logs
        ]
    }


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
        .filter(model.HabitLog.user_id == user_id)
        .all()
    )

    total_logs = len(logs)

    completed = sum(
        1 for log in logs
        if str(log.status).lower() == "completed"
    )

    missed = sum(
        1 for log in logs
        if str(log.status).lower() == "missed"
    )

    if total_logs > 0:
        completion_percentage = round(
            (completed / total_logs) * 100,
            2
        )
    else:
        completion_percentage = 0

    return {
        "success": True,
        "completed": completed,
        "total_logs": total_logs,
        "completion_percentage": completion_percentage,
        "missed": missed
    }


# ============================================================
# AI FALLBACK
# ============================================================

def get_fallback_advice(question: str):

    q = question.lower()

    if any(word in q for word in [
        "study",
        "exam",
        "college",
        "education",
        "learn"
    ]):
        return (
            "Create a simple study routine and focus on one task at a time. "
            "Study for 25 to 30 minutes, take a short break, and continue. "
            "Track your progress every day and stay consistent."
        )

    if any(word in q for word in [
        "exercise",
        "workout",
        "fitness",
        "gym"
    ]):
        return (
            "Start with a realistic daily exercise goal. "
            "Even 20 to 30 minutes of walking or exercise is useful. "
            "Increase your activity gradually and maintain consistency."
        )

    if any(word in q for word in [
        "sleep",
        "rest",
        "routine"
    ]):
        return (
            "Maintain a consistent sleep and daily routine. "
            "Try to sleep and wake up at similar times every day. "
            "Avoid unnecessary screen time before sleeping."
        )

    if any(word in q for word in [
        "water",
        "drink"
    ]):
        return (
            "Keep a simple water reminder throughout the day. "
            "Drink water regularly instead of waiting until you feel very thirsty."
        )

    return (
        "Start with a small and realistic habit. "
        "Set a clear daily goal, track your progress, and focus on consistency. "
        "If you miss one day, do not give up. Start again the next day."
    )


# ============================================================
# AI ADVICE REQUEST
# ============================================================

class AIAdviceRequest(schemas.BaseModel):
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
def ai_advice(request: AIAdviceRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question is required"
        )

    fallback = get_fallback_advice(question)

    # --------------------------------------------------------
    # Gemini not configured
    # --------------------------------------------------------

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

Give practical, simple and positive advice.

User question:
{question}

Rules:
- Keep the answer useful.
- Use simple language.
- Give actionable suggestions.
- Do not give dangerous medical advice.
"""

    # --------------------------------------------------------
    # Try Gemini
    # --------------------------------------------------------

    for model_name in AI_MODELS:

        try:

            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            if response and response.text:

                return {
                    "success": True,
                    "question": question,
                    "advice": response.text.strip(),
                    "user_id": request.user_id,
                    "model": model_name,
                    "source": "Gemini AI"
                }

        except Exception as e:

            error_text = str(e).lower()

            print(
                f"Gemini error ({model_name}):",
                str(e)
            )

            # ------------------------------------------------
            # QUOTA / 429
            # ------------------------------------------------

            if (
                "429" in error_text
                or "quota" in error_text
                or "resource_exhausted" in error_text
                or "rate limit" in error_text
            ):
                print(
                    "Gemini quota exceeded. "
                    "Using fallback advice."
                )
                break

            # ------------------------------------------------
            # SERVER BUSY / 503
            # ------------------------------------------------

            if (
                "503" in error_text
                or "unavailable" in error_text
                or "overloaded" in error_text
                or "high demand" in error_text
            ):
                time.sleep(1)
                continue

            # ------------------------------------------------
            # OTHER GEMINI ERROR
            # ------------------------------------------------

            continue

    # --------------------------------------------------------
    # ALWAYS RETURN FALLBACK
    # --------------------------------------------------------

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
def ai_predict(data: dict):

    completion_rate = float(
        data.get("completion_rate", 0)
    )

    missed_days = int(
        data.get("missed_days", 0)
    )

    current_streak = int(
        data.get("current_streak", 0)
    )

    frequency = int(
        data.get("frequency", 7)
    )

    # Simple rule-based prediction

    if completion_rate >= 80 and current_streak >= 5:
        prediction = "Likely to Complete"
        confidence = 100.0
        recommendation = (
            "Keep following your current habit routine."
        )

    elif completion_rate >= 60:
        prediction = "Moderately Likely to Complete"
        confidence = 80.0
        recommendation = (
            "Try to maintain a regular routine "
            "and reduce missed days."
        )

    else:
        prediction = "Needs Improvement"
        confidence = 70.0
        recommendation = (
            "Start with a smaller goal and focus "
            "on completing the habit consistently."
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
def admin_login(data: dict):

    email = data.get("email")
    password = data.get("password")

    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="Admin credentials are not configured"
        )

    if email != ADMIN_EMAIL or password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials"
        )

    token = secrets.token_hex(32)

    ADMIN_TOKENS.add(token)

    return {
        "success": True,
        "message": "Admin login successful",
        "token": token
    }


# ============================================================
# ADMIN AUTH
# ============================================================

def verify_admin_token(token: str):

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
def admin_logout(data: dict):

    token = data.get("token")

    if token in ADMIN_TOKENS:
        ADMIN_TOKENS.remove(token)

    return {
        "success": True,
        "message": "Admin logout successful"
    }


# ============================================================
# ADMIN STATS
# ============================================================

@app.get("/admin/stats")
def admin_stats(
    token: str,
    db: Session = Depends(get_db)
):

    verify_admin_token(token)

    users_count = db.query(model.User).count()
    habits_count = db.query(model.Habit).count()
    logs_count = db.query(model.HabitLog).count()

    completed_count = (
        db.query(model.HabitLog)
        .filter(
            model.HabitLog.status == "Completed"
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
    token: str,
    db: Session = Depends(get_db)
):

    verify_admin_token(token)

    users = db.query(model.User).all()

    return {
        "success": True,
        "users": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email
            }
            for user in users
        ]
    }


# ============================================================
# ADMIN USER DETAILS
# ============================================================

@app.get("/admin/users/{user_id}")
def admin_user_details(
    user_id: int,
    token: str,
    db: Session = Depends(get_db)
):

    verify_admin_token(token)

    user = (
        db.query(model.User)
        .filter(model.User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    habits = (
        db.query(model.Habit)
        .filter(model.Habit.user_id == user_id)
        .all()
    )

    logs = (
        db.query(model.HabitLog)
        .filter(model.HabitLog.user_id == user_id)
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
                "duration": l.duration
            }
            for l in logs
        ]
    }


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    print("======================================")
    print("AI Habit Coach Backend")
    print("Server starting...")
    print("======================================")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000))
    )