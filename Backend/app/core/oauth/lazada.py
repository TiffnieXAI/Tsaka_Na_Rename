import hashlib
import hmac
import time
from urllib.parse import quote

import httpx

from app.config import settings
from app.core.oauth.base import OAuthProvider, TokenResult


class LazadaOAuthProvider(OAuthProvider):
    """
    Verified against Lazada Open Platform docs (open.lazada.com) as of this
    writing.

    Flow:
      1. Redirect seller to AUTH_BASE with client_id + redirect_uri.
      2. Lazada redirects back to our callback with `code`.
      3. GET TOKEN_URL (signed) to exchange code -> access_token.

    Signature: HMAC-SHA256(path + sorted concatenated "key value" params,
    app_secret), uppercase hex digest.
    """

    AUTH_BASE = "https://auth.lazada.com/oauth/authorize"
    TOKEN_URL = "https://auth.lazada.com/rest/auth/token/create"
    TOKEN_PATH = "/auth/token/create"

    def __init__(self):
        self.app_key = settings.lazada_app_key
        self.app_secret = settings.lazada_app_secret
        self.redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/oauth/lazada/callback"

    def _sign(self, path: str, params: dict) -> str:
        sorted_params = sorted(params.items())
        base_string = path + "".join(f"{k}{v}" for k, v in sorted_params)
        return hmac.new(
            self.app_secret.encode(), base_string.encode(), hashlib.sha256
        ).hexdigest().upper()

    def build_authorize_url(self, state: str) -> str:
        # Lazada's redirect_uri also doesn't natively carry `state` - same
        # trick as Shopee, append it to our own redirect_uri.
        redirect_with_state = f"{self.redirect_uri}?state={state}"
        return (
            f"{self.AUTH_BASE}?response_type=code&force_auth=true"
            f"&redirect_uri={quote(redirect_with_state, safe='')}&client_id={self.app_key}"
        )

    async def exchange_code_for_token(self, code: str, **kwargs) -> TokenResult:
        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.app_key,
            "sign_method": "sha256",
            "timestamp": timestamp,
            "code": code,
        }
        params["sign"] = self._sign(self.TOKEN_PATH, params)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.TOKEN_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Lazada returns code "0" (as a string) on success, non-zero on failure
        if data.get("code") not in (None, "0", 0):
            raise RuntimeError(f"Lazada token exchange failed: {data}")

        seller_info = (data.get("country_user_info_list") or [{}])[0]

        return TokenResult(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            external_account_id=str(seller_info.get("seller_id", "unknown")),
            external_display_name=seller_info.get("short_code"),
        )
