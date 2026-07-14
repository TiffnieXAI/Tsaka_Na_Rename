import hashlib
import hmac
import time
from urllib.parse import quote

import httpx

from app.config import settings
from app.core.oauth.base import OAuthProvider, TokenResult


class ShopeeOAuthProvider(OAuthProvider):
    """
    Verified against Shopee Open Platform docs (open.shopee.com) as of this
    writing. Sandbox base URL: https://partner.test-stable.shopeemobile.com

    Flow:
      1. Redirect seller to AUTH_PATH with a signed request.
      2. Shopee redirects back to our callback with `code` and `shop_id`.
      3. POST to TOKEN_PATH (also signed) to exchange code -> access_token.

    Signature: HMAC-SHA256(partner_id + path + timestamp, partner_key)
    (only partner_id+path+timestamp for auth/token endpoints - the extended
    signature with access_token+shop_id is only for later authenticated
    shop-level API calls, not this initial exchange.)
    """

    AUTH_PATH = "/api/v2/shop/auth_partner"
    TOKEN_PATH = "/api/v2/auth/token/get"

    def __init__(self):
        self.partner_id = settings.shopee_partner_id
        self.partner_key = settings.shopee_partner_key
        self.base_url = settings.shopee_base_url
        self.redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/oauth/shopee/callback"

    def _sign(self, path: str, timestamp: int) -> str:
        base_string = f"{self.partner_id}{path}{timestamp}"
        return hmac.new(
            self.partner_key.encode(), base_string.encode(), hashlib.sha256
        ).hexdigest()

    def build_authorize_url(self, state: str) -> str:
        timestamp = int(time.time())
        sign = self._sign(self.AUTH_PATH, timestamp)
        # Shopee's redirect param doesn't natively carry a `state` field -
        # append it as a query param on our own redirect_uri instead, so it
        # survives the round trip and comes back to us in the callback.
        redirect_with_state = f"{self.redirect_uri}?state={state}"
        return (
            f"{self.base_url}{self.AUTH_PATH}"
            f"?partner_id={self.partner_id}&redirect={quote(redirect_with_state, safe='')}"
            f"&timestamp={timestamp}&sign={sign}"
        )

    async def exchange_code_for_token(self, code: str, **kwargs) -> TokenResult:
        shop_id = kwargs.get("shop_id")
        if not shop_id:
            raise ValueError("Shopee token exchange requires shop_id (sent back in the callback query string)")

        timestamp = int(time.time())
        sign = self._sign(self.TOKEN_PATH, timestamp)
        url = (
            f"{self.base_url}{self.TOKEN_PATH}"
            f"?partner_id={self.partner_id}&timestamp={timestamp}&sign={sign}"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json={
                "code": code,
                "shop_id": int(shop_id),
                "partner_id": int(self.partner_id),
            })
            resp.raise_for_status()
            data = resp.json()

        if data.get("error"):
            raise RuntimeError(f"Shopee token exchange failed: {data.get('message', data['error'])}")

        return TokenResult(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expire_in"),  # Shopee access tokens last ~4 hours
            external_account_id=str(shop_id),
        )
