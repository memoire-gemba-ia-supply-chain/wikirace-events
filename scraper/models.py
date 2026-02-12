"""
Event data models for scraping
"""
from dataclasses import dataclass, asdict
from typing import Optional
import re


@dataclass
class RaceEvent:
    """Represents a race event"""
    id: str
    name: str
    date: str  # YYYY-MM-DD format
    city: str
    country: str
    countryCode: str
    discipline: str  # "Running", "Trail", "Triathlon"
    distance: str  # "Marathon", "Half Marathon", "Ultra Trail", etc.
    elevationGain: Optional[int]
    description: str
    registrationUrl: str
    imageUrl: str
    price: Optional[float]
    currency: Optional[str]
    registrationStatus: Optional[str]
    gpxUrl: Optional[str]
    websiteUrl: Optional[str]
    source: Optional[str] = None
    isFallback: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary, filtering out None values for optional fields"""
        d = asdict(self)
        # Keep None for optional fields - the iOS app handles them
        return d
    
    @staticmethod
    def generate_id(name: str, date_str: str, location_hint: str = "") -> str:
        """Generate a unique ID from name and date"""
        base = f"{name} {location_hint}".strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
        date_slug = re.sub(r"[^0-9]", "", date_str)
        return f"{slug}-{date_slug}"
