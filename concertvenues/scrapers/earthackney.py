"""
EartH Hackney scraper.

earthackney.co.uk sits behind Cloudflare, which *intermittently* answers
datacentre IPs with a block/challenge page instead of the listing. That is why
this scraper works from a laptop but has come back with 0 events from GitHub
Actions: the failing run got its response in 330ms, far too quick for the 650KB
listing page.

Probing from a runner showed plain requests, Playwright and the sitemap all
succeeding when Cloudflare is in a good mood, so the strategies below are
ordered cheapest-first and each is only tried after the previous one came back
empty. Whatever the site actually returned is logged on failure, so the next
time this breaks we can tell a block apart from a markup change.
"""

import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from time import sleep
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper

_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
]

# Fingerprints of a Cloudflare interstitial rather than the real page.
_BLOCK_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "/cdn-cgi/challenge-platform",
    "cf_chl_opt",
    "attention required",
    "enable javascript and cookies to continue",
    "error 1015",
    "access denied",
)

_LISTING_SELECTOR = "li.list--events__item"


def _log(message: str) -> None:
    """Report fallbacks on stderr; a healthy first-try scrape stays silent."""
    print(f"[earthackney] {message}", file=sys.stderr, flush=True)


def _browser_headers(user_agent: str) -> dict:
    """The header set a real Chrome sends, minus Accept-Encoding.

    Leaving Accept-Encoding to urllib3 matters: it advertises only the codecs it
    can actually decode, and this origin serves zstd. Pinning the header by hand
    earns an undecodable body that parses to 0 events — a block that isn't one.
    """
    if "Windows" in user_agent:
        platform = '"Windows"'
    elif "Macintosh" in user_agent:
        platform = '"macOS"'
    else:
        platform = '"Linux"'

    chrome_major = re.search(r"Chrome/(\d+)", user_agent)
    version = chrome_major.group(1) if chrome_major else "140"

    return {
        "User-Agent": user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Sec-Ch-Ua": (
            f'"Chromium";v="{version}", "Not=A?Brand";v="24", '
            f'"Google Chrome";v="{version}"'
        ),
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": platform,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


