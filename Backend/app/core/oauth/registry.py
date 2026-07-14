from app.models.models import PlatformType
from app.core.oauth.base import OAuthProvider
from app.core.oauth.shopee import ShopeeOAuthProvider
from app.core.oauth.lazada import LazadaOAuthProvider
from app.core.oauth.tiktok_shop import TikTokShopOAuthProvider
from app.core.oauth.meta import MetaOAuthProvider


def get_oauth_provider(platform_type: PlatformType) -> OAuthProvider:
    if platform_type == PlatformType.SHOPEE:
        return ShopeeOAuthProvider()
    if platform_type == PlatformType.LAZADA:
        return LazadaOAuthProvider()
    if platform_type == PlatformType.TIKTOK_SHOP:
        return TikTokShopOAuthProvider()
    if platform_type == PlatformType.META:
        return MetaOAuthProvider()
    raise ValueError(f"No OAuth provider configured for {platform_type}")
