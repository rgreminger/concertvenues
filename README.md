# Concert Venues

This project builds and updates a little website that keeps track of upcoming concerts/events at some venues I know that might have events that interest me. By displaying the data one one site, I don't have to check multiple sites whenever I am looking for something to do.

It also served as a test for using the capabilities of Claude Code to build a complete project with multiple components, including web scraping, data handling, and static site generation. Everything in this repository, other than these few lines above, were generated and written by Claude.

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

## Usage

```bash
cv scrape              # Scrape all enabled venues
cv scrape --venue fillmore  # Scrape one venue
cv generate            # Build the static site into output/
cv run                 # Scrape + generate in one step
cv serve              # Serve the generated site locally at http://localhost:8000
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
3. The `deploy.yml` workflow runs weekly and on manual dispatch:
   - Scrapes all venues
   - Generates the static site
   - Deploys `output/` to the `gh-pages` branch
