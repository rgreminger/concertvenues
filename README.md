# Concert Venues

A static website generator that scrapes upcoming concert events from multiple venue websites and publishes them via GitHub Pages. It runs nightly via GitHub Actions.

## Project Structure

```
concertvenues/
├── concertvenues/          # Python package
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Config loader (config.toml)
│   ├── db.py               # SQLite access layer
│   ├── models.py           # Venue and Event dataclasses
│   ├── scrapers/
│   │   ├── base.py         # BaseScraper abstract class
│   │   ├── __init__.py     # Scraper registry
│   │   └── venue_template.py  # Copy this to add a new venue
│   └── generator/
│       └── build.py        # Jinja2-based static site builder
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and other static assets
├── output/                 # Generated site (gitignored; deployed by CI)
├── data/                   # SQLite database (gitignored)
├── tests/                  # pytest tests
├── config.toml             # Site and venue configuration
└── .github/workflows/deploy.yml  # GitHub Actions CI/CD
```

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Edit `config.toml` to set your site URL and add venues:

```toml
[site]
base_url = "https://yourusername.github.io/concertvenues"
days_ahead = 90

[venues.fillmore]
name = "The Fillmore"
city = "San Francisco, CA"
url = "https://www.thefillmore.com/events"
enabled = true
```

## Usage

```bash
cv scrape              # Scrape all enabled venues
cv scrape --venue fillmore  # Scrape one venue
cv generate            # Build the static site into output/
cv run                 # Scrape + generate in one step
```

Preview the site by opening `output/index.html` in a browser.

## Adding a New Venue Scraper

1. Copy `concertvenues/scrapers/venue_template.py` to `concertvenues/scrapers/<venue_key>.py`
2. Set `venue_key` and `venue_name` on the class
3. Implement `fetch_events()` — return a list of `Event` objects
4. Register it in `concertvenues/scrapers/__init__.py`
5. Add a `[venues.<venue_key>]` section to `config.toml`

## Running Tests

```bash
pytest
```

## GitHub Pages Deployment

1. Push this repository to GitHub
2. In **Settings → Pages**, set the source branch to `gh-pages`
3. The `deploy.yml` workflow runs nightly and on manual dispatch:
   - Scrapes all venues
   - Generates the static site
   - Deploys `output/` to the `gh-pages` branch
