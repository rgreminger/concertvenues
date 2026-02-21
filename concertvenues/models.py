from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


@dataclass
class Venue:
    key: str           # Unique identifier, matches config.toml section and scraper venue_key
    name: str
    city: str
    url: str


@dataclass
class Event:
    venue_key: str     # Foreign key to Venue.key
    title: str
    date: date
    url: str
    time: Optional[time] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    on_sale_date: Optional[date] = None
    price: Optional[str] = None        # e.g. "£25", "From £30"
    sold_out: bool = False
    # Populated by DB layer after insert
    id: Optional[int] = field(default=None, repr=False)
