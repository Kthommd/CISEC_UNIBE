from __future__ import annotations

from datetime import date

from bot.features.week import compute_week_status


def test_week_before_start():
    status = compute_week_status(date(2025, 9, 1))
    assert status.current_week is None
    assert "inicia" in status.label
    assert status.progress_bar == "░" * 10


def test_week_during_period():
    status = compute_week_status(date(2025, 9, 15))
    assert status.current_week == 2
    assert "Semana" in status.label
    assert len(status.progress_bar) == 10


def test_week_after_period():
    status = compute_week_status(date(2025, 12, 25))
    assert status.current_week == 15
    assert status.progress_bar == "▓" * 10
