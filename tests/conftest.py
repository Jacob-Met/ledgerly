import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerly.agent import Agent  # noqa: E402
from ledgerly.paypal import SandboxMock  # noqa: E402

FIXTURES = ROOT / "fixtures"
INVOICER = {"name": "Jacob Scott-Metoyer", "email_address": "jacob@ledgerly.example"}


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class Clock:
    def __init__(self, d: date):
        self.d = d

    def __call__(self) -> date:
        return self.d


@pytest.fixture
def clock():
    return Clock(date(2026, 10, 1))


@pytest.fixture
def mock():
    return SandboxMock()


@pytest.fixture
def agent(mock, clock):
    return Agent(mock, INVOICER, today=clock)
