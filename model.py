from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)

    habits = relationship(
        "Habit",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    habit_logs = relationship(
        "HabitLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# ============================================================
# HABIT
# ============================================================

class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    target = Column(String, nullable=False)
    status = Column(String, default="Pending", nullable=False)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    user = relationship(
        "User",
        back_populates="habits"
    )

    habit_logs = relationship(
        "HabitLog",
        back_populates="habit",
        cascade="all, delete-orphan"
    )


# ============================================================
# HABIT LOG
# ============================================================

class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    habit_id = Column(
        Integer,
        ForeignKey("habits.id"),
        nullable=False,
        index=True
    )

    date = Column(Date, nullable=False)

    status = Column(String, nullable=False)

    duration = Column(
        Integer,
        default=0,
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="habit_logs"
    )

    habit = relationship(
        "Habit",
        back_populates="habit_logs"
    )