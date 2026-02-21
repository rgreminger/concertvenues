"""
Islington Assembly Hall scraper.

Listing page: https://islingtonassemblyhall.co.uk/events/
  - Event cards: li.event__item
  - Title: a.event__item__title
  - Date spans: .event__item__date__day, .event__item__date__numeric, .event__item__date__month
    → assembled as e.g. "Sat 21 Feb"
  - Link: a.event__item__title[href]  (relative, e.g. /events/jeff-tweedy-...)
  - Pagination: ?page=N

Detail page (fetched concurrently):
  - .event__details__list contains labelled spans:
      "Date"  → "21/02/2026"
      "Time"  → "19:00"
      "Total price, inc booking fee" → "£52.02"
  - Ticket CTA text: .event__details__list__item--tickets .cta__foreground
      "Get tickets" → available
      "Waiting List" → sold out / waitlist (treat as sold_out=True)
      "Free"         → price="Free", sold_out=False
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_BASE = "https://islingtonassemblyhall.co.uk"
_HEADERS = {"User-Agent": "concertvenues-bot/0.1"}
_MAX_PAGES = 10


def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None


def _parse_listing_page(url: str) -> list[tuple[str, str]]:
    """Return list of (absolute_url, title) from one listing page."""
    soup = _get(url)
    if not soup:
        return []
    results = []
    for item in soup.select("li.event__item"):
        title_el = item.select_one("a.event__item__title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        if not href:
            continue
        abs_url = href if href.startswith("http") else _BASE + href
        results.append((abs_url, title))
    return results


def _parse_detail(url: str, title: str, today: date) -> Optional[Event]:
    """Fetch an event detail page and extract date, time, price, sold-out."""
    soup = _get(url)
    if not soup:
        return None

    details: dict[str, str] = {}
    dl = soup.select_one(".event__details__list")
    if dl:
        items = dl.select(".event__details__list__item")
        for item in items:
            lines = item.select(".event__details__list__line")
            if len(lines) >= 2:
                label = lines[0].get_text(strip=True).lower()
                value = lines[1].get_text(strip=True)
                details[label] = value

    # Date
    date_str = details.get("date", "")
    try:
        event_date = datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        return None

    if event_date < today:
        return None

    # Time
    time_str = details.get("time", "")
    event_time: Optional[time] = None
    try:
        event_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        pass

    # Price
    price_raw = details.get("total price, inc booking fee", "")
    price: Optional[str] = None
    if price_raw:
        m = re.search(r"[£$€][\d.,]+", price_raw)
        if m:
            price = m.group()

    # Sold-out / availability
    sold_out = False
    ticket_el = soup.select_one(".event__details__list__item--tickets .cta__foreground")
    if ticket_el:
        cta_text = ticket_el.get_text(strip=True).lower()
        if "waiting" in cta_text or "sold" in cta_text:
            sold_out = True
        if "free" in cta_text:
            price = "Free"

    return Event(
        venue_key="islingtonassemblyhall",
        title=title,
        date=event_date,
        time=event_time,
        url=url,
        price=price,
        sold_out=sold_out,
    )


class IslingtonAssemblyHallScraper(BaseScraper):
    venue_key = "islingtonassemblyhall"
    venue_name = "Islington Assembly Hall"

    def fetch_events(self) -> list[Event]:
        today = date.today()

        # Collect all event URLs across paginated listing
        all_event_links: list[tuple[str, str]] = []
        seen_urls: set[str] = set()

        for page in range(1, _MAX_PAGES + 1):
            page_url = self.url if page == 1 else f"{self.url}?page={page}"
            links = _parse_listing_page(page_url)
            if not links:
                break
            new_links = [(u, t) for u, t in links if u not in seen_urls]
            if not new_links:
                break
            for u, t in new_links:
                seen_urls.add(u)
            all_event_links.extend(new_links)

        if not all_event_links:
            return []

        # Fetch detail pages concurrently
        events: list[Event] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {
                pool.submit(_parse_detail, url, title, today): (url, title)
                for url, title in all_event_links
            }
            for future in as_completed(future_map):
                event = future.result()
                if event is not None:
                    events.append(event)

        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events
