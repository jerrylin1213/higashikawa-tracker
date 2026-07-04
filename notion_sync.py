"""Notion sync for higashikawa-tracker — full parity (4 databases).

Auto-creates + maintains under NOTION_PARENT_PAGE_ID:
  每日紀錄     one row per unit per day (occupancy/price/revenue/velocity/status)
  90天行事曆   one row per future night, columns per unit + ref prices
  真實入住歷史 one row per past night (reconstructed from snapshots)
  入住彙總     one row per unit (cumulative realized occupancy)

Skips cleanly if NOTION_TOKEN / NOTION_PARENT_PAGE_ID are unset.
"""
import os
from datetime import date as _date, timedelta

import requests

NOTION_VER = "2022-06-28"
API = "https://api.notion.com/v1"
DAILY_TITLE = "每日紀錄"
CAL_TITLE = "90天行事曆"
HIST_TITLE = "真實入住歷史"
SUMMARY_TITLE = "入住彙總"


def _h(token):
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VER,
            "Content-Type": "application/json"}


def _find_db(page, title, h):
    cur = None
    while True:
        url = f"{API}/blocks/{page}/children?page_size=100"
        if cur:
            url += f"&start_cursor={cur}"
        r = requests.get(url, headers=h, timeout=30)
        r.raise_for_status()
        j = r.json()
        for b in j.get("results", []):
            if b.get("type") == "child_database" and \
                    b["child_database"].get("title") == title:
                return b["id"]
        if not j.get("has_more"):
            return None
        cur = j.get("next_cursor")


