from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.core.security import create_oauth_state_token, decode_oauth_state_token
from app.core.oauth.registry import get_oauth_provider
from app.models.models import PlatformConnection, PlatformType, ConnectionStatus, User


def start_authorization(user: User, platform_type: PlatformType) -> str:
    state = create_oauth_state_token(user.id, platform_type.value)
    provider = get_oauth_provider(platform_type)
    return provider.build_authorize_url(state)


async def complete_authorization(db: Session, platform_type: PlatformType,
                                  code: str, state: str, **extra) -> PlatformConnection:
    payload = decode_oauth_state_token(state)
    if not payload:
        raise ValueError("Invalid or expired OAuth state - please restart the connection flow")
    if payload.get("platform") != platform_type.value:
        raise ValueError("OAuth state does not match the platform in this callback")

    user_id = int(payload["sub"])

    provider = get_oauth_provider(platform_type)
    token_result = await provider.exchange_code_for_token(code, **extra)

    expires_at = None
    if token_result.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_result.expires_in)

    existing = db.query(PlatformConnection).filter(
        PlatformConnection.user_id == user_id,
        PlatformConnection.platform_type == platform_type,
        PlatformConnection.external_account_id == token_result.external_account_id,
    ).first()

    if existing:
        existing.access_token = token_result.access_token
        existing.refresh_token = token_result.refresh_token
        existing.token_expires_at = expires_at
        existing.status = ConnectionStatus.CONNECTED
        connection = existing
    else:
        connection = PlatformConnection(
            user_id=user_id,
            platform_type=platform_type,
            external_account_id=token_result.external_account_id,
            external_display_name=token_result.external_display_name,
            access_token=token_result.access_token,
            refresh_token=token_result.refresh_token,
            token_expires_at=expires_at,
            status=ConnectionStatus.CONNECTED,
        )
        db.add(connection)

    db.commit()
    db.refresh(connection)
    return connection


def list_connections(db: Session, user_id: int) -> list[PlatformConnection]:
    return db.query(PlatformConnection).filter(PlatformConnection.user_id == user_id).all()


def disconnect(db: Session, user_id: int, connection_id: int) -> PlatformConnection:
    connection = db.query(PlatformConnection).filter(
        PlatformConnection.id == connection_id,
        PlatformConnection.user_id == user_id,
    ).first()
    if not connection:
        raise ResourceNotFoundException(f"Platform connection {connection_id} not found")
    connection.status = ConnectionStatus.DISCONNECTED
    db.commit()
    db.refresh(connection)
    return connection
