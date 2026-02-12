#!/usr/bin/env python3
"""
WikiRace Event Scraper - cloud-first pipeline entrypoint.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List

# Local imports
sys.path.insert(0, str(Path(__file__).parent))

from models import RaceEvent
from sources.ahotu import fetch_ahotu_marathons, fetch_ahotu_running, fetch_ahotu_trails
from sources.common import is_generic_url, is_noise_event, is_reasonable_future_date
from sources.runsignup import fetch_runsignup_events
from sources.triathlon import fetch_triathlon_events
from sources.ultrasignup import fetch_ultrasignup_events


GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "memoire-gemba-ia-supply-chain")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "wikirace-events")
PUBLIC_JSON_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/events.json"


@dataclass
class SourceResult:
    name: str
    events: List[RaceEvent]
    ok: bool
    error: str | None = None


def _source_runner(name: str, fn: Callable[[], List[RaceEvent]]) -> SourceResult:
    try:
        events = fn()
        return SourceResult(name=name, events=events, ok=True)
    except Exception as exc:
        return SourceResult(name=name, events=[], ok=False, error=str(exc))


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _event_score(event: RaceEvent) -> int:
    score = 0
    if event.registrationUrl and not is_generic_url(event.registrationUrl):
        score += 4
    if event.description and len(event.description) > 60:
        score += 1
    if event.registrationStatus:
        score += 1
    if event.price is not None:
        score += 1
    if event.websiteUrl:
        score += 1
    if not event.isFallback:
        score += 2
    return score


def _deduplicate(events: List[RaceEvent]) -> List[RaceEvent]:
    chosen: dict[tuple[str, str, str, str], RaceEvent] = {}
    for event in events:
        key = (_normalize_name(event.name), event.date, event.countryCode or "", event.discipline)
        current = chosen.get(key)
        if current is None or _event_score(event) > _event_score(current):
            chosen[key] = event
    return list(chosen.values())


def _final_filter(events: List[RaceEvent]) -> List[RaceEvent]:
    filtered: List[RaceEvent] = []
    for event in events:
        if not is_reasonable_future_date(event.date, max_months=24):
            continue
        if not event.registrationUrl or is_generic_url(event.registrationUrl):
            continue
        if is_noise_event(event.name, event.distance, event.description):
            continue
        filtered.append(event)
    filtered.sort(key=lambda e: e.date)
    return filtered


def _ensure_unique_ids(events: List[RaceEvent]) -> None:
    seen: dict[str, int] = {}
    for event in events:
        base = event.id
        if base not in seen:
            seen[base] = 1
            continue

        # Use discipline first to keep ids stable across runs.
        candidate = f"{base}-{event.discipline.lower()}"
        if candidate not in seen:
            event.id = candidate
            seen[candidate] = 1
            continue

        counter = seen[base] + 1
        while f"{base}-{counter}" in seen:
            counter += 1
        event.id = f"{base}-{counter}"
        seen[event.id] = 1
        seen[base] = counter


def _quality_snapshot(events: List[RaceEvent]) -> dict:
    discipline_counts = Counter(e.discipline for e in events)
    source_counts = Counter(e.source or "unknown" for e in events)
    country_counts = Counter(e.countryCode for e in events if e.countryCode)
    fallback_count = sum(1 for e in events if e.isFallback)

    return {
        "disciplines": dict(discipline_counts),
        "sources": dict(source_counts),
        "countriesTop10": dict(country_counts.most_common(10)),
        "fallbackEvents": fallback_count,
        "fallbackRatio": round(fallback_count / len(events), 4) if events else 1.0,
    }


def main() -> int:
    print("WikiRace Event Scraper")
    print("=" * 40)

    source_jobs: list[tuple[str, Callable[[], List[RaceEvent]]]] = [
        ("RunSignup", lambda: fetch_runsignup_events(max_results=240)),
        ("Ahotu/Running", lambda: fetch_ahotu_running(max_results=90)),
        ("Ahotu/Marathon", lambda: fetch_ahotu_marathons(max_results=90)),
        ("Ahotu/Trail", lambda: fetch_ahotu_trails(max_results=100)),
        ("UltraSignup", lambda: fetch_ultrasignup_events(max_results=120)),
        ("Triathlon", lambda: fetch_triathlon_events(max_results=60)),
    ]

    results: list[SourceResult] = []
    for name, fn in source_jobs:
        print(f"\nFetching {name}...")
        result = _source_runner(name, fn)
        results.append(result)
        if result.ok:
            print(f"  {name}: {len(result.events)} events")
        else:
            print(f"  {name}: FAILED - {result.error}")

    all_events = [event for result in results for event in result.events]
    print(f"\nRaw events: {len(all_events)}")

    deduped = _deduplicate(all_events)
    final_events = _final_filter(deduped)
    _ensure_unique_ids(final_events)
    quality = _quality_snapshot(final_events)

    print(f"Deduped events: {len(deduped)}")
    print(f"Final events: {len(final_events)}")

    source_stats = {
        result.name: {
            "ok": result.ok,
            "count": len(result.events),
            "error": result.error,
        }
        for result in results
    }

    now = datetime.now(timezone.utc).isoformat()
    output = {
        "lastUpdated": now,
        "totalEvents": len(final_events),
        "publicUrl": PUBLIC_JSON_URL,
        "sources": [job[0] for job in source_jobs],
        "sourceStats": source_stats,
        "quality": quality,
        "events": [event.to_dict() for event in final_events],
    }

    root_events = Path(__file__).parent.parent / "events.json"
    with open(root_events, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)

    summary = {
        "generatedAt": now,
        "totalEvents": len(final_events),
        "sourceStats": source_stats,
        "quality": quality,
    }
    summary_path = Path(__file__).parent / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    print(f"\nSaved: {root_events}")
    print(f"Summary: {summary_path}")
    print(f"Public URL: {PUBLIC_JSON_URL}")

    if len(final_events) == 0:
        print("No valid events generated.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
