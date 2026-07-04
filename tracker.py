"""Higashikawa competitor tracker — phase 1 (5 confirmed properties).

Sources: Airbnb calendar API (Peak, Crane), niseu official calendar,
Jalan vacancy (perican, andon). Computes forward 7/30/60/90d occupancy and
writes a daily snapshot. Notion write is phase 2 (needs NOTION_TOKEN).

Usage:
    python tracker.py dryrun   # fetch + compute + snapshot, no Notion
    python tracker.py          # same + Notion write (phase 2)
"""
import json
import sys
from datetime import date
from pathlib import Path

from properties import PROPERTIES
from airbnb_calendar import fetch_airbnb_calendar
from jalan_calendar import fetch_jalan_calendar
from niseu_calendar import fetch_niseu_calendar
from occupancy import forward_occupancy

WINDOWS = [7, 30, 60, 90]
SNAP_DIR = Path(__file__).parent / "snapshots"


def collect(prop):
    """Return {building: {iso: available_bool}} for one property."""
    src = prop["source"]
    if src == "airbnb":
        return {prop["buildings"][0]: fetch_airbnb_calendar(prop["id"])}
    if src == "jalan":
        return {prop["buildings"][0]: fetch_jalan_calendar(prop["id"])}
    if src == "niseu":
        raw = fetch_niseu_calendar()
        per = {b: {} for b in prop["buildings"]}
        for d, bmap in raw.items():
            for b, v in bmap.items():
                if b in per:
                    per[b][d] = v
        return per
    return {}


def main(dry=False):
    today = date.today().isoformat()
    snap, rows = {}, []
    print(f"=== higashikawa-tracker {today} (dry={dry}) ===\n")
    for prop in PROPERTIES:
        label = prop["label"]
        try:
            data = collect(prop)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {label:22s} {prop['source']}: {e}")
            continue
        snap[label] = data
        for bldg, cal in data.items():
            if not cal:
                print(f"[----] {label} / {bldg}: no calendar data ({prop['source']})")
                continue
            occ = {w: forward_occupancy(cal, w)["pct"] for w in WINDOWS}
            occ_s = "  ".join(
                f"{w}d={occ[w]}%" if occ[w] is not None else f"{w}d=—"
                for w in WINDOWS)
            print(f"[ OK ] {label} / {bldg}: {len(cal)}d  {occ_s}")
            rows.append({"label": label, "building": bldg,
                         "source": prop["source"], "nights": len(cal), "occ": occ})

    d = SNAP_DIR / today
    d.mkdir(parents=True, exist_ok=True)
    (d / "snapshot.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1))
    (d / "occupancy.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"\nsnapshot -> {d}/  ({len(rows)} building-rows)")

    if not dry:
        from notion_sync import write_notion  # phase 2
        write_notion(today, rows, snap)


if __name__ == "__main__":
    main(dry="dryrun" in sys.argv)
