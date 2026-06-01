"""
Central FHIR server authentication.

Builds an httpx.Auth from a stored auth_config. Supported types:
  - none
  - basic                     -> httpx.BasicAuth
  - oauth2_client_credentials -> self-refreshing Bearer token (for Blaze etc.)

Legacy rows that stored {"username", "password"} without a "type" are treated
as basic auth.
"""

import logging
from time import monotonic
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def normalize_auth_config(raw: Optional[dict]) -> dict:
    """Return a canonical config dict that always has a 'type'."""
    if not raw:
        return {"type": "none"}
    if raw.get("type") in ("none", "basic", "oauth2_client_credentials"):
        return raw
    # Legacy shape: bare username/password.
    if raw.get("username") or raw.get("password"):
        return {
            "type": "basic",
            "username": raw.get("username"),
            "password": raw.get("password"),
        }
    return {"type": "none"}


class OAuth2ClientCredentialsAuth(httpx.Auth):
    """
    OAuth2 client-credentials flow with in-memory token caching.

    The token is fetched lazily and refreshed 60s before expiry. Because the
    check runs inside the auth flow on every request, a single auth object can
    be reused for the whole run and will refresh itself mid-run.
    """

    requires_response_body = True

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
    ):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def _build_token_request(self) -> httpx.Request:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            data["scope"] = self.scope
        return httpx.Request(
            "POST",
            self.token_url,
            data=data,
            headers={"Accept": "application/json"},
        )

    async def async_auth_flow(self, request: httpx.Request):
        if self._access_token is None or monotonic() >= self._expires_at:
            token_response = yield self._build_token_request()
            if token_response.status_code != 200:
                raise httpx.HTTPError(
                    f"Token endpoint {self.token_url} returned "
                    f"{token_response.status_code}: {token_response.text[:200]}"
                )
            payload = token_response.json()
            self._access_token = payload["access_token"]
            self._expires_at = monotonic() + max(
                int(payload.get("expires_in", 300)) - 60, 0
            )

        request.headers["Authorization"] = f"Bearer {self._access_token}"
        yield request


def build_httpx_auth(raw: Optional[dict]) -> Optional[httpx.Auth]:
    """Build an httpx.Auth for a server's auth_config, or None for no auth."""
    cfg = normalize_auth_config(raw)
    auth_type = cfg["type"]

    if auth_type == "basic":
        if cfg.get("username") and cfg.get("password"):
            return httpx.BasicAuth(cfg["username"], cfg["password"])
        logger.warning("basic auth config incomplete; proceeding without auth")
        return None

    if auth_type == "oauth2_client_credentials":
        missing = [
            k for k in ("token_url", "client_id", "client_secret") if not cfg.get(k)
        ]
        if missing:
            logger.warning("oauth2 config missing %s; proceeding without auth", missing)
            return None
        return OAuth2ClientCredentialsAuth(
            token_url=cfg["token_url"],
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            scope=cfg.get("scope"),
        )

    return None
