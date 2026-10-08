from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

# ============================================================
# SQLITE DATABASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "habit.db"

DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# ============================================================
# DATABASE SESSION
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()