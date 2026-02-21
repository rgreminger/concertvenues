"""
Scraper registry.

To add a new venue scraper:
1. Copy venue_template.py to <venue_key>.py
2. Implement the class, setting venue_key and venue_name
3. Import and register it in the SCRAPERS dict below
"""

from concertvenues.scrapers.alexandrapalace import AlexandraPalaceScraper
from concertvenues.scrapers.base import BaseScraper
from concertvenues.scrapers.earthackney import EarthAckneyScraper
from concertvenues.scrapers.electricballroom import ElectricBallroomScraper
from concertvenues.scrapers.islingtonassemblyhall import IslingtonAssemblyHallScraper
from concertvenues.scrapers.jazzcafe import JazzCafeScraper
from concertvenues.scrapers.koko import KokoScraper
from concertvenues.scrapers.o2academy import O2AcademyBrixtonScraper, O2ForumKentishTownScraper
from concertvenues.scrapers.roundhouse import RoundhouseScraper
from concertvenues.scrapers.thegarage import TheGarageScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    "electricballroom": ElectricBallroomScraper,
    "earthackney": EarthAckneyScraper,
    "jazzcafe": JazzCafeScraper,
    "roundhouse": RoundhouseScraper,
    "islingtonassemblyhall": IslingtonAssemblyHallScraper,
    "alexandrapalace": AlexandraPalaceScraper,
    "o2academybrixton": O2AcademyBrixtonScraper,
    "o2forumkentishtown": O2ForumKentishTownScraper,
    "koko": KokoScraper,
    "thegarage": TheGarageScraper,
}
