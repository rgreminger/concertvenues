import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional

from concertvenues.models import Event, Venue


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _create_schema(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS venues (
            key   TEXT PRIMARY KEY,
            name  TEXT NOT NULL,
            city  TEXT NOT NULL,
            url   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            venue_key    TEXT NOT NULL REFERENCES venues(key),
            title        TEXT NOT NULL,
            date         TEXT NOT NULL,
            time         TEXT,
            url          TEXT NOT NULL,
            description  TEXT,
            image_url    TEXT,
            on_sale_date TEXT,
            price        TEXT,
            sold_out     INTEGER NOT NULL DEFAULT 0,
            UNIQUE(venue_key, url)
        );
    """)
    conn.commit()


# --- Venues ---

def upsert_venue(conn: sqlite3.Connection, venue: Venue) -> None:
    conn.execute(
        """
        INSERT INTO venues (key, name, city, url)
        VALUES (:key, :name, :city, :url)
        ON CONFLICT(key) DO UPDATE SET
            name = excluded.name,
            city = excluded.city,
            url  = excluded.url
        """,
        {"key": venue.key, "name": venue.name, "city": venue.city, "url": venue.url},
    )
    conn.commit()


def get_all_venues(conn: sqlite3.Connection) -> list[Venue]:
    rows = conn.execute("SELECT key, name, city, url FROM venues ORDER BY name").fetchall()
    return [Venue(key=r["key"], name=r["name"], city=r["city"], url=r["url"]) for r in rows]


# --- Events ---

def upsert_event(conn: sqlite3.Connection, event: Event) -> None:
    conn.execute(
        """
        INSERT INTO events (venue_key, title, date, time, url, description, image_url, on_sale_date, price, sold_out)
        VALUES (:venue_key, :title, :date, :time, :url, :description, :image_url, :on_sale_date, :price, :sold_out)
        ON CONFLICT(venue_key, url) DO UPDATE SET
            title        = excluded.title,
            date         = excluded.date,
            time         = excluded.time,
            description  = excluded.description,
            image_url    = excluded.image_url,
            on_sale_date = excluded.on_sale_date,
            price        = excluded.price,
            sold_out     = excluded.sold_out
        """,
        {
            "venue_key":    event.venue_key,
            "title":        event.title,
            "date":         event.date.isoformat(),
            "time":         event.time.isoformat() if event.time else None,
            "url":          event.url,
            "description":  event.description,
            "image_url":    event.image_url,
            "on_sale_date": event.on_sale_date.isoformat() if event.on_sale_date else None,
            "price":        event.price,
            "sold_out":     1 if event.sold_out else 0,
        },
    )
    conn.commit()


def get_upcoming_events(
    conn: sqlite3.Connection,
    from_date: Optional[date] = None,
    days_ahead: int = 90,
) -> list[Event]:
    start = (from_date or date.today()).isoformat()
    end = date.fromordinal(date.fromisoformat(start).toordinal() + days_ahead).isoformat()
    rows = conn.execute(
        """
        SELECT id, venue_key, title, date, time, url, description, image_url, on_sale_date, price, sold_out
        FROM events
        WHERE date >= ? AND date <= ?
        ORDER BY date, time
        """,
        (start, end),
    ).fetchall()
    return [_row_to_event(r) for r in rows]


def delete_past_events(conn: sqlite3.Connection) -> int:
    today = date.today().isoformat()
    cursor = conn.execute("DELETE FROM events WHERE date < ?", (today,))
    conn.commit()
    return cursor.rowcount


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        venue_key=row["venue_key"],
        title=row["title"],
        date=date.fromisoformat(row["date"]),
        time=time.fromisoformat(row["time"]) if row["time"] else None,
        url=row["url"],
        description=row["description"],
        image_url=row["image_url"],
        on_sale_date=date.fromisoformat(row["on_sale_date"]) if row["on_sale_date"] else None,
        price=row["price"],
        sold_out=bool(row["sold_out"]),
    )
