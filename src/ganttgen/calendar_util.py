"""Working-day calendar arithmetic."""

from __future__ import annotations

from datetime import date, timedelta

from .models import Config


def is_working(d: date, config: Config) -> bool:
    return d.weekday() not in config.weekends and d not in config.holiday_dates


def snap_back_to_working(d: date, config: Config) -> date:
    while not is_working(d, config):
        d -= timedelta(days=1)
    return d


def snap_forward_to_working(d: date, config: Config) -> date:
    while not is_working(d, config):
        d += timedelta(days=1)
    return d


def add_working_days(start: date, n: int, config: Config) -> date:
    """Return the date n working days after start (n >= 0). n=0 => start."""
    if n < 0:
        raise ValueError("n must be >= 0")
    d = start
    stepped = 0
    while stepped < n:
        d += timedelta(days=1)
        if is_working(d, config):
            stepped += 1
    return d


def shift_working_days(d: date, n: int, config: Config) -> date:
    """Move `d` by n working days (n may be negative). `d` should be working."""
    if n == 0:
        return d
    if n > 0:
        return add_working_days(d, n, config)
    stepped = 0
    while stepped < -n:
        d -= timedelta(days=1)
        if is_working(d, config):
            stepped += 1
    return d


def working_day_delta(a: date, b: date, config: Config) -> int:
    """Signed working-day steps from a to b (both working). shift(a, delta) == b."""
    if a == b:
        return 0
    if b > a:
        n = 0
        d = a
        while d < b:
            d += timedelta(days=1)
            if is_working(d, config):
                n += 1
        return n
    return -working_day_delta(b, a, config)


def iter_days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)
