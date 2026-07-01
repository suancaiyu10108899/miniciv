# prototype/conftest.py — pytest 共享 fixtures

import pytest
from prototype.mapgen import generate_map
from prototype.constants import DEFAULT_SIZE


@pytest.fixture
def balanced_map_30():
    """30×30 balanced 地图，固定 seed=42"""
    return generate_map(seed=42, size=30, generator_id="balanced")


@pytest.fixture
def small_map_15():
    """15×15 balanced 地图"""
    return generate_map(seed=1, size=15, generator_id="balanced")


@pytest.fixture
def symmetric_map_30():
    """30×30 symmetric 地图"""
    return generate_map(seed=42, size=30, generator_id="symmetric")
