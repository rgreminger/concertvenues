"""
Dingwalls scraper — Camden venue, WordPress/Elementor "gig" post type.

Not sourced from Ticketmaster: the venue is split across four stale TM venue
IDs (KovZ9177J9f, KovZpZAn6vtA, KovZ9177U1V, Z7r9jZa7M9, the last two empty)
carrying 7 events between them, while the venue's own listing has ~36.

The Elementor grid is configured for infinite scroll, but WordPress still
serves classic pagination at /whats-on/page/<n>/, so no JS is needed.
Listing cards expose title, date, URL and image only — time and price live on
the individual gig pages and are left unset here.
"""

from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

# Safety cap so a listing that never stops paginating cannot loop forever
_MAX_PAGES = 20


class DingwallsScraper(BaseScraper):
    venue_key = "dingwalls"
    venue_name = "Dingwalls"

    def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        today = date.today()
        seen: set[str] = set()

        for page in range(1, _MAX_PAGES + 1):
            soup = self._fetch_page(page)
            if soup is None:
                break

            cards = soup.select(".e-loop-item")
            if not cards:
                break  # past the last page

            new_on_page = 0
            for card in cards:
                event = self._parse_card(card, today)
                if event is None or event.url in seen:
                    continue
                seen.add(event.url)
                new_on_page += 1
                events.append(event)

            # A page that repeats the previous one means pagination is ignored
            if new_on_page == 0:
                break

        events.sort(key=lambda e: e.date)
        return events

    def _fetch_page(self, page: int) -> Optional[BeautifulSoup]:
        url = self.url if page == 1 else f"{self.url.rstrip('/')}/page/{page}/"
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "concertvenues-bot/0.1"},
        )
        if page > 1 and response.status_code == 404:
            return None  # ran off the end of the listing
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def _parse_card(self, card, today: date) -> Optional[Event]:
        # --- Title & URL ---
        # Elementor's own element classes are build hashes, so key off the
        # post-title heading link instead.
        title_el = card.select_one("h1 a[href], h2 a[href], h3 a[href]")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        event_url = title_el["href"]
        if not title or not event_url:
            return None

        # --- Date ---
        # Second heading in the card, e.g. "Saturday, 1st August 2026".
        event_date = None
        for heading in card.select(".elementor-heading-title"):
            text = heading.get_text(strip=True)
            if text == title:
                continue
            try:
                event_date = dateparser.parse(text, dayfirst=True).date()
            except (ValueError, TypeError, OverflowError):
                continue
            break

        if event_date is None or event_date < today:
            return None  # unparseable or past event

        # --- Image ---
        image_url = None
        img_el = card.select_one("img[src]")
        if img_el:
            image_url = img_el["src"]

        return Event(
            venue_key=self.venue_key,
            title=title,
            date=event_date,
            url=event_url,
            image_url=image_url,
        )
