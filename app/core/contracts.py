"""Ortak veri modelleri ve arayüzler (Faz 0 — Kontratlar).

Bu modül tüm Stream'lerin (A: config/paths, B: yt-dlp etkileşimi,
C: kuyruk, D: UI) paylaştığı tek kaynak. Yalnızca standart kütüphaneye
bağlıdır; PySide6 importu yoktur. Somut signal'lı sınıflar (QObject)
ilgili Stream'lerde yazılır, burada yalnızca davranış sözleşmesi
(`Protocol`) tarif edilir.

Tasarım notları:
- `DownloadOptions` → "Introduce Parameter Object" refactoring tekniği.
- Enum'lar → "Replace Magic Number/String with Symbolic Constant".
- `Protocol` arayüzleri → Stream'ler birbirini beklemeden mock'a karşı
  geliştirilebilir (gevşek bağlılık).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Enum'lar
# ---------------------------------------------------------------------------


class DownloadMode(StrEnum):
    """İndirme türü. Strategy seçimini belirler."""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


class JobState(StrEnum):
    """Kuyruk işinin yaşam döngüsü (State deseni geçişleri)."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        """İş bitti mi (sıradaki başlatılabilir mi)?"""
        return self in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELED)


class CookieSource(StrEnum):
    """Çerez modülünün kaynağı."""

    NONE = "none"
    BROWSER = "browser"
    FILE = "file"


class AppPhase(StrEnum):
    """Ana ekranın UI durumu (handoff state machine ile uyumlu).

    UI'ya özeldir (Stream D sahibi); çekirdek için zorunlu değil ama
    tutarlılık için sözleşmede tutulur.
    """

    EMPTY = "empty"  # henüz URL yok / fetch yapılmadı
    FETCHING = "fetching"  # metadata çekiliyor
    LOADED = "loaded"  # media card dolu


class ErrorKind(StrEnum):
    """`errors.map_stderr()` çıktısının sınıfı (UI davranışını yönlendirir)."""

    AGE_RESTRICTED = "age_restricted"
    FORMAT_UNAVAILABLE = "format_unavailable"
    UNAVAILABLE = "unavailable"
    FFMPEG_MISSING = "ffmpeg_missing"
    NETWORK = "network"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


# Mantıksal kalite ön ayarları (UI çipleri ile eşleşir).
PRESET_BEST = "best"
PRESET_1080P = "1080p"
PRESET_720P = "720p"
PRESET_480P = "480p"
PRESET_AUDIO = "audio"

# yt-dlp wiki: PO token / çerez yardımı için kullanıcıya gösterilecek link.
PO_TOKEN_HELP_URL = "https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"


# ---------------------------------------------------------------------------
# Veri modelleri
# ---------------------------------------------------------------------------


@dataclass
class DownloadOptions:
    """Tek bir indirme işinin tüm parametreleri (Parameter Object).

    `command_builder` bu nesneden yt-dlp argümanlarını üretir.
    """

    url: str
    mode: DownloadMode = DownloadMode.VIDEO

    # Format seçimi: ya elle `format_id`, ya da mantıksal `preset`.
    format_id: str | None = None
    preset: str | None = PRESET_BEST

    # Çıktı dizinleri (Config bunları `base_dir / subfolder` olarak çözer).
    video_dir: Path = field(default_factory=lambda: Path("videos"))
    audio_dir: Path = field(default_factory=lambda: Path("musics"))
    output_template: str = "%(title)s.%(ext)s"

    # Ses
    audio_format: str = "opus"

    # Çerez modülü
    cookie_source: CookieSource = CookieSource.NONE
    browser: str | None = None
    cookies_file: Path | None = None

    # Altyazı
    subtitle_langs: list[str] = field(default_factory=lambda: ["en", "tr"])
    write_auto_subs: bool = False
    embed_subs: bool = False

    # Gömme
    embed_thumbnail: bool = False
    embed_metadata: bool = False

    # Hız
    concurrent_fragments: int = 4

    def target_dir(self) -> Path:
        """Moda göre çıktı klasörü."""
        return self.audio_dir if self.mode == DownloadMode.AUDIO else self.video_dir


@dataclass
class Progress:
    """Tek indirmenin anlık ilerlemesi (runner → UI, Observer)."""

    status: str = "downloading"
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None  # bayt/sn
    eta: int | None = None  # saniye
    indeterminate: bool = False  # toplam boyut bilinmiyorsa True

    @property
    def percent(self) -> float | None:
        """0–100 arası yüzde; toplam bilinmiyorsa None."""
        if self.indeterminate or not self.total_bytes or self.downloaded_bytes is None:
            return None
        return min(100.0, self.downloaded_bytes / self.total_bytes * 100.0)


@dataclass
class AppError:
    """Kullanıcıya gösterilecek dostça hata (errors.map_stderr çıktısı)."""

    kind: ErrorKind = ErrorKind.UNKNOWN
    user_message: str = ""
    raw: str = ""
    hint_url: str | None = None


@dataclass
class FormatInfo:
    """Format tablosunun tek satırı (`yt-dlp -J` formats öğesinden)."""

    format_id: str
    ext: str = ""
    resolution: str = ""  # "1920x1080" veya "audio only"
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    filesize: int | None = None  # bayt (filesize | filesize_approx)
    tbr: float | None = None  # toplam bit hızı (kbps)
    note: str = ""  # format_note (örn. "1080p60", "DASH audio")


@dataclass
class MediaInfo:
    """Tek videonun meta bilgisi (media card için; `yt-dlp -J` üst düzey alanlar).

    `IFormatFetcher.fetch_formats` bunu format listesiyle birlikte döndürür.
    """

    title: str
    channel: str = ""
    duration: int | None = None  # saniye
    thumbnail_url: str = ""
    webpage_url: str = ""
    needs_cookies: bool = False  # yaş sınırı/giriş gerekiyor mu (sezgisel)
    subtitle_langs: list[str] = field(default_factory=list)  # manuel altyazı dilleri
    auto_caption_langs: list[str] = field(default_factory=list)  # otomatik altyazı dilleri


@dataclass
class PlaylistItem:
    """`--flat-playlist` ile çekilen tek öğe; her biri ayrı işe açılır."""

    id: str
    title: str
    url: str


@dataclass
class BinaryStatus:
    """yt-dlp/ffmpeg konum çözümünün sonucu (paths.resolve_*)."""

    found: bool
    path: Path | None = None
    version: str | None = None  # splash + Settings "Binaries" durum satırı
    message: str = ""
    download_url: str = ""


# ---------------------------------------------------------------------------
# Config şeması (Stream A — config.py bunu kaynak alır)
# ---------------------------------------------------------------------------

#: Tüm ayar alanları + varsayılanları tek yerde. config.py yükleme/migrasyonda
#: bunu temel alır; eksik/bilinmeyen alanlar buraya göre düşer.
CONFIG_DEFAULTS: dict[str, object] = {
    "base_dir": r"C:\yt-dlp",
    "video_subfolder": "videos",
    "audio_subfolder": "musics",
    "cookies_enabled": False,
    "cookies_source": CookieSource.BROWSER.value,
    "browser_choice": "chrome",
    "cookies_file_path": "",
    "default_preset": PRESET_BEST,
    "audio_format": "opus",
    "subtitle_langs": ["en", "tr"],
    "write_auto_subs": False,
    "embed_subs": False,
    "embed_thumbnail": False,
    "embed_metadata": False,
    "concurrent_fragments": 4,
    "max_concurrent_downloads": 2,  # aynı anda en fazla N indirme
    "ytdlp_path": "",  # boş → otomatik çözüm (paths.py)
    "ffmpeg_path": "",
    # Görünüm (handoff) — Stream D kullanır
    "accent_theme": "purple",  # purple | indigo | pink
    "dock_style": "ring",  # ring | bar
    "reduced_motion": False,
}


# ---------------------------------------------------------------------------
# Soyut arayüzler (Protocol) — Stream'ler bunlara karşı geliştirir
# ---------------------------------------------------------------------------

# Observer geri çağrı imzaları (somut sınıflar Qt signal'larıyla karşılar).
ProgressCallback = Callable[[Progress], None]
LogCallback = Callable[[str], None]
FinishedCallback = Callable[[JobState, AppError | None], None]


@runtime_checkable
class IYtDlpRunner(Protocol):
    """Tek bir indirme işini yürüten bileşen (Facade + Adapter).

    Somut implementasyon (`ytdlp_runner.YtDlpRunner`) bir QObject olup
    aşağıdaki geri çağrıları Qt signal'larıyla yayınlar. Mock implementasyon
    test/CI ve UI iskeleti için kullanılır.
    """

    def start(self, options: DownloadOptions) -> None:
        """İndirmeyi başlat (asenkron)."""
        ...

    def cancel(self) -> None:
        """Aktif indirmeyi iptal et (.part dosyası korunur)."""
        ...

    def set_callbacks(
        self,
        on_progress: ProgressCallback,
        on_log: LogCallback,
        on_finished: FinishedCallback,
    ) -> None:
        """Observer geri çağrılarını bağla (Qt signal köprüsü).

        Kullanım kalıbı: önce `set_callbacks(...)`, sonra `start(options)`.
        """
        ...


#: Her kuyruk işi için yeni bir tek-iş runner üretir. QueueManager bunu
#: enjekte alır (gerçek `YtDlpRunner` fabrikası veya test mock'u) ve N=2
#: eşzamanlı indirme için her aktif işe ayrı runner örnekler.
RunnerFactory = Callable[[], IYtDlpRunner]


@runtime_checkable
class IFormatFetcher(Protocol):
    """Format/metadata ve playlist çekimi (asenkron)."""

    def fetch_formats(
        self,
        url: str,
        on_done: Callable[[MediaInfo, list[FormatInfo]], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        """Tek video için meta + mevcut formatları çek (media card'ı besler)."""
        ...

    def expand_playlist(
        self,
        url: str,
        on_done: Callable[[list[PlaylistItem]], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        """Playlist URL'ini öğelerine aç (--flat-playlist)."""
        ...


@runtime_checkable
class IConfig(Protocol):
    """Ayar kalıcılığı (Stream A)."""

    def get(self, key: str) -> object: ...

    def set(self, key: str, value: object) -> None: ...

    def save(self) -> None: ...
