"""UI-test-local fixtures: an in-memory IConfig and a built MainWindow.

These do not touch the shared tests/conftest.py (owned by Stream T); they only
add UI-only helpers layered on top of the mock fetcher/runner fixtures there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from app.core.contracts import CONFIG_DEFAULTS


@dataclass
class MemoryConfig:
    """In-memory IConfig implementation seeded with CONFIG_DEFAULTS."""

    _data: dict[str, object] = field(default_factory=lambda: dict(CONFIG_DEFAULTS))
    saved: int = 0

    def get(self, key: str) -> object:
        return self._data.get(key)

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def save(self) -> None:
        self.saved += 1


@pytest.fixture
def mock_config() -> MemoryConfig:
    cfg = MemoryConfig()
    # keep animations effectively instant in tests
    cfg.set("reduced_motion", True)
    return cfg


@pytest.fixture
def window(qtbot, mock_fetcher, mock_runner_factory, mock_config):  # type: ignore[no-untyped-def]
    from app.main_window import MainWindow

    win = MainWindow(mock_fetcher, mock_runner_factory, mock_config, reduced_motion=True)
    qtbot.addWidget(win)
    win.show()
    return win
