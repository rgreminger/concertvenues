import re
from datetime import date, time

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_SOLD_OUT_RE = re.compile(r"sold.?out", re.IGNORECASE)
# Matches "SOLD OUT!" / "– SOLD OUT!" appended to event names
_TITLE_SUFFIX_RE = re.compile(r"\s*[–-]?\s*sold.?out!?\s*$", re.IGNORECASE)


class ElectricBallroomScraper(BaseScraper):
    venue_key = "electricballroom"
    venue_name = "Electric Ballroom"

    def fetch_events(self) -> list[Event]:
        response = requests.get(
            self.url,
            timeout=15,
            headers={"User-Agent": "concertvenues-bot/0.1"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        events: list[Event] = []
        today = date.today()

        for card in soup.select(".grid-block"):
            # --- URL ---
            link_el = card.select_one("a.grid-link")
            if not link_el:
                continue
            event_url = link_el["href"]

            # --- Title ---
            name_el = card.select_one(".event-name a")
            if not name_el:
                continue
            raw_title = name_el.get_text(strip=True)

            # Detect sold-out from title text before stripping the suffix
            sold_out = bool(_SOLD_OUT_RE.search(raw_title))
            # Also treat missing buy-button as sold out (Crowbar-style)
            if not sold_out and not card.select_one(".buy-share-event .button"):
                sold_out = True

            title = _TITLE_SUFFIX_RE.sub("", raw_title).strip()

            # --- Date ---
            date_el = card.select_one(".event-date")
            if not date_el:
                continue
            date_str = date_el.get_text(strip=True)
            try:
                event_date = _parse_date(date_str, today)
            except Exception:
                continue  # skip cards with unparseable dates

            if event_date < today:
                continue  # skip past events

            # --- Time ---
            time_el = card.select_one(".event-time")
            event_time = None
            if time_el:
                try:
                    event_time = dateparser.parse(time_el.get_text(strip=True)).time()
                except Exception:
                    pass

            # --- Price ---
            price_el = card.select_one(".event-price")
            price = price_el.get_text(strip=True) if price_el else None

            # --- Image ---
            image_el = card.select_one(".grid-image")
            image_url = None
            if image_el and image_el.get("style"):
                m = re.search(r"url\(['\"]?(.+?)['\"]?\)", image_el["style"])
                if m:
                    image_url = m.group(1)

            events.append(Event(
                venue_key=self.venue_key,
                title=title,
                date=event_date,
                time=event_time,
                url=event_url,
                price=price,
                sold_out=sold_out,
                image_url=image_url,
            ))

        return events


def _parse_date(date_str: str, reference: date) -> date:
    """
    Parse a human-readable date like "Saturday 21st February" into a date object.
    Infers the year: uses the current year, but rolls to next year if the
    parsed date is more than 60 days in the past (handles end-of-year edge cases).
    """
    parsed = dateparser.parse(date_str, dayfirst=True)
    if parsed is None:
        raise ValueError(f"Cannot parse date: {date_str!r}")
    candidate = parsed.replace(year=reference.year).date()
    if (reference - candidate).days > 60:
        candidate = candidate.replace(year=reference.year + 1)
    return candidate
