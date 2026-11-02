from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, PasswordChangeRequest, RegisterRequest, TokenResponse, UserResponse,
)
from app.services.auth_service import authenticate_user, register_user
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(db, payload.email, payload.full_name, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_audit(db, user.id, "auth.registered", "user", str(user.id))
    token = create_access_token(user.id, user.role, user.token_version)
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password."
        )
    record_audit(db, user.id, "auth.login", "user", str(user.id))
    token = create_access_token(user.id, user.role, user.token_version)
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/admin-check", tags=["administration"])
def admin_check(user: User = Depends(require_admin)):
    return {"status": "ok", "message": "Administrator access confirmed."}


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    record_audit(db, user.id, "auth.logout", "user", str(user.id))
    return {"status": "ok", "message": "Session revoked."}


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400, detail="New password must differ from the current password."
        )
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    db.commit()
    record_audit(db, user.id, "auth.password_changed", "user", str(user.id))
    return {"status": "ok", "message": "Password changed. Sign in again with your new password."}
