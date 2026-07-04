"""Airbnb PdpAvailabilityCalendar fetcher (self-contained, stdlib only).

Public GraphQL persisted query. Returns ~months*30 nights of availability.
NOTE: dense local calls get IP rate-limited (HTTP 400); one-a-day from a
fresh CI runner IP is fine (proven by maruko-tracker in production).
"""
import json
import time
import urllib.parse
import urllib.request

API_KEY = "d306zoyjsyarp7ifhu67rjxn52tv0t20"
HASH = "8f08e03c7bd16fcad3c92a3592c19a8b559a0d0855a77a9a3aac79e2ad4cf4d4"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_airbnb_calendar(listing_id, months=4, retries=3):
    """Return {date_iso: available_bool}. Empty dict if listing has no calendar."""
    variables = {"request": {"count": months, "listingId": str(listing_id),
                             "month": time.gmtime().tm_mon, "year": time.gmtime().tm_year}}
    extensions = {"persistedQuery": {"version": 1, "sha256Hash": HASH}}
    url = ("https://www.airbnb.com/api/v3/PdpAvailabilityCalendar/" + HASH
           + "?operationName=PdpAvailabilityCalendar&locale=en&currency=JPY"
           + "&variables=" + urllib.parse.quote(json.dumps(variables))
           + "&extensions=" + urllib.parse.quote(json.dumps(extensions)))
    headers = {"X-Airbnb-Api-Key": API_KEY, "User-Agent": UA, "Accept": "application/json"}
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            cal = data.get("data", {}).get("merlin", {}).get("pdpAvailabilityCalendar")
            if not cal:
                return {}
            out = {}
            for m in cal.get("calendarMonths", []):
                for d in m.get("days", []):
                    iso = d.get("calendarDate")
                    if iso:
                        out[iso] = bool(d.get("available"))
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise last
