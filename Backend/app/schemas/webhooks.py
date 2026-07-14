from typing import Any, Optional

from pydantic import BaseModel

from app.models.models import PlatformType


class PlatformActivityIn(BaseModel):
    """
    Webhook / API activity telemetry (Logins, Transactions). 
    Deliberately loose (`payload: dict`) since each
    platform's real webhook body shape differs and per-platform signature
    verification / normalization isn't built yet (see docstring in
    app/routers/webhooks.py) - this is the ingestion contract our own
    backend/services use, not necessarily the raw shape any given
    platform sends over the wire.
    """

    platform: PlatformType
    event_type: str  # e.g. "login", "transaction", "listing_update" - not yet a fixed enum, see TODO
    payload: dict[str, Any]
    external_account_id: Optional[str] = None