def _create_db(page, title, props, h):
    r = requests.post(f"{API}/databases", headers=h, json={
        "parent": {"type": "page_id", "page_id": page},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": props}, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def _get_db(page, title, props, h):
    return _find_db(page, title, h) or _create_db(page, title, props, h)


def _query(db, h, filt=None):
    out, cur = [], None
    while True:
        body = {"page_size": 100}
        if filt:
            body["filter"] = filt
        if cur:
            body["start_cursor"] = cur
        r = requests.post(f"{API}/databases/{db}/query", headers=h,
                          json=body, timeout=30)
        r.raise_for_status()
        j = r.json()
        out += j.get("results", [])
        if not j.get("has_more"):
            return out
        cur = j.get("next_cursor")


def _archive(db, h, filt=None):
    for pg in _query(db, h, filt):
        requests.patch(f"{API}/pages/{pg['id']}", headers=h,
                       json={"archived": True}, timeout=30)


def _post(db, props, h):
    r = requests.post(f"{API}/pages", headers=h,
                      json={"parent": {"database_id": db}, "properties": props},
                      timeout=30)
    if not r.ok:
        print(f"    post fail: {r.status_code} {r.text[:100]}")
    return r.ok


def _pct(v):
    return None if v is None else round(v / 100.0, 4)


def _sel(name):
    return {"select": {"name": name}} if name else {"select": None}


def _rt(s):
    return [{"text": {"content": s[:1900]}}] if s else []


def write_daily(page, today, daily, h):
    props = {
        "紀錄": {"title": {}}, "紀錄日期": {"date": {}},
        "物件": {"select": {}}, "棟": {"select": {}}, "來源": {"select": {}},
        "來源狀態": {"select": {}}, "Booking狀態": {"select": {}},
        "7天入住率": {"number": {"format": "percent"}},
        "30天入住率": {"number": {"format": "percent"}},
        "60天入住率": {"number": {"format": "percent"}},
        "90天入住率": {"number": {"format": "percent"}},
        "未來60天已訂晚數": {"number": {}},
        "今日新增預訂": {"number": {}}, "今日取消": {"number": {}},
        "Booking每晚均價": {"number": {}}, "預估營收60天": {"number": {}},
        "失敗詳情": {"rich_text": {}},
    }
    db = _get_db(page, DAILY_TITLE, props, h)
    _archive(db, h, {"property": "紀錄日期", "date": {"equals": today}})
    n = 0
    for r in daily:
        occ = r["occ"]
        p = {
            "紀錄": {"title": [{"text": {"content": f"{today} — {r['name']}"}}]},
            "紀錄日期": {"date": {"start": today}},
            "物件": _sel(r["label"]), "棟": _sel(r["building"]),
            "來源": _sel(r["source"]), "來源狀態": _sel(r["source_status"]),
            "Booking狀態": _sel(r["booking_status"]),
            "7天入住率": {"number": _pct(occ.get(7))},
            "30天入住率": {"number": _pct(occ.get(30))},
            "60天入住率": {"number": _pct(occ.get(60))},
            "90天入住率": {"number": _pct(occ.get(90))},
            "未來60天已訂晚數": {"number": r["booked_60"]},
            "今日新增預訂": {"number": r["new_book"]},
            "今日取消": {"number": r["cancel"]},
            "Booking每晚均價": {"number": r["ref_price"]},
            "預估營收60天": {"number": r["est_rev_60"]},
            "失敗詳情": {"rich_text": _rt(r["fail_detail"])},
        }
        if _post(db, p, h):
            n += 1
    print(f"  每日紀錄: wrote {n}/{len(daily)} rows")


def write_calendar(page, today, units, weekday, h):
    price_units = [u for u in units if u["ref_price"] is not None]
    props = {"日期": {"title": {}}, "日付": {"date": {}}, "星期": {"select": {}}}
    for u in units:
        props[u["building"]] = {"select": {}}
    for u in price_units:
        props[f"{u['building']}房價"] = {"number": {}}
    db = _get_db(page, CAL_TITLE, props, h)
    _archive(db, h)
    t = _date.fromisoformat(today)
    n = 0
    for i in range(1, 91):
        d = t + timedelta(days=i)
        iso = d.isoformat()
        p = {"日期": {"title": [{"text": {"content": iso}}]},
             "日付": {"date": {"start": iso}},
             "星期": _sel(weekday[d.weekday()])}
        for u in units:
            rec = u["cal"].get(iso)
            if rec is not None:
                p[u["building"]] = _sel("可訂" if rec else "已訂")
        for u in price_units:
            p[f"{u['building']}房價"] = {"number": u["ref_price"]}
        if _post(db, p, h):
            n += 1
    print(f"  90天行事曆: wrote {n} rows")


def write_history_summary(page, today, hist, units, weekday, h):
    uk_to_bldg = {u["uk"]: u["building"] for u in units}
    hprops = {"日期": {"title": {}}, "日付": {"date": {}}, "星期": {"select": {}},
              "判定來源日": {"date": {}}}
    for u in units:
        hprops[u["building"]] = {"select": {}}
    hdb = _get_db(page, HIST_TITLE, hprops, h)
    _archive(hdb, h)
    counts = {u["uk"]: {"tracked": 0, "booked": 0} for u in units}
    n = 0
    for night in sorted(hist):
        e = hist[night]
        d = _date.fromisoformat(night)
        p = {"日期": {"title": [{"text": {"content": night}}]},
             "日付": {"date": {"start": night}},
             "星期": _sel(weekday[d.weekday()]),
             "判定來源日": {"date": {"start": e["src"]}}}
        for uk, avail in e["status"].items():
            b = uk_to_bldg.get(uk)
            if not b:
                continue
            p[b] = _sel("可訂" if avail else "已訂")
            if uk in counts:
                counts[uk]["tracked"] += 1
                if not avail:
                    counts[uk]["booked"] += 1
        if _post(hdb, p, h):
            n += 1
    print(f"  真實入住歷史: wrote {n} nights")

    sprops = {"物件": {"title": {}}, "棟": {"select": {}}, "來源": {"select": {}},
              "紀錄天數": {"number": {}}, "入住天數": {"number": {}},
              "入住率": {"number": {"format": "percent"}},
              "起算日": {"date": {}}, "統計至": {"date": {}}}
    sdb = _get_db(page, SUMMARY_TITLE, sprops, h)
    _archive(sdb, h)
    start = min(hist) if hist else None
    end = max(hist) if hist else None
    m = 0
    for u in units:
        c = counts[u["uk"]]
        p = {"物件": {"title": [{"text": {"content": u["name"]}}]},
             "棟": _sel(u["building"]), "來源": _sel(u["source"]),
             "紀錄天數": {"number": c["tracked"]},
             "入住天數": {"number": c["booked"]},
             "入住率": {"number": (c["booked"] / c["tracked"])
                       if c["tracked"] else None}}
        if start:
            p["起算日"] = {"date": {"start": start}}
        if end:
            p["統計至"] = {"date": {"start": end}}
        if _post(sdb, p, h):
            m += 1
    print(f"  入住彙總: wrote {m} units")


def write_all(today, daily, units, hist, weekday):
    today = today.isoformat() if hasattr(today, "isoformat") else today
    token = os.environ.get("NOTION_TOKEN")
    page = os.environ.get("NOTION_PARENT_PAGE_ID")
    if not token or not page:
        print("  Notion: skipped (NOTION_TOKEN / NOTION_PARENT_PAGE_ID not set)")
        return
    h = _h(token)
    write_daily(page, today, daily, h)
    write_calendar(page, today, units, weekday, h)
    write_history_summary(page, today, hist, units, weekday, h)
    print("  Notion: 4 databases synced")
