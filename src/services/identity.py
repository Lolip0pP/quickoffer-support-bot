"""Identity service for Telegram user binding with QuickOffer accounts."""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.infrastructure.m2m.fuckhr_client import (
    FuckHRSupportAPIClient,
    FuckHRSupportAPIError,
)

logger = logging.getLogger(__name__)


class IdentityCheckRequest(BaseModel):
    """Request for identity check."""

    telegram_id: int = Field(..., gt=0, description="Telegram user ID")


class IdentityCheckResponse(BaseModel):
    """Response from identity check."""

    is_bound: bool = Field(..., description="Whether Telegram ID is bound")
    user_id: str | None = Field(
        None, description="QuickOffer user ID if bound"
    )
    bound_at: str | None = Field(None, description="ISO timestamp when bound")


class AuthLinkRequest(BaseModel):
    """Request for auth link generation."""

    telegram_id: int = Field(..., gt=0, description="Telegram user ID")
    ttl_seconds: int = Field(
        default=3600, ge=60, le=86400, description="Link TTL in seconds"
    )


class AuthLinkResponse(BaseModel):
    """Response from auth link generation."""

    auth_url: str = Field(..., description="One-time auth link URL")
    expires_at: str = Field(..., description="ISO timestamp when link expires")


class IdentityService:
    """Service for managing Telegram user identity binding."""

    def __init__(self, client: FuckHRSupportAPIClient | None = None) -> None:
        """Initialize identity service.

        Args:
            client: FuckHR Support API client (auto-initialized if None).
        """
        self.client = client or FuckHRSupportAPIClient()

    async def check_identity(
        self, telegram_id: int
    ) -> IdentityCheckResponse:
        """Check if Telegram ID is bound to QuickOffer account.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            IdentityCheckResponse: Identity check result.

        Raises:
            Exception: If API call fails.
        """
        logger.info(f"Checking identity for telegram_id={telegram_id}")

        try:
            response = await self.client.check_identity(telegram_id)

            result = IdentityCheckResponse(
                is_bound=response.get("is_bound", False),
                user_id=response.get("user_id"),
                bound_at=response.get("bound_at"),
            )

            logger.info(
                f"Identity check successful: is_bound={result.is_bound}",
                extra={
                    "telegram_id": telegram_id,
                    "user_id": result.user_id,
                },
            )

            return result

        except FuckHRSupportAPIError as e:
            logger.error(
                f"Identity check failed: {str(e)}",
                extra={"telegram_id": telegram_id},
            )
            raise

    async def generate_auth_link(
        self,
        telegram_id: int,
        ttl_seconds: int = 3600,
    ) -> AuthLinkResponse:
        """Generate one-time auth link for unbound Telegram account.

        Args:
            telegram_id: Telegram user ID.
            ttl_seconds: Time-to-live for auth link in seconds (default: 1 hour).

        Returns:
            AuthLinkResponse: Auth link generation result.

        Raises:
            Exception: If API call fails.
        """
        logger.info(
            f"Generating auth link for telegram_id={telegram_id}",
            extra={"ttl_seconds": ttl_seconds},
        )

        try:
            response = await self.client.generate_auth_link(
                telegram_id, ttl_seconds
            )

            result = AuthLinkResponse(
                auth_url=response.get("auth_url", ""),
                expires_at=response.get("expires_at", ""),
            )

            if not result.auth_url or not result.expires_at:
                raise ValueError(
                    "Invalid response: missing auth_url or expires_at"
                )

            logger.info(
                f"Auth link generated successfully",
                extra={"telegram_id": telegram_id},
            )

            return result

        except FuckHRSupportAPIError as e:
            logger.error(
                f"Auth link generation failed: {str(e)}",
                extra={"telegram_id": telegram_id},
            )
            raise

    async def check_and_bind_or_link(
        self, telegram_id: int
    ) -> dict[str, Any]:
        """Check identity binding, return user_id if bound or auth_link if not.

        This is a convenience method for the typical bot flow.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            dict: Either {"user_id": str} if bound or {"auth_url": str, "expires_at": str}.

        Raises:
            Exception: If API calls fail.
        """
        identity = await self.check_identity(telegram_id)

        if identity.is_bound and identity.user_id:
            logger.info(
                f"User already bound",
                extra={
                    "telegram_id": telegram_id,
                    "user_id": identity.user_id,
                },
            )
            return {"user_id": identity.user_id}

        logger.info(
            f"User not bound, generating auth link",
            extra={"telegram_id": telegram_id},
        )
        auth_link = await self.generate_auth_link(telegram_id)

        return {
            "auth_url": auth_link.auth_url,
            "expires_at": auth_link.expires_at,
        }


def get_identity_service(
    client: FuckHRSupportAPIClient | None = None,
) -> IdentityService:
    """Factory function to get identity service.

    Args:
        client: Optional FuckHR API client for dependency injection.

    Returns:
        IdentityService: Configured identity service instance.
    """
    return IdentityService(client)
