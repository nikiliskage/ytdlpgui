"""Ortak pytest fixture'ları (Stream T sahipliğinde).

Buradaki mock'lar `app.core.contracts` arayüzlerini (Protocol) yapısal olarak
karşılar; gerçek implementasyonlar gelmeden Stream A/B/C/D bunlara karşı test
yazar. QueueManager yalnızca `set_callbacks(...)` + `start()` köprüsünü kullandığı
için mock'lar saf Python'dur (Qt event-loop'u zorunlu değil) ve **kendiliğinden
bitmez** — testler bitişi `finish()` ile elle tetikler; böylece N=2 eşzamanlılık
yarışı deterministik test edilir.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from app.core import contracts as c

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Mock runner (IYtDlpRunner) + factory (RunnerFactory)
# ---------------------------------------------------------------------------


@dataclass
class MockRunner:
    """Elle tetiklenebilir tek-iş runner taklidi."""

    options: c.DownloadOptions | None = None
    started: bool = False
    canceled: bool = False
    _on_progress: c.ProgressCallback | None = None
    _on_log: c.LogCallback | None = None
    _on_finished: c.FinishedCallback | None = None

    # IYtDlpRunner ------------------------------------------------------------
    def set_callbacks(
        self,
        on_progress: c.ProgressCallback,
        on_log: c.LogCallback,
        on_finished: c.FinishedCallback,
    ) -> None:
        self._on_progress = on_progress
        self._on_log = on_log
        self._on_finished = on_finished

    def start(self, options: c.DownloadOptions) -> None:
        self.options = options
        self.started = True

    def cancel(self) -> None:
        self.canceled = True

    # Test-facing triggers ----------------------------------------------------
    def emit_progress(self, progress: c.Progress) -> None:
        assert self._on_progress is not None, "set_callbacks() çağrılmadı"
        self._on_progress(progress)

    def emit_log(self, line: str) -> None:
        assert self._on_log is not None
        self._on_log(line)

    def finish(
        self, state: c.JobState = c.JobState.COMPLETED, error: c.AppError | None = None
    ) -> None:
        assert self._on_finished is not None
        self._on_finished(state, error)


@dataclass
class MockRunnerFactory:
    """`RunnerFactory` taklidi; üretilen runner'ları kaydeder."""

    created: list[MockRunner] = field(default_factory=list)

    def __call__(self) -> MockRunner:
        runner = MockRunner()
        self.created.append(runner)
        return runner


@pytest.fixture
def mock_runner() -> MockRunner:
    return MockRunner()


@pytest.fixture
def mock_runner_factory() -> MockRunnerFactory:
    return MockRunnerFactory()


# ---------------------------------------------------------------------------
# Mock fetcher (IFormatFetcher)
# ---------------------------------------------------------------------------


@dataclass
class MockFetcher:
    """`IFormatFetcher` taklidi; varsayılan başarı, istenirse hata döndürür."""

    media: c.MediaInfo = field(default_factory=lambda: c.MediaInfo(title="Sample Video"))
    formats: list[c.FormatInfo] = field(
        default_factory=lambda: [c.FormatInfo(format_id="22", ext="mp4", resolution="1280x720")]
    )
    playlist: list[c.PlaylistItem] = field(default_factory=list)
    fail_with: c.AppError | None = None

    def fetch_formats(
        self,
        url: str,
        on_done: Callable[[c.MediaInfo, list[c.FormatInfo]], None],
        on_error: Callable[[c.AppError], None],
    ) -> None:
        if self.fail_with is not None:
            on_error(self.fail_with)
        else:
            on_done(self.media, self.formats)

    def expand_playlist(
        self,
        url: str,
        on_done: Callable[[list[c.PlaylistItem]], None],
        on_error: Callable[[c.AppError], None],
    ) -> None:
        if self.fail_with is not None:
            on_error(self.fail_with)
        else:
            on_done(self.playlist)


@pytest.fixture
def mock_fetcher() -> MockFetcher:
    return MockFetcher()


# ---------------------------------------------------------------------------
# Veri / config fixture'ları
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_options(tmp_path: Path) -> c.DownloadOptions:
    return c.DownloadOptions(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        video_dir=tmp_path / "videos",
        audio_dir=tmp_path / "musics",
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_dump() -> dict:
    return json.loads((FIXTURES / "sample_dump.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_flat() -> dict:
    return json.loads((FIXTURES / "sample_flat.json").read_text(encoding="utf-8"))


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Geçici dizinde Config. Stream A `Config` yazana kadar testi atlar.

    Sözleşme: Config, `YTDLPGUI_CONFIG_DIR` ortam değişkenini (varsa) config
    dizini olarak kullanır.
    """
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))
    try:
        from app.core.config import Config  # type: ignore[attr-defined]
    except Exception:
        pytest.skip("Config henüz yok (Stream A)")
    return Config()
