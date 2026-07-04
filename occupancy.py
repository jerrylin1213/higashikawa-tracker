"""Forward occupancy from an availability map."""
from datetime import date, timedelta


def forward_occupancy(avail_map, days, start=None):
    """avail_map: {iso: available_bool}. Count booked share over the next
    `days` nights starting tomorrow. Returns dict(booked, total, pct)."""
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
