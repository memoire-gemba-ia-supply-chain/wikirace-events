"""
Triathlon source.
Primary: Ahotu triathlon calendar.
Fallback: curated world majors when remote extraction is low.
"""
from __future__ import annotations

import re
from typing import List

from models import RaceEvent
from sources.ahotu import fetch_ahotu_triathlons
from sources.common import map_country_code, normalize_registration_status


def _curated_triathlon_fallback() -> List[RaceEvent]:
    curated = [
        ("Ironman 70.3 Agadir", "2026-10-25", "Agadir", "Morocco", "https://www.ironman.com/im703-agadir", "Half Ironman"),
        ("Ironman 70.3 World Championship", "2026-09-13", "Lahti", "Finland", "https://www.ironman.com/im703-world-championship", "Half Ironman"),
        ("Ironman World Championship", "2026-10-10", "Kailua-Kona", "United States", "https://www.ironman.com/im-world-championship", "Ironman"),
        ("Challenge Roth", "2026-07-05", "Roth", "Germany", "https://www.challenge-roth.com/en", "Ironman"),
        ("Norseman Xtreme Triathlon", "2026-08-01", "Eidfjord", "Norway", "https://nxtri.com", "Ironman"),
        ("Ironman Frankfurt", "2026-06-28", "Frankfurt", "Germany", "https://www.ironman.com/im-frankfurt", "Ironman"),
    ]

    events: List[RaceEvent] = []
    for name, date_str, city, country, reg_url, distance in curated:
        events.append(
            RaceEvent(
                id=RaceEvent.generate_id(name=name, date_str=date_str, location_hint=city),
                name=name,
                date=date_str,
                city=city,
                country=country,
                countryCode=map_country_code(country),
                discipline="Triathlon",
                distance=distance,
                elevationGain=None,
                description=f"Major triathlon event in {city}.",
                registrationUrl=reg_url,
                imageUrl=name.lower().replace(" ", "_"),
                price=None,
                currency=None,
                registrationStatus=normalize_registration_status("open"),
                gpxUrl=None,
                websiteUrl=reg_url,
                source="Triathlon/curated",
                isFallback=True,
            )
        )
    return events


TRIATHLON_PATTERN = re.compile(
    r"(triathlon|duathlon|aquathlon|ironman|70\.3|\btri\b|triatlon)",
    flags=re.IGNORECASE,
)


def _is_probable_triathlon(event: RaceEvent) -> bool:
    haystack = f"{event.name} {event.registrationUrl} {event.websiteUrl or ''}"
    return bool(TRIATHLON_PATTERN.search(haystack))


def fetch_triathlon_events(max_results: int = 50) -> List[RaceEvent]:
    events = fetch_ahotu_triathlons(max_results=max_results)
    tri_events: List[RaceEvent] = []
    for event in events:
        if not _is_probable_triathlon(event):
            continue
        event.discipline = "Triathlon"
        if event.distance not in {"Half Ironman", "Ironman"}:
            event.distance = "Half Ironman" if "70.3" in event.name else "Ironman"
        event.source = "Ahotu/triathlon"
        tri_events.append(event)

    if len(tri_events) >= 8:
        return tri_events[:max_results]

    seen = {e.id for e in tri_events}
    for fallback_event in _curated_triathlon_fallback():
        if fallback_event.id in seen:
            continue
        tri_events.append(fallback_event)
        seen.add(fallback_event.id)
        if len(tri_events) >= max_results:
            break
    return tri_events


if __name__ == "__main__":
    sample = fetch_triathlon_events(max_results=20)
    for event in sample[:10]:
        print(f"- {event.date} | {event.name} | {event.city}, {event.country}")
