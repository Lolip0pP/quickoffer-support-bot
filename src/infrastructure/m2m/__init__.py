"""M2M (Machine-to-Machine) infrastructure - API clients for external services."""

from src.infrastructure.m2m.clients import FuckHRAPIClient, JobsAPIClient
from src.infrastructure.m2m.factory import get_fuckhr_client, get_jobs_client
from src.infrastructure.m2m.fuckhr_client import (
    FuckHRSupportAPIClient,
    FuckHRSupportAPIError,
)
from src.infrastructure.m2m.mock_clients import (
    MockFuckHRAPIClient,
    MockJobsAPIClient,
)

__all__ = [
    "FuckHRAPIClient",
    "JobsAPIClient",
    "FuckHRSupportAPIClient",
    "FuckHRSupportAPIError",
    "MockFuckHRAPIClient",
    "MockJobsAPIClient",
    "get_fuckhr_client",
    "get_jobs_client",
]
