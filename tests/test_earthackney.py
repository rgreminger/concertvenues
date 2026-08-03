"""
Tests for the EartH Hackney scraper, whose job is mostly to survive Cloudflare.

Cloudflare intermittently answers CI runners with a challenge page instead of
the listing, so the scraper walks a chain of strategies. These tests pin down
both the parsing and, more importantly, that a blocked listing really does fall
through to the next strategy instead of quietly reporting 0 events.
"""

from datetime import date, time
from pathlib import Path
from unittest.mock import patch

import pytest
import responses as rsps

from concertvenues.scrapers.earthackney import EarthAckneyScraper

URL = "https://earthackney.co.uk/events/"
FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture
def scraper():
    return EarthAckneyScraper({"url": URL})


@pytest.fixture(autouse=True)
def no_backoff():
    """Skip the retry sleeps so the tests don't sit there waiting."""
    with patch("concertvenues.scrapers.earthackney.sleep"):
        yield


def mock_listing(body: str, status: int = 200) -> None:
    rsps.add(rsps.GET, "https://earthackney.co.uk/", body="<html></html>", status=200)
    rsps.add(rsps.GET, URL, body=body, status=status)


def mock_sitemap() -> None:
    rsps.add(rsps.GET, "https://earthackney.co.uk/sitemap.xml",
             body=fixture("earthackney_sitemap_index.xml"), content_type="text/xml")
    rsps.add(rsps.GET, "https://earthackney.co.uk/sitemap-post-type-event.xml",
             body=fixture("earthackney_sitemap_events.xml"), content_type="text/xml")
    rsps.add(rsps.GET,
             "https://earthackney.co.uk/events/ebony-6th-aug-earth-london-tickets-yo67ep/",
             body=fixture("earthackney_detail.html"))


# --- Parsing ---------------------------------------------------------------


@rsps.activate
def test_parses_listing(scraper):
    mock_listing(fixture("earthackney_listing.html"))

    events = scraper.fetch_events()

    assert len(events) == 2, "the third fixture item is in the past and should be dropped"
    first = events[0]
    assert first.title == "Ebony"
    assert first.date == date(2099, 8, 6)
    assert first.time == time(19, 30)
    assert first.venue_key == "earthackney"
    assert first.url.endswith("/events/ebony-6th-aug-earth-london-tickets-yo67ep/")
    assert first.image_url.startswith("https://dice-media.imgix.net/")
    assert first.sold_out is False


@rsps.activate
def test_marks_sold_out_and_resolves_relative_urls(scraper):
    mock_listing(fixture("earthackney_listing.html"))

    events = scraper.fetch_events()

    sold_out = next(e for e in events if e.title == "A Sold Out Show")
    assert sold_out.sold_out is True
    assert sold_out.url == (
        "https://earthackney.co.uk/events/sold-out-show-earth-london-tickets-abc123/"
    ), "hrefs on the listing are sometimes relative"


# --- Getting past Cloudflare -----------------------------------------------


@rsps.activate
def test_retries_the_listing_before_moving_on(scraper):
    """A challenge page is not a 'no events today' — try again."""
    mock_listing(fixture("earthackney_challenge.html"))

    with patch.object(EarthAckneyScraper, "_fetch_via_playwright", return_value=[]):
        with patch.object(EarthAckneyScraper, "_fetch_via_sitemap", return_value=[]):
            scraper.fetch_events()

    listing_calls = [c for c in rsps.calls if c.request.url == URL]
    assert len(listing_calls) == 3, "should retry with each of the three user agents"
    user_agents = {c.request.headers["User-Agent"] for c in listing_calls}
    assert len(user_agents) == 3, "each retry should present a different user agent"


@rsps.activate
def test_falls_back_to_playwright_when_blocked(scraper):
    mock_listing(fixture("earthackney_challenge.html"), status=403)
    recovered = scraper._parse_listing(fixture("earthackney_listing.html"))

    with patch.object(EarthAckneyScraper, "_fetch_via_playwright", return_value=recovered) as pw:
        events = scraper.fetch_events()

    assert pw.called
    assert len(events) == 2


@rsps.activate
def test_falls_back_to_sitemap_when_playwright_also_fails(scraper):
    mock_listing(fixture("earthackney_challenge.html"))
    mock_sitemap()

    with patch.object(EarthAckneyScraper, "_fetch_via_playwright", return_value=[]):
        events = scraper.fetch_events()

    assert len(events) == 1
    assert events[0].title == "Ebony"
    assert events[0].date == date(2099, 8, 6)
    assert events[0].time == time(19, 30)
    assert events[0].image_url == (
        "https://earthackney.co.uk/wp-content/uploads/2026/07/ebony.jpg"
    )


@rsps.activate
def test_survives_playwright_not_being_installed(scraper):
    mock_listing(fixture("earthackney_challenge.html"))
    mock_sitemap()

    with patch.object(EarthAckneyScraper, "_fetch_via_playwright",
                      side_effect=ImportError("No module named 'playwright'")):
        events = scraper.fetch_events()

    assert len(events) == 1, "a missing browser must not sink the whole scrape"


@rsps.activate
def test_sitemap_skips_image_and_taxonomy_entries(scraper):
    """<image:loc> artwork and term archives are not event pages."""
    mock_sitemap()

    urls = scraper._event_urls_from_sitemap()

    assert urls == [
        "https://earthackney.co.uk/events/ebony-6th-aug-earth-london-tickets-yo67ep/"
    ], "the listing URL, the artwork and the taxonomy sitemaps should all be skipped"


@rsps.activate
def test_returns_empty_when_everything_is_blocked(scraper):
    mock_listing(fixture("earthackney_challenge.html"))

    with patch.object(EarthAckneyScraper, "_fetch_via_playwright", return_value=[]):
        with patch.object(EarthAckneyScraper, "_fetch_via_sitemap", return_value=[]):
            events = scraper.fetch_events()

    assert events == [], "an exhausted chain reports nothing, which the CLI warns about"
