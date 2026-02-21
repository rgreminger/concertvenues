"""
Template for a new venue scraper.

Steps to use this template:
1. Copy this file to <venue_key>.py  (e.g., fillmore.py)
2. Set venue_key  — must match the [venues.<key>] section in config.toml
3. Set venue_name — human-readable display name
4. Implement fetch_events() to return a list of Event objects
5. Import and register the class in scrapers/__init__.py

Tips:
- Use self.url to read the venue URL from config.toml
- Use requests + BeautifulSoup to parse HTML pages
- Use python-dateutil's parse() for robust date parsing
- If the site requires JavaScript, look into requests-html or playwright
- Keep the scraper stateless; fetch_events() should be safe to call multiple times
"""

from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper


class VenueTemplateScraper(BaseScraper):
    venue_key = "venue_template"          # <-- change this
    venue_name = "Venue Template"         # <-- change this

    def fetch_events(self) -> list[Event]:
        response = requests.get(self.url, timeout=15, headers={"User-Agent": "concertvenues/0.1"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        events: list[Event] = []

        # TODO: update the CSS selectors below to match the actual venue HTML structure
        for item in soup.select(".event-item"):
            title_el = item.select_one(".event-title")
            date_el = item.select_one(".event-date")
            link_el = item.select_one("a[href]")

            if not (title_el and date_el and link_el):
                continue

            title = title_el.get_text(strip=True)
            event_date = dateparser.parse(date_el.get_text(strip=True)).date()
            url = link_el["href"]
            if url.startswith("/"):
                # Make relative URLs absolute using the venue's base URL
                from urllib.parse import urlparse
                base = urlparse(self.url)
                url = f"{base.scheme}://{base.netloc}{url}"

            events.append(Event(
                venue_key=self.venue_key,
                title=title,
                date=event_date,
                url=url,
            ))

        return events
