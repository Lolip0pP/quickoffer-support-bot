"""M2M (Machine-to-Machine) infrastructure - API clients for external services."""

from src.infrastructure.m2m.clients import FuckHRAPIClient, JobsAPIClient
from src.infrastructure.m2m.fuckhr_client import (
    FuckHRSupportAPIClient,
    FuckHRSupportAPIError,
)

__all__ = [
    "FuckHRAPIClient",
    "JobsAPIClient",
    "FuckHRSupportAPIClient",
    "FuckHRSupportAPIError",
]
