"""Factory for creating M2M API clients based on configuration."""

from src.core.config import settings
from src.domain.interfaces import M2MClient
from src.infrastructure.m2m.clients import FuckHRAPIClient, JobsAPIClient
from src.infrastructure.m2m.mock_clients import (
    MockFuckHRAPIClient,
    MockJobsAPIClient,
)


def get_fuckhr_client() -> M2MClient:
    """Get FuckHR API client instance.

    Returns appropriate client based on USE_MOCKS setting:
    - MockFuckHRAPIClient if USE_MOCKS=true
    - FuckHRAPIClient if USE_MOCKS=false (default)

    Returns:
        M2MClient: FuckHR API client instance.
    """
    if settings.use_mocks:
        return MockFuckHRAPIClient()
    return FuckHRAPIClient()


def get_jobs_client() -> M2MClient:
    """Get Jobs API client instance.

    Returns appropriate client based on USE_MOCKS setting:
    - MockJobsAPIClient if USE_MOCKS=true
    - JobsAPIClient if USE_MOCKS=false (default)

    Returns:
        M2MClient: Jobs API client instance.
    """
    if settings.use_mocks:
        return MockJobsAPIClient()
    return JobsAPIClient()
