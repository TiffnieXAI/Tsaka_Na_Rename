from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.models import PlatformType, ConnectionStatus


class AuthorizeUrlResponse(BaseModel):
    authorize_url: str


class PlatformConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_type: PlatformType
    external_account_id: str
    external_display_name: Optional[str]
    status: ConnectionStatus
    connected_at: datetime
    # access_token / refresh_token intentionally excluded from responses
