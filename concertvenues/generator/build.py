import shutil
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import concertvenues.config as cfg_module
import concertvenues.db as db_module
from concertvenues.models import Event, Venue


def build_site(conn: sqlite3.Connection, cfg: dict, output_dir: Path) -> None:
    site_cfg = cfg_module.get_site(cfg)
    days_ahead = site_cfg.get("days_ahead", 90)
    base_url = site_cfg.get("base_url", "").rstrip("/")
    site_title = site_cfg.get("title", "Upcoming Concerts")

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
    env.globals["generated_date"] = date.today().isoformat()

    # Group events by venue
    events_by_venue: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        events_by_venue[event.venue_key].append(event)

    # Render index page (all events, sorted by date)
    _render(env, "index.html", output_dir / "index.html", {
        "events": events,
        "venues": venues,
        "page_title": site_title,
    })

    # Render per-venue pages
    venues_dir = output_dir / "venues"
    venues_dir.mkdir(exist_ok=True)
    for venue_key, venue_events in events_by_venue.items():
        venue = venues.get(venue_key)
        _render(env, "venue.html", venues_dir / f"{venue_key}.html", {
            "venue": venue,
            "events": venue_events,
            "page_title": venue.name if venue else venue_key,
        })


def _render(env: Environment, template_name: str, dest: Path, context: dict) -> None:
    template = env.get_template(template_name)
    dest.write_text(template.render(**context), encoding="utf-8")
