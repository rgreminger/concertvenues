"""
Shared Ticketmaster Discovery API helper.

Venue IDs:
  - Royal Albert Hall:       KovZ9177Arf
  - Roundhouse:              KovZpZAn6k6A
  - Islington Assembly Hall: KovZ9177akf
  - Alexandra Palace:        KovZpZAn61lA
  - KOKO:                    KovZ91777W7
  - The Garage:              KovZ9177Akf

API endpoint:
  https://app.ticketmaster.com/discovery/v2/events.json
    ?venueId=<ID>&size=200&page=<N>&apikey=<key>

Fields used:
  - name                      → event title
  - url                       → direct Ticketmaster ticket URL
  - dates.start.localDate     → event date (YYYY-MM-DD)
  - dates.start.localTime     → event time (HH:MM:SS)
  - dates.start.timeTBA       → true if time not yet set
  - dates.start.noSpecificTime→ true if event has no specific time
  - dates.status.code         → "onsale" / "offsale" / "cancelled" / "postponed"
  - page.totalPages           → pagination
"""

import os
from datetime import date, datetime, time
from typing import Optional

import requests

_API = "https://app.ticketmaster.com/discovery/v2/events.json"


def get_api_key(venue_cfg: dict) -> str:
    """Return the Ticketmaster API key from venue config or environment."""
    key = venue_cfg.get("ticketmaster_api_key") or os.environ.get("TICKETMASTER_API_KEY", "")
    if not key:
        raise RuntimeError("TICKETMASTER_API_KEY not set in secrets or environment")
    return key


def fetch_tm_events(venue_id: str, venue_key: str, fallback_url: str, api_key: str) -> list:
    """
    Fetch all upcoming events for a Ticketmaster venue ID.

    Returns a list of Event-compatible dicts with keys:
      venue_key, title, date, time, url, sold_out
    """
    from concertvenues.models import Event

    today = date.today()
    events: list[Event] = []
    page = 0

    while True:
        r = requests.get(
            _API,
            params={"venueId": venue_id, "size": 200, "page": page, "apikey": api_key},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        page_data = data.get("page", {})
        docs = data.get("_embedded", {}).get("events", [])

        for doc in docs:
            status_code = doc.get("dates", {}).get("status", {}).get("code", "")
            if status_code in ("cancelled", "postponed"):
                continue

            start = doc.get("dates", {}).get("start", {})
            raw_date = start.get("localDate", "")
            try:
                event_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
            if event_date < today:
                continue

            title = doc.get("name", "").strip()
            if not title:
                continue

            event_time: Optional[time] = None
            if not start.get("timeTBA") and not start.get("noSpecificTime"):
                raw_time = start.get("localTime", "")
                try:
                    event_time = time.fromisoformat(raw_time)
                except (ValueError, TypeError):
                    pass

            event_url = doc.get("url", "") or fallback_url
            sold_out = status_code == "offsale"

            events.append(Event(
                venue_key=venue_key,
                title=title,
                date=event_date,
                time=event_time,
                url=event_url,
                sold_out=sold_out,
            ))

        total_pages = page_data.get("totalPages", 1)
        if page + 1 >= total_pages:
            break
        page += 1

    events.sort(key=lambda e: (e.date, e.time or time.min))
    return events