def _describe(status: int, html: str) -> str:
    """One-line summary of a response, for working out why parsing found nothing."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else "(no title)"
    lowered = html[:20_000].lower()
    hits = [marker for marker in _BLOCK_MARKERS if marker in lowered]
    verdict = f"cloudflare challenge ({', '.join(hits)})" if hits else "no challenge markers"
    return f"HTTP {status}, {len(html) // 1024}KB, title={title!r}, {verdict}"


def _sitemap_locs(xml: str, wrapper: str) -> list[str]:
    """Direct <loc> children of every <wrapper> element.

    Direct children only: entries also carry a nested <image:image><image:loc>
    with the artwork, which a plain search for "loc" would hand back as if it
    were a page.
    """
    soup = BeautifulSoup(xml, "xml")
    locs = []
    for element in soup.find_all(wrapper):
        loc = element.find("loc", recursive=False)
        if loc:
            locs.append(loc.get_text(strip=True))
    return locs


def _parse_time_range(text: str) -> time | None:
    """'19:30\n - 23:00' -> time(19, 30). Only the start time interests us."""
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


class EarthAckneyScraper(BaseScraper):
    venue_key = "earthackney"
    venue_name = "EartH Hackney"

    def fetch_events(self) -> list[Event]:
        strategies = (
            ("requests", self._fetch_via_requests),
            ("playwright", self._fetch_via_playwright),
            ("sitemap", self._fetch_via_sitemap),
        )

        for name, strategy in strategies:
            try:
                events = strategy()
            except Exception as exc:
                _log(f"{name} strategy raised {type(exc).__name__}: {exc}")
                continue
            if events:
                if name != "requests":
                    _log(f"{name} strategy recovered {len(events)} events")
                return events
            _log(f"{name} strategy found no events, trying the next one")

        _log("every strategy came back empty — Cloudflare block or the markup moved")
        return []

    # --- Strategy 1: plain HTTP, retried with fresh identities ---------------

    def _fetch_via_requests(self) -> list[Event]:
        """Retry the listing a few times, changing user agent and backing off.

        The block is intermittent, so a second attempt a few seconds later
        against a different Cloudflare edge often just works.
        """
        for attempt, user_agent in enumerate(_USER_AGENTS):
            if attempt:
                # Exponential backoff with jitter, so retries don't look like a bot
                # hammering the origin on a fixed cadence.
                sleep(2 ** attempt + random.uniform(0, 1.5))

            session = requests.Session()
            session.headers.update(_browser_headers(user_agent))

            # Land on the homepage first: it sets any Cloudflare cookies and makes
            # the listing request look like in-site navigation rather than a
            # cold hit straight at /events/.
            try:
                session.get(urljoin(self.url, "/"), timeout=20)
                session.headers.update({
                    "Referer": urljoin(self.url, "/"),
                    "Sec-Fetch-Site": "same-origin",
                })
            except requests.RequestException:
                pass  # Warm-up is a nicety; the real request below still gets a go.

            response = session.get(self.url, timeout=25)
            if response.status_code != 200:
                _log(f"attempt {attempt + 1}: {_describe(response.status_code, response.text)}")
                continue

            events = self._parse_listing(response.text)
            if events:
                return events
            _log(f"attempt {attempt + 1}: {_describe(response.status_code, response.text)}")

        return []

    # --- Strategy 2: a real browser -----------------------------------------

    def _fetch_via_playwright(self) -> list[Event]:
        """Drive headless Chromium, which clears JS challenges on its own.

        A real browser brings a real TLS fingerprint and runs the challenge
        script, so it gets through cases where requests cannot.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                context = browser.new_context(
                    # The default UA says "HeadlessChrome", which is an easy tell.
                    user_agent=_USER_AGENTS[0],
                    viewport={"width": 1440, "height": 900},
                    locale="en-GB",
                    timezone_id="Europe/London",
                    extra_http_headers={"Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8"},
                )
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                page = context.new_page()
                page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)

                try:
                    page.wait_for_selector(_LISTING_SELECTOR, timeout=30_000)
                except Exception:
                    # An interstitial usually resolves itself and redirects within
                    # a few seconds; give it that chance before giving up.
                    _log("playwright: listing did not appear, waiting out a challenge")
                    page.wait_for_timeout(8_000)

                html = page.content()
            finally:
                browser.close()

        events = self._parse_listing(html)
        if not events:
            _log(f"playwright: {_describe(200, html)}")
        return events

    # --- Strategy 3: the sitemap, which is a different route entirely --------

    def _fetch_via_sitemap(self) -> list[Event]:
        """Rebuild the listing from /sitemap-post-type-event.xml + detail pages.

        Slower (one request per event) but it never touches /events/, so a rule
        aimed at the listing page doesn't apply to it.
        """
        urls = self._event_urls_from_sitemap()
        if not urls:
            return []

        _log(f"sitemap: fetching {len(urls)} event pages")
        today = date.today()
        with ThreadPoolExecutor(max_workers=8) as pool:
            parsed = pool.map(lambda u: self._parse_detail(u, today), urls)

        events = [event for event in parsed if event is not None]
        events.sort(key=lambda e: (e.date, e.time or time.min))
        return events

    def _event_urls_from_sitemap(self) -> list[str]:
        headers = _browser_headers(_USER_AGENTS[0])

        # Read the index rather than hardcoding the child name, so a rename on
        # their side doesn't silently kill this fallback.
        index = requests.get(urljoin(self.url, "/sitemap.xml"), headers=headers, timeout=25)
        index.raise_for_status()
        index_locs = _sitemap_locs(index.text, "sitemap")
        # Only the upcoming-events post type: skip past-event, and skip the
        # taxonomy-event-{type,genre,venue} sitemaps, which are term archives
        # and would triple the number of pages fetched for nothing.
        children = [
            u for u in index_locs
            if "event" in u and "past" not in u and "taxonomy" not in u
        ]
        if not children:
            children = [urljoin(self.url, "/sitemap-post-type-event.xml")]

        urls: list[str] = []
        seen: set[str] = set()
        listing = self.url.rstrip("/")
        for child in children:
            response = requests.get(child, headers=headers, timeout=25)
            if response.status_code != 200:
                continue
            for url in _sitemap_locs(response.text, "url"):
                if url.rstrip("/") == listing or url in seen:
                    continue
                seen.add(url)
                urls.append(url)

        return urls

    def _parse_detail(self, url: str, today: date) -> Event | None:
        """Pull one event out of its own page (same microdata as the listing)."""
        try:
            response = requests.get(url, headers=_browser_headers(_USER_AGENTS[0]), timeout=25)
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        date_el = soup.select_one("time[itemprop=startDate]")
        if not date_el or not date_el.get("datetime"):
            return None
        try:
            event_date = datetime.fromisoformat(date_el["datetime"]).date()
        except ValueError:
            return None
        if event_date < today:
            return None

        title_el = soup.select_one("h1[itemprop=name]") or soup.select_one("h1.event__title")
        if not title_el:
            return None

        times_el = soup.select_one(".event__times")
        image_el = soup.select_one("meta[property='og:image']")
        ticket_el = soup.select_one(".ticket-note")

        return Event(
            venue_key=self.venue_key,
            title=title_el.get_text(strip=True),
            date=event_date,
            time=_parse_time_range(times_el.get_text()) if times_el else None,
            url=url,
            sold_out=bool(ticket_el) and "sold out" in ticket_el.get_text(strip=True).lower(),
            price=None,
            image_url=image_el.get("content") if image_el else None,
        )

    # --- Shared parsing ------------------------------------------------------

    def _parse_listing(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "lxml")

        events: list[Event] = []
        today = date.today()

        for item in soup.select(_LISTING_SELECTOR):
            # --- Title ---
            title_el = item.select_one(".list--events__item__title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            # --- URL ---
            link_el = item.select_one(".list--events__item__image a")
            if not link_el:
                continue
            event_url = urljoin(self.url, link_el["href"])

            # --- Date & Time ---
            # <time itemprop="startDate" datetime="2026-02-27T00:00:00+00:00">
            date_el = item.select_one("time[itemprop=startDate]")
            if not date_el or not date_el.get("datetime"):
                continue
            try:
                dt = datetime.fromisoformat(date_el["datetime"])
                event_date = dt.date()
            except ValueError:
                continue

            if event_date < today:
                continue

            # Start time from <time class="time">19:00\n - 23:00</time>
            time_el = item.select_one("time.time")
            event_time = _parse_time_range(time_el.get_text()) if time_el else None

            # --- Sold out & Price ---
            ticket_el = item.select_one(".ticket-note")
            sold_out = False
            price = None
            if ticket_el:
                ticket_text = ticket_el.get_text(strip=True)
                sold_out = "sold out" in ticket_text.lower()
                # Price is not shown on listing page for Earth; skip for now
                # (individual event pages would be needed)

            # --- Image ---
            image_url = None
            img_el = item.select_one("img.event-image")
            if img_el and img_el.get("src"):
                image_url = img_el["src"]

            events.append(Event(
                venue_key=self.venue_key,
                title=title,
                date=event_date,
                time=event_time,
                url=event_url,
                sold_out=sold_out,
                price=price,
                image_url=image_url,
            ))

        return events
