"""
The Garage London scraper — uses Playwright for the listing page, then
requests for individual gig detail pages (SSL bypass via verify=False).

Listing page: https://www.thegarage.london/live/
  - Event cards: .card  with  a[href*="/gigs/"]  inside
  - Title:       .card__heading
  - Sold-out:    .card__notification text == "Gig Sold Out"
  - No date/time/price on listing page — fetched from detail pages.

Detail pages (e.g. https://www.thegarage.london/gigs/<slug>/):
  - Date:  strong/p text matching "WED 25TH FEBRUARY 2026" pattern
  - Time:  strong/p text matching "7:00 PM" pattern
  - Price: strong/p text matching "£NN" pattern
  - The site has an SSL certificate error; requests uses verify=False.
"""

import re
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_BASE = "https://www.thegarage.london"
_HEADERS = {"User-Agent": "concertvenues-bot/0.1"}

# Pattern to find dates like "WED 25TH FEBRUARY 2026"
_DATE_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}\b",
    re.IGNORECASE,
)
# Pattern to find times like "7:00 PM" or "19:00"
_TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*(?:AM|PM)?)\b", re.IGNORECASE)
# Pattern to find prices like "£20" or "£12.50"
_PRICE_RE = re.compile(r"£\s*(\d+(?:\.\d{1,2})?)")


def _fetch_detail(url: str, today: date) -> Optional[dict]:
    """Fetch a gig detail page and extract date, time, and price."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = requests.get(url, headers=_HEADERS, timeout=15, verify=False)
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    # Gather all text nodes from the page body to search for date/time/price
    body_text = soup.get_text(" ", strip=True)

    # Date
    date_match = _DATE_RE.search(body_text)
    if not date_match:
        return None
    try:
        event_date = dateparser.parse(date_match.group(), dayfirst=True).date()
    except Exception:
        return None
    if event_date < today:
        return None

    # Time
    event_time: Optional[time] = None
    time_match = _TIME_RE.search(body_text)
    if time_match:
        try:
            event_time = dateparser.parse(time_match.group().strip()).time()
        except Exception:
            pass

    # Price
    price: Optional[str] = None
    price_match = _PRICE_RE.search(body_text)
    if price_match:
        price = f"£{float(price_match.group(1)):.0f}"

    return {
        "date": event_date,
        "time": event_time,
        "price": price,
    }


class TheGarageScraper(BaseScraper):
    venue_key = "thegarage"
    venue_name = "The Garage"

    def fetch_events(self) -> list[Event]:
        from playwright.sync_api import sync_playwright

        today = date.today()

        # Use Playwright for the listing page (SSL issues with requests)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(ignore_https_errors=True)
            try:
                page.goto(self.url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2000)
                html = page.content()
            finally:
                browser.close()

        soup = BeautifulSoup(html, "lxml")

        # Collect unique gig URLs and metadata from listing cards
        gig_urls: list[tuple[str, str, bool]] = []  # (url, title, sold_out)
        seen: set[str] = set()

        for card in soup.select(".card"):
            link_el = card.select_one('a[href*="/gigs/"]')
            if not link_el:
                continue
            href = link_el.get("href", "")
            if not href:
                continue
            gig_url = href if href.startswith("http") else _BASE + href
            if gig_url in seen:
                continue
            seen.add(gig_url)

            title_el = card.select_one(".card__heading")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                # Fallback: last segment of URL slug
                title = href.rstrip("/").split("/")[-1].replace("-", " ").title()

            notif_el = card.select_one(".card__notification")
            sold_out = bool(notif_el and "sold out" in notif_el.get_text(strip=True).lower())

            gig_urls.append((gig_url, title, sold_out))

        if not gig_urls:
            return []

        # Fetch detail pages concurrently for date/time/price
        events: list[Event] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {
                pool.submit(_fetch_detail, url, today): (url, title, sold_out)
                for url, title, sold_out in gig_urls
            }
            for future in as_completed(future_map):
                url, title, sold_out = future_map[future]
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
                    sold_out=sold_out,
                ))

        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events
