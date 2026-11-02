import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password
from app.models.user import User


def register_user(db: Session, email: str, full_name: str, password: str) -> User:
    normalized = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalized)):
        raise ValueError("An account with this email already exists.")
    user = User(email=normalized, full_name=full_name.strip(), password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def seed_admin(db: Session) -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    if len(password) < 12:
        raise ValueError("ADMIN_PASSWORD must contain at least 12 characters.")
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return
    db.add(User(
        email=email,
        full_name=os.getenv("ADMIN_FULL_NAME", "CodeGuard Administrator"),
        password_hash=hash_password(password),
        role="admin",
    ))
    db.commit()
