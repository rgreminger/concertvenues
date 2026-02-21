import re
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

from concertvenues.models import Event
from concertvenues.scrapers.base import BaseScraper


class EarthAckneyScraper(BaseScraper):
    venue_key = "earthackney"
    venue_name = "EartH Hackney"

    def fetch_events(self) -> list[Event]:
        response = requests.get(
            self.url,
            timeout=15,
            headers={"User-Agent": "concertvenues-bot/0.1"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        events: list[Event] = []
        today = date.today()

        for item in soup.select("li.list--events__item"):
            # --- Title ---
            title_el = item.select_one(".list--events__item__title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            # --- URL ---
            link_el = item.select_one(".list--events__item__image a")
            if not link_el:
                continue
            event_url = link_el["href"]

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
            event_time = None
            time_el = item.select_one("time.time")
            if time_el:
                time_text = time_el.get_text(strip=True)
                # "19:00 - 23:00" or "19:00\n - 23:00" — take the first part
                start_str = time_text.split("-")[0].strip()
                try:
                    from datetime import time as dt_time
                    h, m = start_str.split(":")
                    event_time = dt_time(int(h), int(m))
                except Exception:
                    pass

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
