"""
Alexandra Palace scraper — uses Playwright (headless Chromium).

Listing page: https://www.alexandrapalace.com/whats-on/
  - Event cards: div.event_card_wrapper   (excludes .past-event cards)
  - Title: a.event_target > h3
  - Date: p.dates  (format "21 Feb 2026")
  - URL:  a.event_target[href]
  - Sold-out: 'waiting_list' or 'sold_out' in card classes
  - No time or price on the listing page; not fetching detail pages.
"""

import re
from datetime import date, time
from typing import Optional

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper


def _parse_date(date_str: str, today: date) -> Optional[date]:
    """Parse '21 Feb 2026' style date strings."""
    try:
        parsed = dateparser.parse(date_str, dayfirst=True)
        if parsed is None:
            return None
        return parsed.date()
    except Exception:
        return None


class AlexandraPalaceScraper(BaseScraper):
    venue_key = "alexandrapalace"
    venue_name = "Alexandra Palace"

    def fetch_events(self) -> list[Event]:
        from playwright.sync_api import sync_playwright

        today = date.today()
        events: list[Event] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(self.url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2000)
                html = page.content()
            finally:
                browser.close()

        soup = BeautifulSoup(html, "lxml")

        for card in soup.select(".event_card_wrapper"):
            classes = card.get("class", [])
            if "past-event" in classes:
                continue

            link_el = card.select_one("a.event_target")
            if not link_el:
                continue
            url = link_el.get("href", "")
            if not url:
                continue

            title_el = link_el.select_one("h3")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            date_el = card.select_one("p.dates")
            if not date_el:
                continue
            date_str = date_el.get_text(strip=True)
            event_date = _parse_date(date_str, today)
            if event_date is None or event_date < today:
                continue

            sold_out = "waiting_list" in classes or "sold_out" in classes

            events.append(Event(
                venue_key=self.venue_key,
                title=title,
                date=event_date,
                url=url,
                sold_out=sold_out,
            ))

        events.sort(key=lambda e: e.date)
        return events
