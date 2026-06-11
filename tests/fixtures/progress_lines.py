"""`--progress-template` örnek satırları + beklenen ayrıştırma.

Şablon: ``PROG|status|downloaded|total|total_est|speed|eta``
Boş/bilinmeyen alanlar yt-dlp'de varsayılan ``NA`` placeholder'ı ile gelir.
Stream B `parse_progress_line()` testleri bunu kullanır.
"""

# (satır, beklenen) — beklenen alanlar parse_progress_line çıktısıyla karşılaştırılır.
CASES: list[tuple[str, dict]] = [
    # Normal: tüm alanlar dolu.
    (
        "PROG|downloading|1048576|10485760|10485760|524288.0|18",
        {
            "status": "downloading",
            "downloaded_bytes": 1048576,
            "total_bytes": 10485760,
            "speed": 524288.0,
            "eta": 18,
            "indeterminate": False,
        },
    ),
    # total yok ama total_estimate var → estimate kullanılır, belirli.
    (
        "PROG|downloading|2097152|NA|10485760|600000.0|14",
        {
            "downloaded_bytes": 2097152,
            "total_bytes": 10485760,
            "indeterminate": False,
        },
    ),
    # İkisi de yok → belirsiz, total None.
    (
        "PROG|downloading|3145728|NA|NA|450000.0|NA",
        {
            "downloaded_bytes": 3145728,
            "total_bytes": None,
            "eta": None,
            "indeterminate": True,
        },
    ),
    # Bitti.
    (
        "PROG|finished|10485760|10485760|10485760|NA|0",
        {
            "status": "finished",
            "downloaded_bytes": 10485760,
            "total_bytes": 10485760,
            "eta": 0,
        },
    ),
]

# PROG| önekiyle başlamayan satırlar (log) → None döndürmeli.
NON_PROGRESS_LINES: list[str] = [
    "[youtube] dQw4w9WgXcQ: Downloading webpage",
    "[download] Destination: videos\\Sample Video.mp4",
    '[Merger] Merging formats into "videos\\Sample Video.mp4"',
    "",
]

# stdout'un satır ortasından bölündüğü senaryo: iki parça birleşince tam satır.
SPLIT_CHUNKS: list[str] = [
    "PROG|downloading|1048576|10485760|10",
    "485760|524288.0|18\n",
]
