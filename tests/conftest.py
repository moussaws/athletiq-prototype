"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--runslow", action="store_true", default=False, help="run slow/cv tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="need --runslow")
    skip_cv = pytest.mark.skip(reason="CV extras not installed / need --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
        if "cv" in item.keywords:
            item.add_marker(skip_cv)
