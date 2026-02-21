import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class JazzCafeScraper(BaseScraper):
    venue_key = "jazzcafe"
    venue_name = "Jazz Cafe"

    def fetch_events(self) -> list[Event]:
        session = requests.Session()
        session.headers.update({"User-Agent": "concertvenues-bot/0.1"})

        response = session.get(self.url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        today = date.today()
        stubs: list[dict] = []

        # Each event block is structured as date_div.parent.parent
        date_divs = soup.find_all(class_="event-date")
        for date_div in date_divs:
            block = date_div.parent.parent

            title_el = block.select_one(".event-title")
            if not title_el:
                continue

            # Title: has a <span class="host"> (subtitle) and a main text node
            # We want just the band/act name, not the host/subtitle
            host_el = title_el.select_one(".host")
            if host_el:
                host_el.extract()
            title = title_el.get_text(separator=" ", strip=True).strip()

            link_el = block.select_one("a[href]")
            if not link_el:
                continue
            event_url = link_el["href"]

            # Parse date: "Sat21Feb" -> date
            date_text = date_div.get_text(strip=True)
            event_date = _parse_date(date_text, today)
            if event_date is None or event_date < today:
                continue

            stubs.append({
                "title": title,
                "url": event_url,
                "date": event_date,
            })

        # Fetch each event page for price + sold-out + time (parallelised)
        events: list[Event] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(_fetch_event_detail, session, stub): stub
                for stub in stubs
            }
            for future in as_completed(futures):
                stub = futures[future]
                try:
                    detail = future.result()
                except Exception:
                    detail = {}
                events.append(Event(
                    venue_key=self.venue_key,
                    title=stub["title"],
                    date=stub["date"],
                    url=stub["url"],
                    time=detail.get("time"),
                    price=detail.get("price"),
                    sold_out=detail.get("sold_out", False),
                ))

        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events


def _fetch_event_detail(session: requests.Session, stub: dict) -> dict:
    r = session.get(stub["url"], timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    result: dict = {}

    # --- Price ---
    # <div class="price"><h2>Price</h2><strong>Standing Tickets: £25</strong> ...
    price_el = soup.select_one(".price")
    if price_el:
        # Remove the "Price" heading
        h = price_el.find(["h1", "h2", "h3"])
        if h:
            h.extract()
        price_text = price_el.get_text(" ", strip=True)
        # Extract lowest £ amount
        amounts = re.findall(r"£([\d.]+)", price_text)
        if amounts:
            min_price = min(float(a) for a in amounts)
            result["price"] = f"From £{min_price:.0f}" if len(amounts) > 1 else f"£{min_price:.0f}"

    # --- Sold out ---
    # .sold-out-div is present on all pages but empty when not sold out
    sold_div = soup.select_one(".sold-out-div")
    if sold_div and sold_div.get_text(strip=True):
        result["sold_out"] = True

    # --- Time ---
    # <div class="details-grid"> contains a div with <h2>Doors</h2><p ...>19:00-22:30</p>
    details = soup.select_one(".details-grid")
    if details:
        for div in details.find_all("div", recursive=False):
            h = div.find(["h2", "h3"])
            if h and "doors" in h.get_text(strip=True).lower():
                p = div.find("p")
                if p:
                    time_str = p.get_text(strip=True).split("-")[0].strip()
                    try:
                        hh, mm = time_str.split(":")
                        result["time"] = time(int(hh), int(mm))
                    except Exception:
                        pass
                break

    return result


def _parse_date(date_text: str, reference: date) -> Optional[date]:
    """Parse 'Sat21Feb' or 'Sat 21 Feb' into a date, inferring year."""
    # Strip day-of-week (first 3 letters if alpha)
    text = re.sub(r"^[A-Za-z]{3}", "", date_text).strip()
    # Now should be like "21Feb" or "21 Feb"
    m = re.match(r"(\d{1,2})\s*([A-Za-z]{3})", text)
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH_MAP.get(m.group(2).lower())
    if not month:
        return None
    year = reference.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return None
    if (reference - candidate).days > 60:
        candidate = date(year + 1, month, day)
    return candidate
