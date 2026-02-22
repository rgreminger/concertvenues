"""
Roundhouse scraper.

Listing pages: https://www.roundhouse.org.uk/whats-on/?type=event
  Paginated as /whats-on/page/N/?type=event
  - Event cards: .event-card
  - Title:       .event-card__title
  - Date:        .event-card__date  (format "Sat 21 Feb 26" or "Sat 21 Feb 2026")
  - Link:        a.event-card__link[href]

Detail pages are fetched concurrently for time/price/sold-out:
  - .booking-button__time  → "7pm"
  - [class*=price]         → "£31.15"
  - .booking-button text may contain "Sold Out"

If a detail page returns 404 or has no booking button, the event is still
included using only the listing date (time/price/sold-out left as defaults).
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, time
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_HEADERS = {"User-Agent": "concertvenues-bot/0.1"}
_MAX_PAGES = 20
_PRICE_RE = re.compile(r"£\s*(\d+(?:\.\d{1,2})?)")


def _fetch(url: str) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None


def _page_url(base: str, page: int) -> str:
    """Build a paginated URL preserving query params, e.g. /whats-on/page/2/?type=event."""
    parsed = urlparse(base)
    path = parsed.path.rstrip("/")
    if page > 1:
        path = f"{path}/page/{page}"
    return urlunparse(parsed._replace(path=path + "/"))


def _parse_date(raw: str) -> Optional[date]:
    """Parse a date string like 'Sat 21 Feb 26' or 'Sat 21 Feb 2026'."""
    raw = raw.strip()
    if not raw:
        return None
    # Use only the first date if a range is given ("Tue 24–Fri 27 Feb 26")
    raw = re.split(r"[–—-]", raw)[0].strip()
    # Expand 2-digit year suffix
    raw = re.sub(r"\b(\d{2})\s*$", lambda m: str(2000 + int(m.group(1))), raw)
    try:
        parsed = dateparser.parse(raw, dayfirst=True)
        if parsed:
            return parsed.date()
    except Exception:
        pass
    return None


def _parse_time(raw: str) -> Optional[time]:
    """Parse a time string like '7pm' or '19:00'."""
    raw = raw.strip().lower()
    if not raw:
        return None
    try:
        parsed = dateparser.parse(raw)
        if parsed:
            return parsed.time()
    except Exception:
        pass
    return None


def _parse_detail(url: str) -> dict:
    """Fetch a detail page for time/price/sold-out. Returns partial dict (may be empty)."""
    result: dict = {}
    soup = _fetch(url)
    if not soup:
        return result

    btn = soup.select_one(".booking-button")
    if not btn:
        return result

    time_el = soup.select_one(".booking-button__time")
    if time_el:
        result["time"] = _parse_time(time_el.get_text(strip=True))

    price_el = soup.select_one("[class*='price']")
    if price_el:
        m = _PRICE_RE.search(price_el.get_text())
        if m:
            result["price"] = f"£{float(m.group(1)):.0f}"

    btn_text = btn.get_text(separator=" ", strip=True).lower()
    result["sold_out"] = "sold out" in btn_text

    return result


class RoundhouseScraper(BaseScraper):
    venue_key = "roundhouse"
    venue_name = "Roundhouse"

    def fetch_events(self) -> list[Event]:
        today = date.today()

        event_items: list[tuple[str, str, date]] = []
        seen: set[str] = set()

        for page in range(1, _MAX_PAGES + 1):
            soup = _fetch(_page_url(self.url, page))
            if not soup:
                break

            cards = soup.select(".event-card")
            if not cards:
                break

            any_new = False
            for card in cards:
                link = card.select_one("a.event-card__link")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or href in seen:
                    continue
                seen.add(href)
                any_new = True

                date_el = card.select_one(".event-card__date")
                event_date = _parse_date(date_el.get_text(strip=True) if date_el else "")
                if not event_date or event_date < today:
                    continue

                title_el = card.select_one(".event-card__title")
                slug = href.rstrip("/").split("/")[-1]
                title = title_el.get_text(strip=True) if title_el else slug.replace("-", " ").title()
                event_items.append((href, title, event_date))

            if not any_new:
                break

        if not event_items:
            return []

        events: list[Event] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {
                pool.submit(_parse_detail, url): (url, title, event_date)
                for url, title, event_date in event_items
            }
            for future in as_completed(future_map):
                url, title, event_date = future_map[future]
                detail = future.result()
                events.append(Event(
                    venue_key=self.venue_key,
                    title=title,
                    date=event_date,
                    time=detail.get("time"),
                    url=url,
                    price=detail.get("price"),
                    sold_out=detail.get("sold_out", False),
                ))

        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events
