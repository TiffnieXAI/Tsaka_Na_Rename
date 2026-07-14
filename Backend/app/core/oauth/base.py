from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenResult:
    access_token: str
    refresh_token: Optional[str]
    expires_in: Optional[int]  # seconds until access_token expires
    external_account_id: str   # shop_id / seller_id - whatever identifies the connected shop
    external_display_name: Optional[str] = None


class OAuthProvider(ABC):
    """One implementation per platform (Shopee/Lazada/TikTok Shop). Each
    platform's authorize-URL construction and token exchange differ enough
    (different signature schemes, different param names) that a single
    generic OAuth2 client can't cover all three - this keeps that mess
    contained to one file per platform."""

    @abstractmethod
    def build_authorize_url(self, state: str) -> str:
        """URL to send the user's browser to, to grant Centry access."""
        ...

    @abstractmethod
    async def exchange_code_for_token(self, code: str, **kwargs) -> TokenResult:
        """kwargs carries any extra callback params a platform sends besides
        `code` - e.g. Shopee also returns shop_id in the callback query string."""
        ...
