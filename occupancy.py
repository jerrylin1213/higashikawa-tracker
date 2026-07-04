"""Occupancy + velocity metrics from an availability map {iso: available_bool}."""
from datetime import date, timedelta


def forward_occupancy(avail_map, days, start=None):
    """Count booked share over the next `days` nights starting tomorrow.
    Returns dict(booked, total, pct)."""
    if start is None:
        start = date.today() + timedelta(days=1)
    booked = total = 0
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        if d in avail_map:
            total += 1
            if not avail_map[d]:
                booked += 1
    pct = round(booked / total * 100) if total else None
    return {"booked": booked, "total": total, "pct": pct}


def booked_nights(avail_map, days, start=None):
    """Number of booked (unavailable) nights in the next `days` nights."""
    if start is None:
        start = date.today() + timedelta(days=1)
    n = 0
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        if d in avail_map and not avail_map[d]:
            n += 1
    return n


def diff_velocity(cur, prev, today):
    """(new_bookings, cancellations) vs previous snapshot, future nights only.
    cur/prev: {iso: available_bool}. Returns (None, None) if no prev."""
    if not prev:
        return None, None
    floor = (today + timedelta(days=1)).isoformat()
    new_book = cancel = 0
    for d, avail in cur.items():
        if d < floor or d not in prev:
            continue
        was, now = prev[d], avail
        if was and not now:
            new_book += 1
        elif not was and now:
            cancel += 1
    return new_book, cancel


def pick_quote_night(avail_map, today, horizon=30):
    """First available night within `horizon` days, for a price quote."""
    for i in range(1, horizon + 1):
        d = today + timedelta(days=i)
        if avail_map.get(d.isoformat()):
            return d
    return None
