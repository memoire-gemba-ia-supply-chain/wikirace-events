#!/usr/bin/env python3
"""
Quality gates for generated events.json.
Fails CI when data quality drops below thresholds.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sources.common import is_generic_url


def _parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def validate(
    events_path: Path,
    min_events: int,
    min_disciplines: int,
    min_triathlon_events: int,
    max_fallback_ratio: float,
    max_generic_url_ratio: float,
    min_future_horizon_days: int,
    min_contributing_sources: int,
) -> tuple[bool, dict]:
    data = json.loads(events_path.read_text(encoding="utf-8"))
    events = data.get("events", [])

    total = len(events)
    ids = [event.get("id") for event in events]
    duplicate_ids = len(ids) - len(set(ids))

    invalid_dates = 0
    parsed_dates = []
    for event in events:
        parsed = _parse_date(event.get("date", ""))
        if parsed is None:
            invalid_dates += 1
        else:
            parsed_dates.append(parsed)

    generic_urls = sum(1 for event in events if is_generic_url(event.get("registrationUrl")))
    fallback_events = sum(1 for event in events if bool(event.get("isFallback")))
    triathlon_count = sum(1 for event in events if event.get("discipline") == "Triathlon")
    disciplines = Counter(event.get("discipline", "Unknown") for event in events)
    sources = Counter(event.get("source", "unknown") for event in events)
    contributing_sources = sum(1 for _, count in sources.items() if count >= 2)

    max_date = max(parsed_dates) if parsed_dates else None
    min_required_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=min_future_horizon_days)

    generic_ratio = (generic_urls / total) if total else 1.0
    fallback_ratio = (fallback_events / total) if total else 1.0

    checks = {
        "min_events": total >= min_events,
        "duplicate_ids": duplicate_ids == 0,
        "invalid_dates": invalid_dates == 0,
        "generic_url_ratio": generic_ratio <= max_generic_url_ratio,
        "fallback_ratio": fallback_ratio <= max_fallback_ratio,
        "min_disciplines": len(disciplines.keys()) >= min_disciplines,
        "min_triathlon_events": triathlon_count >= min_triathlon_events,
        "future_horizon": bool(max_date and max_date >= min_required_date),
        "source_diversity": contributing_sources >= min_contributing_sources,
    }

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "metrics": {
            "totalEvents": total,
            "duplicateIds": duplicate_ids,
            "invalidDates": invalid_dates,
            "genericUrlCount": generic_urls,
            "genericUrlRatio": round(generic_ratio, 4),
            "fallbackEvents": fallback_events,
            "fallbackRatio": round(fallback_ratio, 4),
            "triathlonEvents": triathlon_count,
            "disciplines": dict(disciplines),
            "sourceCounts": dict(sources),
            "maxDate": max_date.strftime("%Y-%m-%d") if max_date else None,
            "minRequiredDate": min_required_date.strftime("%Y-%m-%d"),
            "contributingSources": contributing_sources,
        },
    }

    ok = all(checks.values())
    return ok, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated events.json quality.")
    parser.add_argument(
        "--events",
        default=str(Path(__file__).parent.parent / "events.json"),
        help="Path to events.json",
    )
    parser.add_argument("--min-events", type=int, default=80)
    parser.add_argument("--min-disciplines", type=int, default=3)
    parser.add_argument("--min-triathlon-events", type=int, default=5)
    parser.add_argument("--max-fallback-ratio", type=float, default=0.35)
    parser.add_argument("--max-generic-url-ratio", type=float, default=0.08)
    parser.add_argument("--min-future-horizon-days", type=int, default=120)
    parser.add_argument("--min-contributing-sources", type=int, default=2)
    parser.add_argument(
        "--report",
        default=str(Path(__file__).parent / "quality_report.json"),
        help="Path to output validation report.",
    )
    args = parser.parse_args()

    events_path = Path(args.events)
    if not events_path.exists():
        print(f"events file not found: {events_path}")
        return 1

    ok, report = validate(
        events_path=events_path,
        min_events=args.min_events,
        min_disciplines=args.min_disciplines,
        min_triathlon_events=args.min_triathlon_events,
        max_fallback_ratio=args.max_fallback_ratio,
        max_generic_url_ratio=args.max_generic_url_ratio,
        min_future_horizon_days=args.min_future_horizon_days,
        min_contributing_sources=args.min_contributing_sources,
    )

    report_path = Path(args.report)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report["metrics"], indent=2, ensure_ascii=False))
    if not ok:
        print("Quality checks failed:")
        for name, passed in report["checks"].items():
            if not passed:
                print(f"- {name}")
        return 1

    print("All quality checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
