"""
RunSignup API client.
Primary source for running events in the US.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import requests

from models import RaceEvent
from sources.common import (
    clean_text,
    infer_discipline,
    infer_distance,
    is_noise_event,
    is_reasonable_future_date,
    map_country_code,
    normalize_registration_status,
    parse_date_to_iso,
    sanitize_url,
    strip_html,
)


RUNSIGNUP_API = "https://runsignup.com/Rest/races"


def _is_virtual(city: str, state: str) -> bool:
    token = clean_text(f"{city} {state}").lower()
    if not token:
        return True
    return any(word in token for word in ("virtual", "online", "anywhere"))


def fetch_runsignup_events(max_results: int = 220) -> List[RaceEvent]:
    """
    Fetch events from RunSignup and keep only race-relevant entries.
    """
    events: List[RaceEvent] = []
    today = datetime.utcnow()
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=540)).strftime("%Y-%m-%d")

    page = 1
    max_pages = 8
    per_page = 100

    print(f"  RunSignup: fetching up to {max_pages} pages...")

    while page <= max_pages and len(events) < max_results:
        params = {
            "format": "json",
            "start_date": start_date,
            "end_date": end_date,
            "distance_units": "K",
            "results_per_page": per_page,
            "page": page,
            "sort": "date",
            "only_partner_races": "F",
            "include_waiver": "F",
            "include_event_days": "T",
        }

        try:
            response = requests.get(
                RUNSIGNUP_API,
                params=params,
                timeout=30,
                headers={"User-Agent": "WikiRaceBot/1.0 (+github actions)"},
            )
            response.raise_for_status()
            races = response.json().get("races", [])
        except Exception as exc:
            print(f"  RunSignup: page {page} failed: {exc}")
            break

        if not races:
            break

        for race_data in races:
            if len(events) >= max_results:
                break

            race = race_data.get("race", {})
            name = clean_text(race.get("name"))
            if not name:
                continue

            next_date = parse_date_to_iso(race.get("next_date"))
            if not is_reasonable_future_date(next_date):
                continue

            address = race.get("address", {})
            city = clean_text(address.get("city"))
            state = clean_text(address.get("state"))
            country = clean_text(address.get("country")) or "United States"
            if _is_virtual(city, state):
                continue

            events_list = race.get("events", []) or []
            distances_blob = clean_text(
                " ".join(
                    clean_text((e.get("event", {}) or {}).get("name"))
                    + " "
                    + clean_text(str((e.get("event", {}) or {}).get("distance", "")))
                    for e in events_list
                )
            )

            description = strip_html(race.get("description"))
            if not description:
                description = f"Running event in {city}, {state}" if state else f"Running event in {city}"

            if is_noise_event(name=name, distances=distances_blob, description=description):
                continue

            distance = infer_distance(name, distances_blob, discipline_hint="running")
            discipline = infer_discipline(name, discipline_hint="running", distance=distance)
            registration_url = sanitize_url(race.get("url")) or sanitize_url(f"https://runsignup.com/Race/{race.get('race_id', '')}")
            if not registration_url:
                continue

            website_url = sanitize_url(race.get("external_race_url"))
            status = normalize_registration_status(
                "open" if race.get("is_registration_open") == "T" else "closed"
            )

            location_hint = city if not state else f"{city}-{state}"

            event = RaceEvent(
                id=RaceEvent.generate_id(name=name, date_str=next_date, location_hint=location_hint),
                name=name,
                date=next_date,
                city=f"{city}, {state}" if state else city,
                country=country,
                countryCode=map_country_code(country, default="US"),
                discipline=discipline,
                distance=distance,
                elevationGain=None,
                description=description[:240],
                registrationUrl=registration_url,
                imageUrl=name.lower().replace(" ", "_"),
                price=None,
                currency=None,
                registrationStatus=status,
                gpxUrl=None,
                websiteUrl=website_url,
                source="RunSignup",
                isFallback=False,
            )
            events.append(event)

        page += 1

    print(f"  RunSignup: kept {len(events)} events")
    return events


if __name__ == "__main__":
    sample = fetch_runsignup_events(max_results=20)
    for event in sample[:10]:
        print(f"- {event.date} | {event.name} | {event.city}")
