"""Shared fixtures. Nothing here needs an API key or a network connection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citychat.config import Settings  # noqa: E402
from citychat.context import CityContext  # noqa: E402


def pytest_report_header(config):
    return f"city-chatbot tests, repo root {ROOT}"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        api_key="test-key",
        data_dir=ROOT / "data",
        knowledge_dir=ROOT / "knowledge",
        city="milan",
    )


@pytest.fixture(scope="session")
def context(settings: Settings) -> CityContext:
    if not (settings.cities_dir / "milan" / "meta.json").exists():
        pytest.skip("run scripts/prepare_city.py first")
    return CityContext(settings)
