"""Test-suite compatibility helpers.

The production package keeps test runners optional.  This lightweight hook
lets the repository's async tests run in a bare ``pytest`` environment as
well as with ``pytest-asyncio`` installed.
"""

import asyncio
import inspect
from typing import Any

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: Any) -> bool | None:
    """Run coroutine test functions without requiring an external plugin."""
    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None

    fixture_arguments = {
        name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(test_function(**fixture_arguments))
    return True
