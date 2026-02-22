import calendar
import json
import shutil
import sqlite3
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import concertvenues.config as cfg_module
import concertvenues.db as db_module
from concertvenues.models import Event, Venue


def _event_to_dict(event: Event, venue: Venue | None) -> dict:
    """Serialise an Event to a plain dict for JSON embedding in the template."""
    if event.time:
        time_str = event.time.strftime("%H:%M")
        hour = event.time.hour
        time_of_day = "evening" if hour >= 17 else "daytime"
    else:
        time_str = None
        time_of_day = "unknown"

    return {
        "id": event.id,
        "title": event.title,
        "url": event.url,
        "date": event.date.isoformat(),
        "time": time_str,
        "time_of_day": time_of_day,
        "price": event.price,
        "sold_out": event.sold_out,
        "venue_key": event.venue_key,
        "venue_name": venue.name if venue else event.venue_key,
        "venue_url": venue.url if venue else None,
    }


def _build_months(today: date, days_ahead: int) -> list[dict]:
    """Return a list of month dicts (year, month, name, weeks) covering today + days_ahead."""
    from_date = today
    to_date = date.fromordinal(today.toordinal() + days_ahead)

    months = []
    y, m = from_date.year, from_date.month
    while (y, m) <= (to_date.year, to_date.month):
        cal = calendar.monthcalendar(y, m)

        # For the first month, drop weeks that end before today so the calendar
        # doesn't start with a wall of empty past days.
        if y == from_date.year and m == from_date.month:
            cal = [
                week for week in cal
                if max(d for d in week if d != 0) >= from_date.day
            ]

        months.append({
            "year": y,
            "month": m,
            "name": date(y, m, 1).strftime("%B %Y"),
            "weeks": cal,  # list of [Mon..Sun] lists, 0 = outside month
        })
        m += 1
        if m > 12:
            m = 1
            y += 1

    return months


def build_site(conn: sqlite3.Connection, cfg: dict, output_dir: Path) -> None:
    site_cfg = cfg_module.get_site(cfg)
    days_ahead = site_cfg.get("days_ahead", 62)
    base_url = site_cfg.get("base_url", "").rstrip("/")
    site_title = site_cfg.get("title", "Upcoming Concerts in London")

    today = date.today()

    # Load data from DB
    events = db_module.get_upcoming_events(conn, days_ahead=days_ahead)
    venues = {v.key: v for v in db_module.get_all_venues(conn)}

    # Prepare output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy static assets
    static_src = Path("static")
    static_dst = output_dir / "static"
    if static_src.exists():
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)

    # Set up Jinja2
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["base_url"] = base_url
    env.globals["site_title"] = site_title
    env.globals["generated_date"] = today.isoformat()

    # Serialise events to JSON for JS filter engine
    events_json = json.dumps(
        [_event_to_dict(e, venues.get(e.venue_key)) for e in events],
        ensure_ascii=False,
    )

    # Build month grids
    months = _build_months(today, days_ahead)

    # Venue list for filter UI
    venue_list = [
        {"key": v.key, "name": v.name}
        for v in sorted(venues.values(), key=lambda v: v.name)
        if any(e.venue_key == v.key for e in events)
    ]

    # Render index page
    _render(env, "index.html", output_dir / "index.html", {
        "months": months,
        "today": today.isoformat(),
        "events_json": events_json,
        "venue_list": venue_list,
        "page_title": site_title,
    })


def _render(env: Environment, template_name: str, dest: Path, context: dict) -> None:
    template = env.get_template(template_name)
    dest.write_text(template.render(**context), encoding="utf-8")
