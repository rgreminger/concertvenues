"""
Roundhouse scraper.

Listing page: https://www.roundhouse.org.uk/whats-on/
  - Event cards: div.event-card
  - Title: .event-card__title
  - Date: .event-card__date  (format "Sat 21 Feb 26")
  - Link: a.event-card__link[href]

Detail pages contain an Event JSON-LD block with:
  - startDate (ISO 8601, e.g. "2026-02-21T19:00")
  - offers.lowPrice / priceCurrency
  - offers.availability (schema.org/SoldOut | schema.org/InStock)
  - eventStatus (EventCancelled etc.)

We fetch all event cards from the listing, then fetch each detail page
concurrently to extract time, price, and sold-out status from JSON-LD.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_BASE = "https://www.roundhouse.org.uk"
_HEADERS = {"User-Agent": "concertvenues-bot/0.1"}
_MAX_PAGES = 10

# Slugs containing these strings are not concert events
_NON_EVENT_SLUG_PATTERNS = re.compile(
    r"backstage-pass|dj-development|poetry|animation|film|workshop|"
    r"residency|education|talent|programme|drop-in|club-",
    re.IGNORECASE,
)


def _fetch(url: str) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None


def _parse_detail(url: str, today: date) -> Optional[dict]:
    """Fetch an event detail page and extract fields from its JSON-LD block."""
    soup = _fetch(url)
    if not soup:
        return None

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, dict):
            continue
        if data.get("@type") != "Event":
            continue

        start_raw = data.get("startDate", "")
        try:
            start_dt = datetime.fromisoformat(start_raw)
            event_date = start_dt.date()
            event_time: Optional[time] = start_dt.time() if start_dt.hour or start_dt.minute else None
        except (ValueError, TypeError):
            return None

        if event_date < today:
            return None

        offers = data.get("offers", {})
        low = offers.get("lowPrice")
        currency = offers.get("priceCurrency", "GBP")
        price: Optional[str] = None
        if low:
            symbol = "£" if currency == "GBP" else currency
            high = offers.get("highPrice")
            if high and high != low:
                price = f"{symbol}{float(low):.0f}–{symbol}{float(high):.0f}"
            else:
                price = f"From {symbol}{float(low):.0f}"

        availability = offers.get("availability", "")
        sold_out = "SoldOut" in availability

        status = data.get("eventStatus", "")
        if "Cancelled" in status or "Postponed" in status:
            return None  # skip cancelled/postponed

        return {
            "date": event_date,
            "time": event_time,
            "price": price,
            "sold_out": sold_out,
        }

    return None


class RoundhouseScraper(BaseScraper):
    venue_key = "roundhouse"
    venue_name = "Roundhouse"

    def fetch_events(self) -> list[Event]:
        today = date.today()
        base_listing = self.url.rstrip("/")

        # Collect event URLs across paginated listing (WordPress /page/N/ pattern)
        event_urls: list[tuple[str, str]] = []  # (url, title)
        seen: set[str] = set()

        for page in range(1, _MAX_PAGES + 1):
            page_url = base_listing + "/" if page == 1 else f"{base_listing}/page/{page}/"
            soup = _fetch(page_url)
            if not soup:
                break

            cards = soup.select(".event-card")
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                link = card.select_one("a.event-card__link")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or href in seen:
                    continue
                # Skip non-concert events by URL slug
                slug = href.rstrip("/").split("/")[-1]
                if _NON_EVENT_SLUG_PATTERNS.search(slug):
                    continue
                seen.add(href)
                title_el = card.select_one(".event-card__title")
                title = title_el.get_text(strip=True) if title_el else slug.replace("-", " ").title()
                event_urls.append((href, title))
                new_on_page += 1

            if new_on_page == 0:
                break

        if not event_urls:
            return []

        # Fetch each detail page concurrently
        events: list[Event] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {
                pool.submit(_parse_detail, url, today): (url, title)
                for url, title in event_urls
            }
            for future in as_completed(future_map):
                url, title = future_map[future]
                detail = future.result()
                if detail is None:
                    continue
                events.append(Event(
                    venue_key=self.venue_key,
                    title=title,
                    date=detail["date"],
                    time=detail["time"],
                    url=url,
                    price=detail["price"],
                    sold_out=detail["sold_out"],
                ))

        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events
