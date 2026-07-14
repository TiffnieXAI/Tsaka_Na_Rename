from fastapi import Depends, HTTPException, WebSocket, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.models.models import User

# tokenUrl just tells auto-generated docs (/docs) where to get a token from -
# doesn't affect actual token verification, which happens via decode_access_token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    return user


async def get_current_user_ws(websocket: WebSocket, db: Session = Depends(get_db)) -> User:
    """
    Same idea as get_current_user, but for WebSocket routes (e.g. /ws/live-verify).
    Browser WebSocket clients can't set an Authorization header, so the JWT is
    passed as a query param instead: wss://host/ws/live-verify?token=<jwt>.

    Raising WebSocketException here closes the connection with the given code
    before the route handler's `await websocket.accept()` runs.
    """
    token = websocket.query_params.get("token")
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")

    user_id = decode_access_token(token)
    if user_id is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="User not found or inactive")

    return user
