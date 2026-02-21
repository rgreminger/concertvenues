"""
Placeholder tests for venue scrapers.

Pattern for testing a scraper:
1. Record real HTML from the venue page (save as tests/fixtures/<venue_key>.html)
2. Use the `responses` library to mock the HTTP request
3. Assert that fetch_events() returns correctly parsed Event objects

Example (uncomment and adapt when adding a real scraper):

    import responses as rsps
    from pathlib import Path
    from concertvenues.scrapers.fillmore import FillmoreScraper

    @rsps.activate
    def test_fillmore_scraper():
        fixture = (Path(__file__).parent / "fixtures" / "fillmore.html").read_text()
        rsps.add(rsps.GET, "https://www.thefillmore.com/events", body=fixture)

        scraper = FillmoreScraper({"url": "https://www.thefillmore.com/events"})
        events = scraper.fetch_events()

        assert len(events) > 0
        assert all(e.venue_key == "fillmore" for e in events)
        assert all(e.date is not None for e in events)
"""

from concertvenues.scrapers import SCRAPERS


def test_scraper_registry_is_dict():
    assert isinstance(SCRAPERS, dict)


def test_all_scrapers_have_venue_key():
    for key, cls in SCRAPERS.items():
        scraper = cls({})
        assert scraper.venue_key == key, (
            f"Scraper class {cls.__name__} has venue_key='{scraper.venue_key}' "
            f"but is registered under key '{key}'"
        )
