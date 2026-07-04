"""Higashikawa competitor tracker — full parity with maruko/villa.

Sources: Airbnb calendar API (Peak, Crane), niseu official calendar (3 bldgs),
Jalan vacancy (perican, andon). Each building is a tracked "unit".

Outputs 4 Notion DBs (phase 2, needs NOTION_TOKEN + NOTION_PARENT_PAGE_ID):
  每日紀錄 / 90天行事曆 / 真實入住歷史 / 入住彙總
Metrics: forward 7/30/60/90d occupancy, booked nights, day-over-day new
bookings & cancellations, Booking.com reference price (Peak/perican),
estimated 60d revenue, per-source failure transparency.

Usage:  python tracker.py dryrun   |   python tracker.py
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from properties import PROPERTIES
from airbnb_calendar import fetch_airbnb_calendar
from jalan_calendar import fetch_jalan_calendar
from niseu_calendar import fetch_niseu_calendar
from prices import fetch_booking_prices, BOOKING_SLUGS
from occupancy import (forward_occupancy, booked_nights, diff_velocity,
                       pick_quote_night)

JST = timezone(timedelta(hours=9))
WINDOWS = [7, 30, 60, 90]
WEEKDAY = ["月", "火", "水", "木", "金", "土", "日"]
SNAP_DIR = Path(__file__).parent / "snapshots"


def unit_key(label, building):
    return (f"{label}__{building}".replace("/", "_").replace(" ", "_")
            .replace("　", "_"))


def unit_name(label, building):
    return f"{label} / {building}"


def collect(prop):
    """Return ({building: {iso: available_bool}}, status, fail_detail)."""
    src = prop["source"]
    try:
        if src == "airbnb":
            cal = fetch_airbnb_calendar(prop["id"])
            if not cal:
                raise RuntimeError("empty calendar (no public availability)")
            return {prop["buildings"][0]: cal}, "OK", ""
        if src == "jalan":
            cal = fetch_jalan_calendar(prop["id"])
            if not cal:
                raise RuntimeError("empty jalan calendar")
            return {prop["buildings"][0]: cal}, "OK", ""
        if src == "niseu":
            raw = fetch_niseu_calendar()
            if not raw:
                raise RuntimeError("empty niseu calendar")
            per = {b: {} for b in prop["buildings"]}
            for d, bmap in raw.items():
                for b, v in bmap.items():
                    if b in per:
                        per[b][d] = v
            return per, "OK", ""
    except Exception as e:  # noqa: BLE001
        return {}, "失敗", f"{src}: {str(e)[:200]}"
    return {}, "失敗", "unknown source"


def save_snapshot(uk, today, cal, booking, scraped_at):
    d = SNAP_DIR / today.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{uk}.json").write_text(json.dumps({
        "unit_key": uk, "snapshot_date": today.isoformat(),
        "scraped_at_utc": scraped_at, "calendar": cal, "booking": booking,
    }, ensure_ascii=False))


def load_prev_calendar(uk, today):
    if not SNAP_DIR.exists():
        return None
    days = sorted(p.name for p in SNAP_DIR.iterdir()
                  if p.is_dir() and p.name < today.isoformat())
    for day in reversed(days):
        f = SNAP_DIR / day / f"{uk}.json"
        if f.exists():
            try:
                return json.loads(f.read_text()).get("calendar")
            except Exception:  # noqa: BLE001
                continue
    return None


def all_snapshots():
    out = {}
    if not SNAP_DIR.exists():
        return out
    for day_dir in sorted(SNAP_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        cals = {}
        for f in day_dir.glob("*.json"):
            if f.name in ("daily.json",):
                continue
            try:
                snap = json.loads(f.read_text())
                if "unit_key" in snap:
                    cals[snap["unit_key"]] = snap.get("calendar", {})
            except Exception:  # noqa: BLE001
                continue
        if cals:
            out[day_dir.name] = cals
    return out


def realized_history(today):
    """{night: {"src": day, "status": {unit_key: avail}}} for past nights.

    Truth of night D = availability from the latest snapshot strictly before D
    (avoids same-day checkout-only noise)."""
    snaps = all_snapshots()
    snap_dates = sorted(snaps)
    nights = set()
    for cals in snaps.values():
        for cal in cals.values():
            nights.update(cal.keys())
    hist = {}
    for night in sorted(nights):
        if night >= today.isoformat():
            continue
        prior = [s for s in snap_dates if s < night]
        if not prior:
            continue
        src = prior[-1]
        row = {uk: cal[night] for uk, cal in snaps[src].items() if night in cal}
        if row:
            hist[night] = {"src": src, "status": row}
    return hist


def main(dry=False):
    today = datetime.now(JST).date()
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"=== higashikawa-tracker {scraped_at} (today {today}) dry={dry} ===\n")

    # 1. availability per property
    prop_cal, prop_status = {}, {}
    for prop in PROPERTIES:
        data, st, fail = collect(prop)
        prop_cal[prop["label"]] = data
        prop_status[prop["label"]] = (st, fail)

    # 2. Booking reference prices (Peak/perican); quote night from own calendar
    quote = {}
    for prop in PROPERTIES:
        lbl = prop["label"]
        if lbl in BOOKING_SLUGS:
            cal = prop_cal[lbl].get(prop["buildings"][0], {})
            quote[lbl] = pick_quote_night(cal, today)
    booking = fetch_booking_prices(quote) if quote else {}

    # 3. assemble daily rows + units + snapshots
    daily, units = [], []
    for prop in PROPERTIES:
        lbl, src = prop["label"], prop["source"]
        st, fail = prop_status[lbl]
        binfo = booking.get(lbl, {})
        ref_price = binfo.get("price")
        if lbl not in BOOKING_SLUGS:
            bstatus = "無"
        elif binfo.get("error"):
            bstatus = "失敗"
        elif binfo.get("sold_out") and ref_price is None:
            bstatus = "部分"
        elif ref_price is not None:
            bstatus = "OK"
        else:
            bstatus = "失敗"
        fail_bits = [fail] if fail else []
        if binfo.get("error"):
            fail_bits.append(f"Booking: {binfo['error']}")

        for bldg in prop["buildings"]:
            uk, uname = unit_key(lbl, bldg), unit_name(lbl, bldg)
            cal = prop_cal[lbl].get(bldg, {})
            units.append({"uk": uk, "name": uname, "label": lbl,
                          "building": bldg, "source": src, "cal": cal,
                          "ref_price": ref_price})
            row = {"name": uname, "label": lbl, "building": bldg,
                   "source": src, "source_status": st,
                   "booking_status": bstatus, "ref_price": ref_price,
                   "fail_detail": "; ".join(fail_bits),
                   "occ": {w: None for w in WINDOWS},
                   "booked_60": None, "new_book": None, "cancel": None,
                   "est_rev_60": None}
            if cal:
                row["occ"] = {w: forward_occupancy(cal, w)["pct"]
                              for w in WINDOWS}
                row["booked_60"] = booked_nights(cal, 60)
                nb, cx = diff_velocity(cal, load_prev_calendar(uk, today), today)
                row["new_book"], row["cancel"] = nb, cx
                row["est_rev_60"] = (ref_price * row["booked_60"]
                                     if ref_price is not None else None)
                save_snapshot(uk, today, cal, binfo, scraped_at)
            daily.append(row)

    # 4. realized history (from accumulated snapshots)
    hist = realized_history(today)

    # 5. report
    for r in daily:
        occ = f"{r['occ'][90]}%" if r["occ"][90] is not None else "—"
        price = f"¥{r['ref_price']:,}" if r["ref_price"] else "—"
        vel = ""
        if r["new_book"] is not None:
            vel = f" +{r['new_book']}/-{r['cancel']}"
        print(f"  {r['name']}: {r['source_status']} occ90={occ} "
              f"Booking={r['booking_status']} price={price}{vel}"
              + (f"  ⚠ {r['fail_detail']}" if r["fail_detail"] else ""))

    d = SNAP_DIR / today.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / "daily.json").write_text(json.dumps(daily, ensure_ascii=False, indent=1))
    print(f"\nsnapshot -> {d}/  ({len(daily)} unit-rows, {len(hist)} past nights)")

    if dry:
        print("(dry run — Notion not written)")
        return

    try:
        from notion_sync import write_all
        write_all(today, daily, units, hist, WEEKDAY)
    except Exception as e:  # noqa: BLE001
        print(f"  Notion: error {e}")


if __name__ == "__main__":
    main(dry="dryrun" in sys.argv)
