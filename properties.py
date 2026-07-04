"""The 5 confirmed Higashikawa competitor properties (phase 1).

source types:
  airbnb -> fetch_airbnb_calendar(id)     per-listing availability, ~122d
  niseu  -> fetch_niseu_calendar()        official cal, per-day x 3 buildings
  jalan  -> fetch_jalan_calendar(id)      facility-level availability, ~4 months
"""
PROPERTIES = [
    {"label": "The Peak Villa Suite", "source": "airbnb", "id": "37946397",
     "buildings": ["Peak Villa Suite"], "booking_slug": "the-peak-villa-suite-hokkaido"},
    {"label": "クレインハウス Crane", "source": "airbnb", "id": "36903070",
     "buildings": ["Crane House"], "booking_slug": None},
    {"label": "Villa ニセウコロコロ", "source": "niseu", "id": None,
     "buildings": ["ペロ", "チカプ", "トゥンニ"], "booking_slug": None},
    {"label": "東川ペリカン Pelican", "source": "jalan", "id": "398511",
     "buildings": ["Pelican"], "booking_slug": "dong-chuan-perikan"},
    {"label": "andon 行灯", "source": "jalan", "id": "373749",
     "buildings": ["andon"], "booking_slug": None},
]
