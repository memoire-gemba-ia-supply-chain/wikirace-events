"""
Shared scraping utilities.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse


COUNTRY_CODES = {
    "united states": "US",
    "usa": "US",
    "us": "US",
    "canada": "CA",
    "mexico": "MX",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
    "germany": "DE",
    "switzerland": "CH",
    "austria": "AT",
    "united kingdom": "GB",
    "uk": "GB",
    "morocco": "MA",
    "japan": "JP",
    "china": "CN",
    "south africa": "ZA",
    "australia": "AU",
    "portugal": "PT",
    "netherlands": "NL",
    "belgium": "BE",
    "new zealand": "NZ",
    "denmark": "DK",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "ireland": "IE",
    "greece": "GR",
    "turkey": "TR",
    "thailand": "TH",
    "democratic republic of the congo": "CD",
    "congo": "CG",
    "argentina": "AR",
    "brazil": "BR",
    "peru": "PE",
    "chile": "CL",
    "india": "IN",
    "south korea": "KR",
    "singapore": "SG",
    "united arab emirates": "AE",
    "uae": "AE",
}


NOISE_PATTERN = re.compile(
    r"\b("
    r"membership|volunteer|volunteers|training|camp|clinic|coaching|"
    r"fundraiser|fundraising|charity gala|party|festival volunteers|"
    r"reservation|reservations|lottery|raffle|summit|expo only|"
    r"sponsor|team membership|subscription|grand prix series"
    r")\b",
    flags=re.IGNORECASE,
)


FUTURE_MONTHS_DEFAULT = 18


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return clean_text(re.sub(r"<[^>]+>", " ", text))


def map_country_code(country: str | None, default: str = "XX") -> str:
    country = clean_text(country).lower()
    return COUNTRY_CODES.get(country, default)


def parse_date_to_iso(date_str: str | None) -> Optional[str]:
    """
    Parse multiple human date formats to YYYY-MM-DD.
    """
    raw = clean_text(date_str)
    if not raw:
        return None

    # Handle ranges like "07-08 Nov, 2026 (Sat - Sun)" -> "07 Nov, 2026"
    raw = re.sub(r"\([^)]*\)", "", raw).strip()
    raw = re.sub(r"^(\d{1,2})-\d{1,2}\s+", r"\1 ", raw)
    raw = raw.replace(",", ", ")
    raw = clean_text(raw)

    formats = (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d %b, %Y",
        "%d %B, %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def is_reasonable_future_date(date_iso: str | None, max_months: int = FUTURE_MONTHS_DEFAULT) -> bool:
    if not date_iso:
        return False
    try:
        event_date = datetime.strptime(date_iso, "%Y-%m-%d")
    except ValueError:
        return False

    today = datetime.utcnow().date()
    lower = today - timedelta(days=1)
    upper = today + timedelta(days=max_months * 31)
    return lower <= event_date.date() <= upper


def is_noise_event(name: str, distances: str = "", description: str = "") -> bool:
    haystack = clean_text(f"{name} {distances} {description}").lower()
    if not haystack:
        return True
    return bool(NOISE_PATTERN.search(haystack))


def infer_distance(name: str, distances: str = "", discipline_hint: str = "") -> str:
    text = clean_text(f"{name} {distances} {discipline_hint}").lower()

    if "70.3" in text or "half ironman" in text:
        return "Half Ironman"
    if "5k" in text or "5 km" in text:
        return "5km"
    if "10k" in text or "10 km" in text:
        return "10km"
    if "half marathon" in text or re.search(r"\b21k\b", text):
        return "Half Marathon"
    if "marathon" in text:
        return "Marathon"
    if (
        "ultra" in text
        or "50k" in text
        or "100k" in text
        or "50 mile" in text
        or "100 mile" in text
        or "trail" in text
    ):
        return "Ultra Trail"
    if "ironman" in text or "triathlon" in text or "duathlon" in text:
        return "Ironman"
    if "running" in text:
        return "10km"
    return "Marathon"


def infer_discipline(name: str, discipline_hint: str = "", distance: str = "") -> str:
    text = clean_text(f"{name} {discipline_hint} {distance}").lower()
    if any(token in text for token in ("triathlon", "ironman", "duathlon")):
        return "Triathlon"
    if any(token in text for token in ("trail", "ultra", "mountain")):
        return "Trail"
    return "Running"


def normalize_registration_status(status: str | None, *, cancelled: bool = False) -> Optional[str]:
    if cancelled:
        return "Closed"
    if not status:
        return None
    token = clean_text(status).lower()
    if any(k in token for k in ("open", "registration open", "active")):
        return "Open"
    if any(k in token for k in ("closed", "registration closed", "ended", "cancelled")):
        return "Closed"
    if "sold out" in token or "soldout" in token:
        return "Sold Out"
    return None


def sanitize_url(url: str | None) -> Optional[str]:
    value = clean_text(url)
    if not value:
        return None
    if value.startswith("//"):
        value = f"https:{value}"
    if not value.startswith("http://") and not value.startswith("https://"):
        return None
    return value


def is_generic_url(url: str | None) -> bool:
    value = sanitize_url(url)
    if not value:
        return True
    parsed = urlparse(value)
    domain = parsed.netloc.lower()
    path = parsed.path.strip("/")
    query = parsed.query.lower()

    if "google.com" in domain and "search" in path:
        return True
    if domain in {"ultrasignup.com", "www.ultrasignup.com"} and path == "register.aspx":
        # register.aspx?eid=123 is an event-specific landing page and should be kept.
        return "eid=" not in query
    if domain in {"itra.run", "www.itra.run", "ultrasignup.com", "www.ultrasignup.com"} and path in {""}:
        return True
    if domain in {"example.com", "www.example.com"}:
        return True
    if not path and not query:
        return True
    return False


def parse_price(raw_price: str | None) -> tuple[Optional[float], Optional[str]]:
    text = clean_text(raw_price)
    if not text:
        return (None, None)

    currency = None
    upper = text.upper()
    if " EUR" in upper or "€" in text:
        currency = "EUR"
    elif " USD" in upper or "$" in text:
        currency = "USD"
    elif " GBP" in upper or "£" in text:
        currency = "GBP"
    elif " MAD" in upper:
        currency = "MAD"

    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return (None, currency)

    value = float(match.group(1).replace(",", "."))
    return (value, currency)
