"""
O2 Academy Brixton & O2 Forum Kentish Town scrapers — uses Playwright.

Both venues share the same Academy Music Group platform (Next.js/React).
Listing URL patterns:
  - Brixton:      https://www.academymusicgroup.com/o2academybrixton/events/
  - Kentish Town: https://www.academymusicgroup.com/o2forumkentishtown/events/

Event cards: [data-testid="content-events-module__event-card"]
  - Title:    img[alt] inside the card
  - Datetime: time[datetime]  → ISO 8601 e.g. "2026-02-27T19:00:00.000Z"
  - URL:      a[href*="/events/"]  (relative path, prepend base URL)
  - CTA text: "Find Tickets" = available, "More Info" = info only (no tickets yet),
              sold-out not observed but would appear as different CTA text.
  - No price on listing page.
"""

from datetime import date, datetime, time, timezone
from typing import Optional

from bs4 import BeautifulSoup

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_AMG_BASE = "https://www.academymusicgroup.com"


def _scrape_amg_venue(url: str, venue_key: str, headless_url: str) -> list[Event]:
    from playwright.sync_api import sync_playwright

    today = date.today()
    events: list[Event] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "lxml")

    seen: set[tuple[str, date]] = set()
    for card in soup.select('[data-testid="content-events-module__event-card"]'):
        # Title from image alt text
        img = card.select_one("img[alt]")
        title = img.get("alt", "").strip() if img else ""
        if not title:
            continue

        # Date/time from <time datetime="...">
        time_el = card.select_one("time[datetime]")
        if not time_el:
            continue
        dt_str = time_el.get("datetime", "")
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            # Convert to local date (UTC is close enough for London events)
            event_date = dt.date()
            event_time: Optional[time] = dt.time().replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

        if event_date < today:
            continue

        # URL (relative)
        link_el = card.select_one(f'a[href*="{headless_url}/events/"]')
        if not link_el:
            link_el = card.select_one("a[href*=\"/events/\"]")
        if not link_el:
            continue
        href = link_el.get("href", "")
        event_url = href if href.startswith("http") else _AMG_BASE + href

        # Deduplicate by (url, date) — same show can have multiple nights
        key = (event_url, event_date)
        if key in seen:
            continue
        seen.add(key)

        events.append(Event(
            venue_key=venue_key,
            title=title,
            date=event_date,
            time=event_time,
            url=event_url,
        ))

    events.sort(key=lambda e: (e.date, e.time or time.min))
    return events


class O2AcademyBrixtonScraper(BaseScraper):
    venue_key = "o2academybrixton"
    venue_name = "O2 Academy Brixton"

    def fetch_events(self) -> list[Event]:
        return _scrape_amg_venue(self.url, self.venue_key, "o2academybrixton")


class O2ForumKentishTownScraper(BaseScraper):
    venue_key = "o2forumkentishtown"
    venue_name = "O2 Forum Kentish Town"

    def fetch_events(self) -> list[Event]:
        return _scrape_amg_venue(self.url, self.venue_key, "o2forumkentishtown")
