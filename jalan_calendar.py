"""Jalan (じゃらん) vacancy calendar (Playwright), facility-level availability.

Renders jalan.net/yad<ID>/ month calendar and parses cells
("×"/"満"=full, "N部屋"/"○"/"△"=available), paging forward via
stayYear/stayMonth params. Window ~4 months (~116 days).
Reusable for any Jalan yad id (perican 398511, andon 373749).
"""
import re
from datetime import date

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _cal_rows(pg):
    return pg.evaluate(
        r"""()=>{const t=[...document.querySelectorAll('table')]"""
        r""".find(t=>/[○◯△▲×✕]/.test(t.innerText));"""
        r"""if(!t)return null;return [...t.querySelectorAll('tr')]"""
        r""".map(r=>[...r.querySelectorAll('th,td')]"""
        r""".map(c=>c.textContent.trim()).join('|'));}""")


def parse_month(rows, year, month):
    out = {}
    for row in rows[1:]:
        for cell in row.split('|'):
            m = re.match(r'\s*(\d{1,2})\s+(.+)', cell)
            if not m:
                continue
            day = int(m.group(1))
            st = m.group(2)
            if '×' in st or '満' in st:
                avail = False
            elif '○' in st or '部屋' in st or '△' in st or '空' in st:
                avail = True
            else:
                continue
            out[f"{year}-{month:02d}-{day:02d}"] = avail
    return out


def fetch_jalan_calendar(yad_id, months=4):
    """Return {date_iso: available_bool} facility-level."""
    from playwright.sync_api import sync_playwright
    out = {}
    today = date.today()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_context(user_agent=UA, locale="ja-JP").new_page()
        for k in range(months):
            y, mo = today.year, today.month + k
            while mo > 12:
                y += 1
                mo -= 12
            url = f"https://www.jalan.net/yad{yad_id}/"
            if k > 0:
                url += (f"?stayYear={y}&stayMonth={mo}"
                        f"&stayCount=1&roomCount=1&adultNum=2")
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            for _ in range(8):
                pg.wait_for_timeout(1200)
                if pg.evaluate("()=>/[○△×満]|部屋/.test(document.body.innerText)"):
                    break
            rows = _cal_rows(pg)
            if rows:
                out.update(parse_month(rows, y, mo))
        b.close()
    return out
