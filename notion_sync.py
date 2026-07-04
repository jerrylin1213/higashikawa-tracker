"""Notion sync for higashikawa-tracker (phase 2).

Writes daily occupancy rows into a Notion database under a parent page.
Requires env NOTION_TOKEN + NOTION_PARENT_PAGE_ID. If either is unset it
silently skips, so phase-1 CI keeps working before Notion is configured.

One-time setup (dedicated integration):
  1. https://www.notion.so/my-integrations -> New integration -> copy ntn_ token
  2. Create a page in your workspace (this will be the parent), open its
     ... menu -> Connections -> add your integration. Copy the page id from
     the URL (the 32-hex chunk).
  3. Repo Settings -> Secrets and variables -> Actions, add:
       NOTION_TOKEN            = ntn_...
       NOTION_PARENT_PAGE_ID   = <32-hex page id>
The database ("每日入住率") is auto-created under the parent on first run.
"""
import os

import requests

NOTION_VER = "2022-06-28"
DAILY_DB_TITLE = "每日入住率"
API = "https://api.notion.com/v1"


def _headers(token):
    return {"Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VER,
            "Content-Type": "application/json"}


def _find_child_db(page_id, title, h):
    cursor = None
    while True:
        url = f"{API}/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=h, timeout=30)
        r.raise_for_status()
        j = r.json()
        for blk in j.get("results", []):
            if blk.get("type") == "child_database" and \
                    blk["child_database"].get("title") == title:
                return blk["id"]
        if not j.get("has_more"):
            return None
        cursor = j.get("next_cursor")


def _create_daily_db(page_id, h):
    props = {
        "名稱": {"title": {}},
        "紀錄日期": {"date": {}},
        "物件": {"rich_text": {}},
        "棟": {"rich_text": {}},
        "來源": {"select": {"options": [
            {"name": "airbnb", "color": "red"},
            {"name": "jalan", "color": "orange"},
            {"name": "niseu", "color": "green"}]}},
        "視窗天數": {"number": {}},
        "7天入住率": {"number": {"format": "percent"}},
        "30天入住率": {"number": {"format": "percent"}},
        "60天入住率": {"number": {"format": "percent"}},
        "90天入住率": {"number": {"format": "percent"}},
    }
    r = requests.post(f"{API}/databases", headers=h, json={
        "parent": {"type": "page_id", "page_id": page_id},
        "title": [{"type": "text", "text": {"content": DAILY_DB_TITLE}}],
        "properties": props,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def _pct(v):
    return None if v is None else round(v / 100.0, 4)


def write_notion(today, rows, snap):
    token = os.environ.get("NOTION_TOKEN")
    parent = os.environ.get("NOTION_PARENT_PAGE_ID")
    if not token or not parent:
        print("  Notion: skipped (NOTION_TOKEN / NOTION_PARENT_PAGE_ID not set)")
        return
    h = _headers(token)
    db = _find_child_db(parent, DAILY_DB_TITLE, h) or _create_daily_db(parent, h)
    n = 0
    for row in rows:
        occ = row["occ"]
        name = f"{today} {row['label']} / {row['building']}"
        props = {
            "名稱": {"title": [{"text": {"content": name}}]},
            "紀錄日期": {"date": {"start": today}},
            "物件": {"rich_text": [{"text": {"content": row["label"]}}]},
            "棟": {"rich_text": [{"text": {"content": row["building"]}}]},
            "來源": {"select": {"name": row["source"]}},
            "視窗天數": {"number": row["nights"]},
            "7天入住率": {"number": _pct(occ.get(7))},
            "30天入住率": {"number": _pct(occ.get(30))},
            "60天入住率": {"number": _pct(occ.get(60))},
            "90天入住率": {"number": _pct(occ.get(90))},
        }
        r = requests.post(f"{API}/pages", headers=h, json={
            "parent": {"database_id": db}, "properties": props}, timeout=30)
        if r.ok:
            n += 1
        else:
            print(f"  Notion write fail [{name}]: {r.status_code} {r.text[:120]}")
    print(f"  Notion: wrote {n}/{len(rows)} rows to 「{DAILY_DB_TITLE}」")
