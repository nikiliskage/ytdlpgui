"""Dock: a long queue scrolls inside the dock instead of widening the window."""

from __future__ import annotations

from app.core import contracts as c
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent


def _fill(window, n: int) -> list[str]:  # type: ignore[no-untyped-def]
    ids = [f"job-{i}" for i in range(n)]
    for job_id in ids:
        window.dock.add_item(job_id, f"Track {job_id}")
    return ids


def test_many_items_do_not_widen_the_window(window, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.resize(1100, 780)
    _fill(window, 40)
    qtbot.wait(20)
    assert window.minimumSizeHint().width() <= 1100
    assert window.width() == 1100
    dock = window.dock
    assert dock.expand_btn.geometry().right() <= dock.width()
    assert dock._stat.geometry().right() <= dock.width()  # noqa: SLF001


def test_running_item_is_scrolled_into_view(window, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.resize(1100, 780)
    ids = _fill(window, 40)
    qtbot.wait(20)
    bar = window.dock.strip_scroll.horizontalScrollBar()
    assert bar.value() == 0
    window.dock.set_state(ids[-1], c.JobState.RUNNING)
    assert bar.value() > 0


def test_vertical_wheel_scrolls_sideways(window, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.resize(1100, 780)
    _fill(window, 40)
    qtbot.wait(20)
    scroll = window.dock.strip_scroll
    bar = scroll.horizontalScrollBar()
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(scroll.mapToGlobal(QPoint(10, 10))),
        QPoint(0, 0),
        QPoint(0, -240),  # wheel down
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    scroll.wheelEvent(event)
    assert bar.value() > 0


def test_context_menu_rename_only_for_renamable_jobs(window) -> None:  # type: ignore[no-untyped-def]
    dock = window.dock
    dock.add_item("a", "A")
    dock.set_state("a", c.JobState.COMPLETED)
    menu = dock.build_menu("a")
    actions = {a.text(): a for a in menu.actions() if a.text()}
    assert not actions["Rename…"].isEnabled()
    assert actions["Open folder"].isEnabled()

    dock.set_renamable("a", True)
    actions = {a.text(): a for a in dock.build_menu("a").actions() if a.text()}
    assert actions["Rename…"].isEnabled()
