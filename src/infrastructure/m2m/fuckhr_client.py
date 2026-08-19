"""FuckHR API client for support bot integration."""

import logging
import uuid
from typing import Any

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class FuckHRSupportAPIError(Exception):
    """FuckHR Support API error."""

    pass


class FuckHRSupportAPIClient:
    """HTTP client for FuckHR Support API with automatic headers and error handling."""

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize FuckHR Support API client.

        Args:
            base_url: Base URL for FuckHR API.
        """
        self.base_url = base_url or settings.fuckhr_api_base_url
        self.api_key = settings.m2m_api_key
        self.support_api_path = "/internal/support/v1"

    def _get_headers(
        self, action_id: uuid.UUID | None = None
    ) -> dict[str, str]:
        """Get standard headers with Idempotency-Key and Trace-ID.

        Args:
            action_id: Optional action UUID for Trace-ID.

        Returns:
            dict: Headers dictionary.
        """
        trace_id = str(action_id) if action_id else str(uuid.uuid4())
        idempotency_key = str(uuid.uuid4())

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
            "Trace-ID": trace_id,
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        action_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request with automatic headers and error handling.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            action_id: Optional action UUID for tracing.
            payload: Optional request payload.

        Returns:
            dict: API response data.

        Raises:
            FuckHRSupportAPIError: If request fails.
        """
        url = f"{self.base_url}{self.support_api_path}{endpoint}"
        headers = self._get_headers(action_id)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                logger.info(
                    f"FuckHR API request successful",
                    extra={
                        "method": method,
                        "endpoint": endpoint,
                        "trace_id": headers["Trace-ID"],
                    },
                )
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FuckHR API HTTP error: {e.status_code}",
                extra={
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": e.status_code,
                    "trace_id": headers["Trace-ID"],
                },
            )
            raise FuckHRSupportAPIError(
                f"FuckHR API error {e.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error(
                f"FuckHR API request error: {str(e)}",
                extra={
                    "method": method,
                    "endpoint": endpoint,
                    "trace_id": headers["Trace-ID"],
                },
            )
            raise FuckHRSupportAPIError(
                f"FuckHR API request failed: {str(e)}"
            ) from e

    async def check_identity(self, telegram_id: int) -> dict[str, Any]:
        """Check if Telegram ID is bound to QuickOffer account.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            dict: Identity check response with user_id or None.
        """
        return await self._make_request(
            "POST",
            "/identity/check",
            payload={"telegram_id": telegram_id},
        )

    async def generate_auth_link(
        self, telegram_id: int, ttl_seconds: int = 3600
    ) -> dict[str, Any]:
        """Generate one-time auth link for unbound Telegram account.

        Args:
            telegram_id: Telegram user ID.
            ttl_seconds: Time-to-live for auth link in seconds.

        Returns:
            dict: Auth link generation response with auth_url.
        """
        return await self._make_request(
            "POST",
            "/identity/auth-link",
            payload={"telegram_id": telegram_id, "ttl_seconds": ttl_seconds},
        )

    async def get_referral_promo_code(
        self, user_id: str
    ) -> dict[str, Any]:
        """Get existing referral promo code or generate new one.

        Args:
            user_id: QuickOffer user ID.

        Returns:
            dict: Promo code response with code, discount_percent, expires_at.
        """
        return await self._make_request(
            "POST",
            "/promocodes/referral",
            payload={"user_id": user_id},
        )

    async def check_review(
        self, user_id: str
    ) -> dict[str, Any]:
        """Check if user has published review (len > 30, any sentiment).

        Args:
            user_id: QuickOffer user ID.

        Returns:
            dict: Review check response with review_found, review_id, etc.
        """
        return await self._make_request(
            "POST",
            "/reviews/check",
            payload={"user_id": user_id},
        )

    async def get_review_promo_code(
        self, user_id: str
    ) -> dict[str, Any]:
        """Get existing review promo code or generate one-time code.

        Args:
            user_id: QuickOffer user ID.

        Returns:
            dict: Promo code response with code, max_uses, user_bound flag.
        """
        return await self._make_request(
            "POST",
            "/promocodes/review",
            payload={"user_id": user_id},
        )

    async def get_review_form_url(self) -> dict[str, Any]:
        """Get URL for review form submission.

        Returns:
            dict: Response with review_form_url.
        """
        return await self._make_request(
            "GET",
            "/reviews/form-url",
        )
