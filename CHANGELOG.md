# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added
- Project scaffolding: core contracts (`app/core/contracts.py`), plans, and design handoff.
- Tooling: pytest + pytest-qt, ruff, mypy, GitHub Actions CI (Windows), shared test
  fixtures/mocks, project documentation (README, SECURITY, ARCHITECTURE).

### Planned (see `plans/`)
- Config + binary resolution (Stream A)
- yt-dlp command builder, format fetcher, runner, error mapping (Stream B)
- Download queue, up to 2 concurrent (Stream C)
- UI per high-fidelity design handoff: splash, frameless window, omni-bar, media card,
  download dock, settings slide-over (Stream D)
- Integration + PyInstaller packaging
