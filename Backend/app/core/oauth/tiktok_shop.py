import httpx
from urllib.parse import quote

from app.config import settings
from app.core.oauth.base import OAuthProvider, TokenResult


class TikTokShopOAuthProvider(OAuthProvider):
    """
    ⚠️ NOT FULLY VERIFIED - confirm against https://partner.tiktokshop.com/docv2
    ("Authorization overview") before using this for anything real.

    What IS confirmed:
      - TikTok Shop is a SEPARATE product from "TikTok for Developers" /
        TikTok Login Kit (open-api.tiktok.com, open.tiktokapis.com). Do not
        use that API's OAuth flow here - wrong product, wrong scopes.
      - TikTok Shop's actual API base domain is open-api.tiktokglobalshop.com
      - Auth starts from a link generated in your Partner Center app (it
        encodes your service_id), which the seller visits, picks a region,
        and logs in.
      - After approval, TikTok Shop redirects to your registered redirect_uri
        with an authorization `code`.
      - Token exchange is a request with app_key, app_secret, and the code.
      - Every subsequent authenticated API call needs both access_token AND
        a shop_cipher (an additional per-shop identifier returned separately
        via a "get authorized shops" call after you have the access_token).

    What is NOT confirmed here (placeholders below - fix before relying on this):
      - The exact AUTH_BASE URL (varies by source across different docs/years)
      - The exact TOKEN_URL path and whether it's GET or POST
      - Whether token exchange requires the same HMAC request-signing scheme
        TikTok Shop uses for its regular (non-auth) API calls, or not
      - How to fetch the shop_cipher needed for real API calls after this

    Given the mix of confirmed and unconfirmed pieces above, treat this class
    as a structural starting point, not working code, until someone checks it
    against the current Partner Center docs directly (requires a partner
    account to view the full authorization guide).
    """

    AUTH_BASE = "https://services.tiktokshop.com/open/authorize"  # UNVERIFIED
    TOKEN_URL = "https://auth.tiktok-shops.com/api/v2/token/get"  # UNVERIFIED

    def __init__(self):
        self.app_key = settings.tiktok_shop_app_key
        self.app_secret = settings.tiktok_shop_app_secret
        self.service_id = settings.tiktok_shop_service_id
        self.redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/oauth/tiktok_shop/callback"

    def build_authorize_url(self, state: str) -> str:
        redirect_with_state = f"{self.redirect_uri}?state={state}"
        return (
            f"{self.AUTH_BASE}?service_id={self.service_id}"
            f"&redirect_uri={quote(redirect_with_state, safe='')}"
        )

    async def exchange_code_for_token(self, code: str, **kwargs) -> TokenResult:
        params = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "auth_code": code,
            "grant_type": "authorized_code",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.TOKEN_URL, params=params)  # UNVERIFIED: method may need to be POST
            resp.raise_for_status()
            data = resp.json()

        body = data.get("data", data)
        if data.get("code") not in (0, None):
            raise RuntimeError(f"TikTok Shop token exchange failed: {data}")

        return TokenResult(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("access_token_expire_in"),
            external_account_id=str(body.get("seller_name", "unknown")),  # UNVERIFIED field name
        )
