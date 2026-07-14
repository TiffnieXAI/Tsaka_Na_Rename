from urllib.parse import quote

import httpx

from app.config import settings
from app.core.oauth.base import OAuthProvider, TokenResult

GRAPH_VERSION = "v21.0"


class MetaOAuthProvider(OAuthProvider):
    """
    Facebook Login (Meta Graph API) - connects a Facebook Page the MSME
    owner administers, feeding the "Social Media & E-Commerce" telemetry in
    the flowchart's Cross-Platform Monitoring section.

    Flow (standard Facebook OAuth 2.0, not "Facebook Login for Business" -
    that product is for accessing *other* businesses' assets via a
    Business Manager, which needs Advanced Access / business verification.
    A user connecting their own Page just needs regular Facebook Login):
      1. Redirect the owner to Facebook's OAuth dialog with the requested
         Page-permission scopes.
      2. Facebook redirects back to our callback with `code`.
      3. Exchange code -> short-lived user access token (~1-2 hours).
      4. Exchange short-lived -> long-lived user access token (~60 days) -
         needed because this token has to keep working for background
         monitoring, not just one login session.
      5. Call /me/accounts to list the Pages this user administers and grab
         that Page's access token. Page tokens derived from a long-lived
         user token effectively don't expire, which is what actually gets
         stored (not the user token itself).

    NOTE: a user can administer multiple Pages. This picks the first one
    returned - before this goes further, have the frontend show a
    "choose a Page" step when /me/accounts returns more than one, instead
    of silently picking index 0.

    Permissions used here (pages_show_list, pages_read_engagement,
    pages_manage_metadata) are all available at Standard Access in
    Development Mode - the MSME owner just needs to be an admin/tester
    on this Meta app to authorize with their own Page. No App Review or
    business verification needed until this serves *other* people's Pages.
    """

    AUTH_BASE = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
    GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

    # Extend with pages_messaging / pages_read_user_content / webhook-related
    # scopes once real-time Page event subscriptions (flowchart step 01:
    # "Webhook / API activity telemetry") are wired up.
    SCOPES = "pages_show_list,pages_read_engagement,pages_manage_metadata"

    def __init__(self):
        self.app_id = settings.meta_app_id
        self.app_secret = settings.meta_app_secret
        self.redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/oauth/meta/callback"

    def build_authorize_url(self, state: str) -> str:
        return (
            f"{self.AUTH_BASE}?client_id={self.app_id}"
            f"&redirect_uri={quote(self.redirect_uri, safe='')}"
            f"&state={state}&scope={self.SCOPES}&response_type=code"
        )

    async def exchange_code_for_token(self, code: str, **kwargs) -> TokenResult:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1: code -> short-lived user token
            resp = await client.get(f"{self.GRAPH_BASE}/oauth/access_token", params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            })
            resp.raise_for_status()
            short_lived = resp.json()
            if "error" in short_lived:
                raise RuntimeError(f"Meta token exchange failed: {short_lived['error']}")

            # Step 2: short-lived -> long-lived user token (~60 days)
            resp = await client.get(f"{self.GRAPH_BASE}/oauth/access_token", params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_lived["access_token"],
            })
            resp.raise_for_status()
            long_lived = resp.json()
            if "error" in long_lived:
                raise RuntimeError(f"Meta long-lived token exchange failed: {long_lived['error']}")

            # Step 3: list Pages this user administers, with a per-Page token each
            resp = await client.get(f"{self.GRAPH_BASE}/me/accounts", params={
                "access_token": long_lived["access_token"],
            })
            resp.raise_for_status()
            pages = resp.json().get("data", [])

        if not pages:
            raise ValueError(
                "No Facebook Pages found for this account - the MSME owner "
                "needs to be an admin of at least one Page to connect it."
            )

        page = pages[0]  # TODO: let the user pick when there's more than one
        return TokenResult(
            access_token=page["access_token"],  # Page token - doesn't expire in practice
            refresh_token=None,  # not applicable to Page tokens obtained this way
            expires_in=None,
            external_account_id=page["id"],
            external_display_name=page.get("name"),
        )
