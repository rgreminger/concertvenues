"""
O2 Academy Brixton & O2 Forum Kentish Town scrapers.

Both venues are on the Academy Music Group platform which exposes a JSON API:
  https://www.academymusicgroup.com/api/search/events?VenueIds=<ID>&PageSize=200

Venue IDs:
  - O2 Academy Brixton:      3919
  - O2 Forum Kentish Town:   5597

API document fields used:
  - name                   → event title
  - encodedName            → used to build the event URL slug
  - eventDate              → date (ISO 8601, midnight UTC)
  - doorTime               → "HH:MM" string (door open time)
  - allTicketStatus        → 1 = on sale, 3 = sold out
  - lineup[].isPrimary     → identifies the headline artist
  - lineup[].encodedName   → artist slug used in event URL
  - lineup[].id            → artist ID used in event URL

Event URL pattern:
  https://www.academymusicgroup.com/<venue-slug>/events/<lineup.encodedName>-tickets-ae<lineup.id>/
"""

import re
from datetime import date, datetime, time
from typing import Optional

import requests

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_BASE = "https://www.academymusicgroup.com"
_API = "https://www.academymusicgroup.com/api/search/events"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

_VENUE_IDS = {
    "o2academybrixton": 3919,
    "o2forumkentishtown": 5597,
}
_VENUE_SLUGS = {
    "o2academybrixton": "o2academybrixton",
    "o2forumkentishtown": "o2forumkentishtown",
}


def _scrape_amg_venue(venue_key: str) -> list[Event]:
    venue_id = _VENUE_IDS[venue_key]
    venue_slug = _VENUE_SLUGS[venue_key]
    today = date.today()

    r = requests.get(
        _API,
        params={"VenueIds": venue_id, "PageSize": 200},
        headers=_HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    docs = r.json().get("documents", [])

    events: list[Event] = []
    seen: set[tuple[str, date]] = set()

    for doc in docs:
        # Date
        raw_date = doc.get("eventDate", "")
        try:
            event_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        if event_date < today:
            continue

        # Title
        title = doc.get("name", "").strip()
        if not title:
            continue

        # Time (door time)
        door = doc.get("doorTime", "") or ""
        event_time: Optional[time] = None
        if re.match(r"^\d{1,2}:\d{2}$", door):
            try:
                event_time = time.fromisoformat(door)
            except ValueError:
                pass

        # URL — use primary lineup artist's encodedName + id (not event's own id)
        lineup = doc.get("lineup") or []
        primary = next((a for a in lineup if a.get("isPrimary")), lineup[0] if lineup else None)
        if primary and primary.get("encodedName") and primary.get("id"):
            encoded = primary["encodedName"]
            artist_id = primary["id"]
            event_url = f"{_BASE}/{venue_slug}/events/{encoded}-tickets-ae{artist_id}/"
        else:
            event_url = f"{_BASE}/{venue_slug}/events/"

        # Sold out: allTicketStatus 3 = sold out
        sold_out = doc.get("allTicketStatus") == 3

        key = (event_url, event_date)
        if key in seen:
            continue
        seen.add(key)

        events.append(Event(
            venue_key=venue_key,
            title=title,
            date=event_date,
            time=event_time,
            url=event_url,
            sold_out=sold_out,
        ))

    events.sort(key=lambda e: (e.date, e.time or time.min))
    return events


class O2AcademyBrixtonScraper(BaseScraper):
    venue_key = "o2academybrixton"
    venue_name = "O2 Academy Brixton"

    def fetch_events(self) -> list[Event]:
        return _scrape_amg_venue(self.venue_key)


class O2ForumKentishTownScraper(BaseScraper):
    venue_key = "o2forumkentishtown"
    venue_name = "O2 Forum Kentish Town"

    def fetch_events(self) -> list[Event]:
        return _scrape_amg_venue(self.venue_key)
