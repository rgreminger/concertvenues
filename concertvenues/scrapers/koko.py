"""
KOKO scraper — uses Playwright (headless Chromium).

Listing page: https://www.koko.co.uk/whats-on
  - Event cards: [class*="Event_component"]  (CSS module, e.g. Event_component__Ip5vk)
  - Title:       img[alt] inside the card
  - Date:        [class*="Event_date"] — contains a span with date text like "sat 21 feb"
  - URL:         a[href*="/events/"] (relative path, prepend https://www.koko.co.uk)
  - Sold-out:    presence of [class*="Event_soldout"] element inside card
  - No price on listing page.

Date format is "sat 21 feb" (no year) — year is inferred from context (next occurrence
of that month/day on or after today).
"""

from datetime import date, time
from typing import Optional

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_BASE = "https://www.koko.co.uk"


def _parse_koko_date(raw: str, today: date) -> Optional[date]:
    """Parse 'sat 21 feb' style strings — year inferred as current or next year."""
    raw = raw.strip().lower()
    # Strip leading weekday token if present (e.g. "sat 21 feb" → "21 feb")
    parts = raw.split()
    # Remove any alphabetic-only prefix token (weekday abbreviation)
    if parts and parts[0].isalpha() and len(parts[0]) <= 3:
        parts = parts[1:]
    date_str = " ".join(parts)
    if not date_str:
        return None
    # Try current year first, then next year
    for year in (today.year, today.year + 1):
        try:
            parsed = dateparser.parse(f"{date_str} {year}", dayfirst=True)
            if parsed is None:
                continue
            d = parsed.date()
            if d >= today:
                return d
        except Exception:
            continue
    return None


class KokoScraper(BaseScraper):
    venue_key = "koko"
    venue_name = "KOKO"

    def fetch_events(self) -> list[Event]:
        from playwright.sync_api import sync_playwright

        today = date.today()
        events: list[Event] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(self.url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(3000)
                html = page.content()
            finally:
                browser.close()

        soup = BeautifulSoup(html, "lxml")

        seen_urls: set[str] = set()
        for card in soup.select('[class*="Event_component"]'):
            # Title from image alt text
            img = card.select_one("img[alt]")
            title = img.get("alt", "").strip() if img else ""
            if not title:
                continue

            # Date from [class*="Event_date"] — first span contains date text
            date_el = card.select_one('[class*="Event_date"]')
            if not date_el:
                continue
            # The element may contain multiple spans; grab the first text span
            span = date_el.find("span")
            date_raw = span.get_text(strip=True) if span else date_el.get_text(strip=True)
            event_date = _parse_koko_date(date_raw, today)
            if event_date is None or event_date < today:
                continue

            # URL
            link_el = card.select_one('a[href*="/events/"]')
            if not link_el:
                continue
            href = link_el.get("href", "")
            event_url = href if href.startswith("http") else _BASE + href
            if event_url in seen_urls:
                continue
            seen_urls.add(event_url)

            # Sold-out flag
            sold_out = bool(card.select_one('[class*="Event_soldout"]'))

            events.append(Event(
                venue_key=self.venue_key,
                title=title,
                date=event_date,
                url=event_url,
                sold_out=sold_out,
            ))

        events.sort(key=lambda e: e.date)
        return events
