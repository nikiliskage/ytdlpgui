"""fly_to_dock finishes under reduced motion and deletes its temp widget."""

from __future__ import annotations

from app.widgets.fly_to_dock import fly_to_dock
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget


def test_fly_to_dock_cleans_up(qtbot) -> None:  # type: ignore[no-untyped-def]
    host = QWidget()
    host.resize(400, 300)
    qtbot.addWidget(host)
    host.show()

    done: list[bool] = []
    ghost = fly_to_dock(
        host,
        QPoint(10, 10),
        QPoint(300, 250),
        reduced_motion=True,
        on_finished=lambda: done.append(True),
    )
    # under reduced motion the animation is ~instant; wait for cleanup
    qtbot.waitUntil(lambda: done == [True], timeout=1000)
    # ghost marked deleted + scheduled for deletion (no leak)
    assert ghost.deleted is True
