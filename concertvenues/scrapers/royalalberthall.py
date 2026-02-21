"""
Royal Albert Hall scraper.

NOTE: The Royal Albert Hall website (royalalberthall.com) is protected by
Incapsula/Imperva WAF, which blocks all automated HTTP requests and even
headless browsers (Playwright/Puppeteer). The site returns a 403 bot-challenge
page for any non-interactive browser.

This scraper is a placeholder. To make it work one of the following is needed:
  - A Ticketmaster Discovery API key (RAH uses Ticketmaster for ticketing;
    their Discovery API can return RAH events with the right venue ID).
  - A paid proxy/browser service (e.g. ScrapingBee, Bright Data) that can
    solve Incapsula challenges.
  - Manual cookie injection from a real browser session.

To enable this scraper once a working approach is found, implement fetch_events()
below and register it in scrapers/__init__.py.
"""

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper


class RoyalAlbertHallScraper(BaseScraper):
    venue_key = "royalalberthall"
    venue_name = "Royal Albert Hall"

    def fetch_events(self) -> list[Event]:
        raise NotImplementedError(
            "Royal Albert Hall scraper is not yet implemented. "
            "The site is protected by Incapsula WAF and cannot be "
            "scraped with standard HTTP requests or headless browsers. "
            "See the module docstring for options."
        )
