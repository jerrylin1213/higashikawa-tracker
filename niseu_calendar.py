"""Villa ニセウコロコロ official calendar (Playwright).

Renders nisew-corocoro.com/calendar/ (JS grid, no <table>) and parses the
regular innerText pattern "DAY  ○/× ○/× ○/×" into per-day per-building status.
3 buildings: ペロ / チカプ / トゥンニ. Window ~3 months (~87 days).
"""
import re
from datetime import date

BUILDINGS = ["ペロ", "チカプ", "トゥンニ"]
URL = "https://nisew-corocoro.com/calendar/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def parse_niseu(text, year):
    out = {}
    cur_month = date.today().month
    parts = re.split(r'(\d{1,2})月', text)
    for i in range(1, len(parts) - 1, 2):
        mon = int(parts[i])
        block = parts[i + 1]
        yr = year if mon >= cur_month else year + 1
        for m in re.finditer(r'(\d{1,2})\s*([○×])\s*([○×])\s*([○×])', block):
            day = int(m.group(1))
            syms = [m.group(2), m.group(3), m.group(4)]
            out[f"{yr}-{mon:02d}-{day:02d}"] = {
                b: (s == '○') for b, s in zip(BUILDINGS, syms)}
    return out


def fetch_niseu_calendar():
    """Return {date_iso: {building: available_bool}}."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_context(user_agent=UA, locale="ja-JP").new_page()
        pg.goto(URL, wait_until="networkidle", timeout=45000)
        pg.wait_for_timeout(3000)
        text = pg.evaluate("()=>document.body.innerText")
        b.close()
    return parse_niseu(text, date.today().year)
