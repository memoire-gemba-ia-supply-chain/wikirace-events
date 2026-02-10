"""
Event data models for scraping
"""
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import date
import json


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
    
    def to_dict(self) -> dict:
        """Convert to dictionary, filtering out None values for optional fields"""
        d = asdict(self)
        # Keep None for optional fields - the iOS app handles them
        return d
    
    @staticmethod
    def generate_id(name: str, date_str: str) -> str:
        """Generate a unique ID from name and date"""
        slug = name.lower().replace(" ", "-").replace("'", "")
        # Remove special characters
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return f"{slug}-{date_str}"
