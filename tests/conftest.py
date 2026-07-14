"""Shared test fixtures."""

import pytest

from chaosblade.common.center.manager_factory import ManagerFactory


@pytest.fixture(autouse=True)
def reset_managers():
    """Reset all managers before each test to avoid state leakage."""
    ManagerFactory.load()
    yield
    ManagerFactory.unload()
