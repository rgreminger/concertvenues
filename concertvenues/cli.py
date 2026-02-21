import argparse
import sys
from pathlib import Path

from concertvenues import __version__
import concertvenues.config as cfg_module
import concertvenues.db as db_module
from concertvenues.scrapers import SCRAPERS
from concertvenues.generator.build import build_site


def _scrape(args, cfg):
    db_path = cfg_module.get_database_path(cfg)
    conn = db_module.connect(db_path)
    enabled_venues = cfg_module.get_venues(cfg)

    targets = {}
    if args.venue:
        if args.venue not in SCRAPERS:
            print(f"Error: no scraper registered for venue '{args.venue}'.", file=sys.stderr)
            print(f"Available scrapers: {', '.join(sorted(SCRAPERS))}", file=sys.stderr)
            sys.exit(1)
        targets = {args.venue: SCRAPERS[args.venue]}
    else:
        targets = {k: v for k, v in SCRAPERS.items() if k in enabled_venues}

    if not targets:
        print("No enabled scrapers found. Check your config.toml [venues] section.")
        return

    for key, scraper_cls in targets.items():
        venue_cfg = enabled_venues.get(key, {})
        scraper = scraper_cls(venue_cfg)
        print(f"Scraping {scraper.venue_name} ...", end=" ", flush=True)
        try:
            # Ensure the venue row exists before inserting events
            from concertvenues.models import Venue
            db_module.upsert_venue(conn, Venue(
                key=key,
                name=scraper.venue_name,
                city=venue_cfg.get("city", ""),
                url=venue_cfg.get("url", ""),
            ))
            events = scraper.fetch_events()
            for event in events:
                db_module.upsert_event(conn, event)
            print(f"{len(events)} events saved.")
        except Exception as exc:
            print(f"FAILED ({exc})")

    removed = db_module.delete_past_events(conn)
    if removed:
        print(f"Cleaned up {removed} past events from the database.")


def _generate(args, cfg):
    site_cfg = cfg_module.get_site(cfg)
    db_path = cfg_module.get_database_path(cfg)
    conn = db_module.connect(db_path)
    days_ahead = site_cfg.get("days_ahead", 90)
    output_dir = Path(site_cfg.get("output_dir", "output"))
    build_site(conn, cfg, output_dir)
    print(f"Site generated in '{output_dir}/'.")


def main():
    parser = argparse.ArgumentParser(
        prog="cv",
        description="Concert Venues static site generator",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config", default="config.toml", metavar="PATH",
        help="Path to config.toml (default: config.toml)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # scrape
    sp_scrape = subparsers.add_parser("scrape", help="Run scrapers and update the database")
    sp_scrape.add_argument(
        "--venue", metavar="KEY",
        help="Only scrape this venue (by its key in config.toml)",
    )

    # generate
    subparsers.add_parser("generate", help="Generate the static website from the database")

    # run (scrape + generate)
    sp_run = subparsers.add_parser("run", help="Scrape all venues then generate the site")
    sp_run.add_argument(
        "--venue", metavar="KEY",
        help="Only scrape this venue (by its key in config.toml)",
    )

    args = parser.parse_args()
    cfg = cfg_module.load(Path(args.config))

    if args.command == "scrape":
        _scrape(args, cfg)
    elif args.command == "generate":
        _generate(args, cfg)
    elif args.command == "run":
        _scrape(args, cfg)
        _generate(args, cfg)


if __name__ == "__main__":
    main()
