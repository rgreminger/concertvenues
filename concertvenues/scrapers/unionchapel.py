"""
Union Chapel scraper — NOT YET IMPLEMENTED.

The Union Chapel website (unionchapel.org.uk/venue/whats-on/) uses an
Isotope.js grid that is populated dynamically. The static HTML contains
no event cards — only an empty #items container.

Options to implement:
  1. Headless browser (Playwright) to render the JS and scrape the DOM.
  2. Check for an underlying API that the Isotope grid fetches from
     (inspect Network tab in browser DevTools for XHR calls).
"""

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper


class UnionChapelScraper(BaseScraper):
    venue_key = "unionchapel"
    venue_name = "Union Chapel"

    def fetch_events(self) -> list[Event]:
        raise NotImplementedError(
            "Union Chapel website requires JavaScript rendering (Isotope grid). "
            "Implement using Playwright or find the underlying API."
        )
