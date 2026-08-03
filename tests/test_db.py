"""
Tests for the database layer, focused on what happens between CI runs.

The workflow now restores data/ from the previous run's cache, so the database
is long-lived rather than rebuilt from scratch. These tests pin the behaviour
that relies on: a venue that fails to scrape keeps the events we already had,
re-scraping updates rows in place, and dropping a venue from config actually
removes it.
"""

from datetime import date, timedelta

import pytest

import concertvenues.db as db
from concertvenues.models import Event, Venue

SOON = date.today() + timedelta(days=10)
PAST = date.today() - timedelta(days=3)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "events.db")
    db.upsert_venue(connection, Venue(key="earthackney", name="EartH Hackney",
                                      city="London", url="https://earthackney.co.uk/events/"))
    db.upsert_venue(connection, Venue(key="koko", name="KOKO",
                                      city="London", url="https://koko.co.uk/"))
    return connection


def event(venue_key="earthackney", title="Ebony", event_date=SOON,
          url="https://earthackney.co.uk/events/ebony/", sold_out=False):
    return Event(venue_key=venue_key, title=title, date=event_date,
                 url=url, sold_out=sold_out)


def test_blocked_venue_keeps_its_known_events(conn):
    """The whole point of caching data/: a bad scrape must not empty a venue."""
    db.upsert_event(conn, event())

    # Next run: the scraper is blocked and returns nothing at all for this venue.
    db.delete_past_events(conn)

    upcoming = db.get_upcoming_events(conn)
    assert [e.title for e in upcoming] == ["Ebony"]


def test_rescraping_updates_in_place(conn):
    db.upsert_event(conn, event(sold_out=False))
    db.upsert_event(conn, event(sold_out=True))

    upcoming = db.get_upcoming_events(conn)
    assert len(upcoming) == 1, "same venue/url/date should not accumulate duplicates"
    assert upcoming[0].sold_out is True


def test_past_events_are_still_cleaned_up(conn):
    db.upsert_event(conn, event())
    db.upsert_event(conn, event(title="Old Gig", event_date=PAST,
                                url="https://earthackney.co.uk/events/old/"))

    assert db.delete_past_events(conn) == 1
    assert [e.title for e in db.get_upcoming_events(conn)] == ["Ebony"]


def test_disabling_a_venue_removes_it_and_its_events(conn):
    db.upsert_event(conn, event())
    db.upsert_event(conn, event(venue_key="koko", title="Some Band",
                                url="https://koko.co.uk/some-band/"))

    dropped = db.delete_disabled_venues(conn, {"earthackney"})

    assert dropped == 1
    assert [e.venue_key for e in db.get_upcoming_events(conn)] == ["earthackney"]
    assert [v.key for v in db.get_all_venues(conn)] == ["earthackney"], (
        "a disabled venue must also leave the filter UI, which reads the venues table"
    )


def test_empty_enabled_set_does_not_wipe_the_database(conn):
    """An empty config is a loading bug, not an instruction to delete everything."""
    db.upsert_event(conn, event())

    assert db.delete_disabled_venues(conn, set()) == 0
    assert len(db.get_upcoming_events(conn)) == 1
