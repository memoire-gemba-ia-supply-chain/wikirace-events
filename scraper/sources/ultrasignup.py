"""
UltraSignup source using the public event service endpoint.
"""
from __future__ import annotations

from typing import List

import requests

from models import RaceEvent
from sources.common import (
    clean_text,
    infer_discipline,
    infer_distance,
    is_noise_event,
    is_reasonable_future_date,
    normalize_registration_status,
    parse_date_to_iso,
    sanitize_url,
)


EVENTS_ENDPOINT = "https://ultrasignup.com/service/events.svc/closestevents"


def fetch_ultrasignup_events(max_results: int = 120) -> List[RaceEvent]:
    """
    Fetch events through UltraSignup's JSON endpoint.
    """
    params = {
        "virtual": 0,
        "open": 1,
        "past": 0,
        # Geographic center of the US + large radius to cover most races.
        "lat": 39.5,
        "lng": -98.35,
        "mi": 5000,
        "mo": 24,
    }

    print("  UltraSignup: fetching JSON endpoint...")
    try:
        response = requests.get(
            EVENTS_ENDPOINT,
            params=params,
            timeout=35,
            headers={"User-Agent": "WikiRaceBot/1.0 (+github actions)"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"  UltraSignup failed: {exc}")
        return []

    events: List[RaceEvent] = []
    seen_ids: set[str] = set()

    for raw in payload:
        if len(events) >= max_results:
            break

        name = clean_text(raw.get("EventName"))
        if not name:
            continue

        date_iso = parse_date_to_iso(raw.get("EventDate"))
        if not is_reasonable_future_date(date_iso, max_months=24):
            continue

        city = clean_text(raw.get("City"))
        state = clean_text(raw.get("State"))
        if city.lower() in {"", "virtual"}:
            continue
        if bool(raw.get("VirtualEvent", False)):
            continue

        distances = clean_text(raw.get("Distances"))
        if is_noise_event(name=name, distances=distances, description=""):
            continue

        distance = infer_distance(name=name, distances=distances, discipline_hint="trail")
        discipline = infer_discipline(name=name, discipline_hint="trail", distance=distance)

        event_id = raw.get("EventId")
        reg_url = sanitize_url(raw.get("EventWebsite"))
        if not reg_url and event_id:
            reg_url = f"https://ultrasignup.com/register.aspx?eid={event_id}"
        reg_url = sanitize_url(reg_url)
        if not reg_url:
            continue

        location_hint = city if not state else f"{city}-{state}"
        uid = RaceEvent.generate_id(name=name, date_str=date_iso, location_hint=location_hint)
        if uid in seen_ids:
            continue
        seen_ids.add(uid)

        description = f"{distances} in {city}, {state}".strip(", ")
        if not description:
            description = f"Trail event in {city}, {state}".strip(", ")

        event = RaceEvent(
            id=uid,
            name=name,
            date=date_iso,
            city=f"{city}, {state}" if state else city,
            country="United States",
            countryCode="US",
            discipline=discipline,
            distance=distance,
            elevationGain=None,
            description=description[:240],
            registrationUrl=reg_url,
            imageUrl=name.lower().replace(" ", "_"),
            price=None,
            currency=None,
            registrationStatus=normalize_registration_status(
                "closed" if bool(raw.get("Cancelled", False)) else "open"
            ),
            gpxUrl=None,
            websiteUrl=sanitize_url(raw.get("EventWebsite")),
            source="UltraSignup",
            isFallback=False,
        )
        events.append(event)

    print(f"  UltraSignup: kept {len(events)} events")
    return events


if __name__ == "__main__":
    rows = fetch_ultrasignup_events(max_results=20)
    for item in rows[:10]:
        print(f"- {item.date} | {item.name} | {item.city}")
