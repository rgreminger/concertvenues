"""
Islington Assembly Hall scraper — uses Ticketmaster Discovery API (venue ID: KovZ9177akf).
Requires TICKETMASTER_API_KEY in the 'secrets' file or environment.
"""

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper
from concertvenues.scrapers.ticketmaster import fetch_tm_events, get_api_key

_VENUE_ID = "KovZ9177akf"


class IslingtonAssemblyHallScraper(BaseScraper):
    venue_key = "islingtonassemblyhall"
    venue_name = "Islington Assembly Hall"

    def fetch_events(self) -> list[Event]:
        return fetch_tm_events(_VENUE_ID, self.venue_key, self.url, get_api_key(self.venue_cfg))
