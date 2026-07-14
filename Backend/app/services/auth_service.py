from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateResourceException
from app.core.security import hash_password, verify_password, create_access_token
from app.models.models import User
from app.schemas.auth import UserRegister


def register(db: Session, payload: UserRegister) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise DuplicateResourceException(f"An account already exists with email: {payload.email}")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_token_for_user(user: User) -> str:
    return create_access_token(subject=str(user.id))
