"""
Royal Albert Hall scraper.

Uses the Ticketmaster Discovery API (RAH venue ID: KovZ9177Arf).
Requires TICKETMASTER_API_KEY in the 'secrets' file or environment.

API endpoint:
  https://app.ticketmaster.com/discovery/v2/events.json
    ?venueId=KovZ9177Arf&size=200&apikey=<key>

Fields used:
  - name                        → event title
  - url                         → direct Ticketmaster ticket URL
  - dates.start.localDate       → event date (YYYY-MM-DD)
  - dates.start.localTime       → event time (HH:MM:SS), omitted if timeTBA
  - dates.start.timeTBA         → true if time is not yet set
  - dates.status.code           → "offsale" / "cancelled" / "onsale" etc.
"""

import os
from datetime import date, datetime, time
from typing import Optional

import requests

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_API = "https://app.ticketmaster.com/discovery/v2/events.json"
_VENUE_ID = "KovZ9177Arf"


class RoyalAlbertHallScraper(BaseScraper):
    venue_key = "royalalberthall"
    venue_name = "Royal Albert Hall"

    def fetch_events(self) -> list[Event]:
        api_key = self.venue_cfg.get("ticketmaster_api_key") or os.environ.get("TICKETMASTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("TICKETMASTER_API_KEY not set in secrets or environment")

        today = date.today()
        events: list[Event] = []
        page = 0

        while True:
            r = requests.get(
                _API,
                params={"venueId": _VENUE_ID, "size": 200, "page": page, "apikey": api_key},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()

            page_data = data.get("page", {})
            docs = data.get("_embedded", {}).get("events", [])

            for doc in docs:
                # Skip cancelled / postponed
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

                event_url = doc.get("url", "") or self.url
                sold_out = status_code == "offsale"

                events.append(Event(
                    venue_key=self.venue_key,
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
