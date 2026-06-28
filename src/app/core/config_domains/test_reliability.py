"""Domínio: Test Reliability Program (Missão 84)."""

from pydantic import BaseModel


class TestReliabilityConfig(BaseModel):
    test_reliability_max_retries: int = 3
    test_reliability_track_flaky: bool = True
