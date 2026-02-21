from abc import ABC, abstractmethod

from concertvenues.models import Event


class BaseScraper(ABC):
    # Subclasses must set these class attributes
    venue_key: str = ""
    venue_name: str = ""

    def __init__(self, venue_cfg: dict):
        """
        Args:
            venue_cfg: The [venues.<key>] section from config.toml as a dict.
                       Typically contains at least 'url' and 'enabled'.
        """
        self.venue_cfg = venue_cfg
        self.url = venue_cfg.get("url", "")

    @abstractmethod
    def fetch_events(self) -> list[Event]:
        """Fetch and return a list of upcoming Event objects for this venue."""
        ...
