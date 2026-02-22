"""
The O2 scraper.

Listing page: https://www.theo2.co.uk/events
  - Event cards link to detail pages at /events/detail/<slug>
  - Title: h3 > a inside each card
  - "Load More Events" button (button.loadMoreEvents) must be clicked
    repeatedly until it disappears to get the full event list.

Detail pages contain a MusicEvent JSON-LD block with:
  - startDate (ISO 8601, e.g. "2026-03-21T18:30:00+00:00")
  - offers.availability ("Available" | "SoldOut" | etc.)
  - eventStatus (EventCancelled etc.)

We use Playwright to load the listing (clicking Load More until exhausted),
then fetch each detail page concurrently via requests for JSON-LD data.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_BASE = "https://www.theo2.co.uk"
_HEADERS = {"User-Agent": "concertvenues-bot/0.1"}


def _fetch(url: str) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None


def _parse_detail(url: str, today: date) -> Optional[dict]:
    """Fetch a detail page and extract fields from its MusicEvent JSON-LD block."""
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
        if data.get("@type") not in ("MusicEvent", "Event"):
            continue

        start_raw = data.get("startDate", "")
        try:
            start_dt = datetime.fromisoformat(start_raw)
            event_date = start_dt.date()
            event_time: Optional[time] = start_dt.time() if (start_dt.hour or start_dt.minute) else None
        except (ValueError, TypeError):
            continue

        if event_date < today:
            return None

        status = data.get("eventStatus", "")
        if "Cancelled" in status or "Postponed" in status:
            return None

        offers = data.get("offers", {})
        availability = offers.get("availability", "")
        sold_out = "SoldOut" in availability or "soldout" in availability.lower()

        return {
            "date": event_date,
            "time": event_time,
            "sold_out": sold_out,
        }

    return None


class TheO2Scraper(BaseScraper):
    venue_key = "theo2"
    venue_name = "The O2"

    def fetch_events(self) -> list[Event]:
        from playwright.sync_api import sync_playwright

        today = date.today()

        # Use Playwright to load listing and click "Load More" until exhausted
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(self.url, wait_until="networkidle", timeout=60_000)
                page.wait_for_timeout(2000)

                # Dismiss OneTrust cookie consent banner if present
                for selector in (
                    "#onetrust-accept-btn-handler",
                    "button#accept-recommended-btn-handler",
                    ".onetrust-accept-btn-handler",
                ):
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1000)
                        break

                while True:
                    btn = page.query_selector("button.loadMoreEvents")
                    if not btn or not btn.is_visible():
                        break
                    btn.click()
                    page.wait_for_timeout(1500)
                html = page.content()
            finally:
                browser.close()

        soup = BeautifulSoup(html, "lxml")

        # Collect all unique event detail URLs
        seen: set[str] = set()
        event_links: list[tuple[str, str]] = []  # (url, title)

        for a in soup.select("a[href*='/events/detail/']"):
            href = a.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = _BASE + href
            if href in seen:
                continue
            seen.add(href)

            # Title: prefer h3 inside the same card, else the link text
            heading = a.find("h3") or a.find_parent("div", recursive=False)
            if heading and heading.name == "h3":
                title = heading.get_text(strip=True)
            else:
                # Look for h3 near this link
                card = a.find_parent(lambda tag: tag.find("h3"))
                if card:
                    h3 = card.find("h3")
                    title = h3.get_text(strip=True) if h3 else ""
                else:
                    title = a.get_text(strip=True)

            if not title:
                slug = href.rstrip("/").split("/")[-1]
                title = slug.replace("-", " ").title()

            event_links.append((href, title))

        if not event_links:
            return []

        # Fetch detail pages concurrently
        events: list[Event] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {
                pool.submit(_parse_detail, url, today): (url, title)
                for url, title in event_links
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
                    price=None,
                    sold_out=detail["sold_out"],
                ))

        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events
