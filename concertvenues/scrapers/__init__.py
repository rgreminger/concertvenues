"""
Scraper registry.

To add a new venue scraper:
1. Copy venue_template.py to <venue_key>.py
2. Implement the class, setting venue_key and venue_name
3. Import and register it in the SCRAPERS dict below
"""

# from concertvenues.scrapers.fillmore import FillmoreScraper
# from concertvenues.scrapers.independent import IndependentScraper

from concertvenues.scrapers.base import BaseScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    # "fillmore": FillmoreScraper,
    # "independent": IndependentScraper,
}
