"""Booking.com nightly reference price via Playwright (best-effort).

Only Peak and perican have Booking.com listings; the other 3 have no usable
OTA price source (Crane=Yahoo only, niseu=official site, andon=Jalan/Trip).
Booking sits behind AWS WAF, so a real browser is required; we poll until a
price or sold-out marker appears.
"""
import re
from datetime import timedelta

YEN = re.compile(r"[¥￥]\s?([0-9][0-9,]{2,})")
SOLD = re.compile(r"not available|no rooms|sold out|fully booked|no availability",
                  re.IGNORECASE)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# label -> Booking.com slug (only these two are on Booking)
BOOKING_SLUGS = {
    "The Peak Villa Suite": "the-peak-villa-suite-hokkaido",
    "東川ペリカン Pelican": "dong-chuan-perikan",
}


def _url(slug, checkin, checkout):
    return (f"https://www.booking.com/hotel/jp/{slug}.html"
            f"?checkin={checkin.isoformat()}&checkout={checkout.isoformat()}"
            f"&group_adults=2&selected_currency=JPY&lang=en-us")


def fetch_booking_prices(checkin_by_label, nights=2):
    """checkin_by_label: {label: date|None}. Returns
    {label: {"price": int|None, "checkin": iso|None, "sold_out": bool,
             "error": str|None}} for labels that have a Booking slug."""
    results = {lbl: {"price": None, "checkin": None, "sold_out": False,
                     "error": None} for lbl in BOOKING_SLUGS}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        for lbl in results:
            results[lbl]["error"] = f"playwright unavailable: {e}"
        return results

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, locale="en-US")
        pg = ctx.new_page()
        for lbl, slug in BOOKING_SLUGS.items():
            checkin = checkin_by_label.get(lbl)
            if checkin is None:
                results[lbl]["error"] = "no available night to quote"
                continue
            checkout = checkin + timedelta(days=nights)
            try:
                pg.goto(_url(slug, checkin, checkout),
                        wait_until="domcontentloaded", timeout=30000)
                txt = ""
                for _ in range(15):
                    pg.wait_for_timeout(1000)
                    txt = pg.evaluate(
                        "() => document.body ? document.body.innerText : ''")
                    if YEN.search(txt) or SOLD.search(txt):
                        break
                yen = [int(m.replace(",", "")) for m in YEN.findall(txt)]
                results[lbl]["checkin"] = checkin.isoformat()
                if SOLD.search(txt) and not yen:
                    results[lbl]["sold_out"] = True
                elif yen:
                    results[lbl]["price"] = min(yen)
                else:
                    results[lbl]["error"] = "no price markers (WAF/empty)"
            except Exception as e:  # noqa: BLE001
                results[lbl]["error"] = f"{type(e).__name__}: {e}"
        b.close()
    return results
