from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """subject is typically the user's id (as a string) or email."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Returns the subject (user id) if valid, None otherwise."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def create_oauth_state_token(user_id: int, platform: str) -> str:
    """
    Signed, short-lived token encoding who started an OAuth connection flow.

    Needed because the platform's OAuth callback hits our /callback endpoint
    directly from the user's browser with no Authorization header - there's
    no way to know which logged-in user this is other than what we encode
    into `state` before redirecting them away in the first place.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.oauth_state_expire_minutes)
    payload = {"sub": str(user_id), "platform": platform, "exp": expire, "typ": "oauth_state"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_oauth_state_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != "oauth_state":
            return None
        return payload
    except JWTError:
        return None
