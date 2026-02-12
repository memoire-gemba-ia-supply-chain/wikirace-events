"""
Ahotu calendar scraper.
Used as a global source for running, trail, and triathlon events.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup

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
    parse_price,
    sanitize_url,
)


BASE_URL = "https://www.ahotu.com"
CALENDAR_URLS = {
    "running": f"{BASE_URL}/calendar/running",
    "marathon": f"{BASE_URL}/calendar/running/marathon",
    "trail-running": f"{BASE_URL}/calendar/trail-running",
    "triathlon": f"{BASE_URL}/calendar/triathlon",
}


def _extract_card_details(anchor) -> tuple[str, str, str, str]:
    """
    Returns (name, location, date_text, discipline_text).
    """
    name = clean_text(anchor.select_one("h3").get_text()) if anchor.select_one("h3") else ""
    row_texts = [
        clean_text(span.get_text())
        for span in anchor.select("span.flex-grow")
        if clean_text(span.get_text())
    ]

    location = ""
    date_text = ""
    discipline = ""

    for row in row_texts:
        if not location and "," in row and not re.search(r"\d", row):
            location = row
        if not date_text and re.search(r"\b20\d{2}\b", row):
            date_text = row
        if not discipline and row.lower() in {"running", "trail running", "triathlon"}:
            discipline = row

    return (name, location, date_text, discipline)


def _extract_price(anchor) -> tuple[float | None, str | None]:
    price_text = ""
    for tag in anchor.select("span"):
        text = clean_text(tag.get_text())
        if text.lower().startswith("from "):
            price_text = text
            break
    return parse_price(price_text)


def _to_country_and_city(location: str) -> tuple[str, str]:
    if not location:
        return ("", "")
    parts = [clean_text(p) for p in location.split(",") if clean_text(p)]
    if len(parts) == 1:
        return ("", parts[0])
    city = ", ".join(parts[:-1])
    country = parts[-1]
    return (country, city)


def fetch_ahotu_events(category: str, max_results: int = 80) -> List[RaceEvent]:
    url = CALENDAR_URLS.get(category)
    if not url:
        raise ValueError(f"Unknown Ahotu category: {category}")

    print(f"  Ahotu[{category}]: fetching {url}")
    try:
        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "WikiRaceBot/1.0 (+github actions)"},
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"  Ahotu[{category}] failed: {exc}")
        return []

    soup = BeautifulSoup(response.text, "lxml")
    anchors = soup.select('a.ah-link[href*="/event/"]')

    events: List[RaceEvent] = []
    seen_links: set[str] = set()
    seen_ids: set[str] = set()

    for anchor in anchors:
        href = clean_text(anchor.get("href"))
        if not href:
            continue
        link = f"{BASE_URL}{href}" if href.startswith("/") else href
        link = sanitize_url(link)
        if not link or link in seen_links:
            continue
        seen_links.add(link)

        name, location, date_text, discipline_text = _extract_card_details(anchor)
        if not name:
            continue

        event_date = parse_date_to_iso(date_text)
        if not is_reasonable_future_date(event_date):
            continue

        country, city = _to_country_and_city(location)
        if is_noise_event(name=name, distances="", description=discipline_text):
            continue

        distance = infer_distance(name=name, distances=discipline_text, discipline_hint=category)
        discipline = infer_discipline(name=name, discipline_hint=discipline_text or category, distance=distance)
        price, currency = _extract_price(anchor)

        event_id = RaceEvent.generate_id(name=name, date_str=event_date, location_hint=location)
        if event_id in seen_ids:
            continue
        seen_ids.add(event_id)

        description = f"{discipline} event in {city}, {country}".strip(", ")

        event = RaceEvent(
            id=event_id,
            name=name,
            date=event_date,
            city=city,
            country=country,
            countryCode=map_country_code(country),
            discipline=discipline,
            distance=distance,
            elevationGain=None,
            description=description,
            registrationUrl=link,
            imageUrl=name.lower().replace(" ", "_"),
            price=price,
            currency=currency,
            registrationStatus=normalize_registration_status("open"),
            gpxUrl=None,
            websiteUrl=link,
            source=f"Ahotu/{category}",
            isFallback=False,
        )
        events.append(event)

        if len(events) >= max_results:
            break

    events.sort(key=lambda e: e.date)
    print(f"  Ahotu[{category}]: kept {len(events)} events")
    return events


def fetch_ahotu_marathons(max_results: int = 80) -> List[RaceEvent]:
    return fetch_ahotu_events(category="marathon", max_results=max_results)


def fetch_ahotu_running(max_results: int = 80) -> List[RaceEvent]:
    return fetch_ahotu_events(category="running", max_results=max_results)


def fetch_ahotu_trails(max_results: int = 80) -> List[RaceEvent]:
    return fetch_ahotu_events(category="trail-running", max_results=max_results)


def fetch_ahotu_triathlons(max_results: int = 60) -> List[RaceEvent]:
    return fetch_ahotu_events(category="triathlon", max_results=max_results)


if __name__ == "__main__":
    start = datetime.utcnow()
    for cat in ("marathon", "trail-running", "triathlon"):
        data = fetch_ahotu_events(category=cat, max_results=10)
        print(cat, len(data))
        for item in data[:3]:
            print(f"  - {item.date} | {item.name} | {item.city}, {item.country}")
    print("Elapsed:", datetime.utcnow() - start)
