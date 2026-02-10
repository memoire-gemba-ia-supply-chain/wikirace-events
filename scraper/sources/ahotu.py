"""
Ahotu Calendars scraper
Scrapes running and trail events from ahotu.com - a comprehensive race calendar
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List
import re
import sys
sys.path.append('..')
from models import RaceEvent


AHOTU_BASE_URL = "https://www.ahotu.com"


# Comprehensive country code mapping
COUNTRY_CODES = {
    "france": "FR", "spain": "ES", "italy": "IT", "germany": "DE",
    "switzerland": "CH", "austria": "AT", "united kingdom": "GB", "uk": "GB",
    "usa": "US", "united states": "US", "morocco": "MA", "japan": "JP",
    "china": "CN", "south africa": "ZA", "australia": "AU", "portugal": "PT",
    "netherlands": "NL", "belgium": "BE", "nepal": "NP", "mexico": "MX",
    "canada": "CA", "brazil": "BR", "argentina": "AR", "chile": "CL",
    "south korea": "KR", "india": "IN", "thailand": "TH", "malaysia": "MY",
    "singapore": "SG", "indonesia": "ID", "philippines": "PH", "vietnam": "VN",
    "greece": "GR", "turkey": "TR", "ireland": "IE", "poland": "PL",
    "czech republic": "CZ", "czechia": "CZ", "hungary": "HU", "romania": "RO",
    "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
    "new zealand": "NZ", "kenya": "KE", "ethiopia": "ET", "nigeria": "NG",
    "egypt": "EG", "uae": "AE", "dubai": "AE", "saudi arabia": "SA",
    "israel": "IL", "russia": "RU", "ukraine": "UA", "croatia": "HR",
    "slovenia": "SI", "slovakia": "SK", "serbia": "RS", "bulgaria": "BG",
    "peru": "PE", "colombia": "CO", "ecuador": "EC", "bolivia": "BO",
    "uruguay": "UY", "paraguay": "PY", "venezuela": "VE", "costa rica": "CR",
    "panama": "PA", "guatemala": "GT", "puerto rico": "PR", "cuba": "CU",
    "andorra": "AD", "monaco": "MC", "luxembourg": "LU", "liechtenstein": "LI",
    "iceland": "IS", "malta": "MT", "cyprus": "CY", "taiwan": "TW",
    "hong kong": "HK", "macau": "MO",
}


def get_country_code(country: str) -> str:
    """Map country name to ISO code"""
    if not country:
        return "XX"
    return COUNTRY_CODES.get(country.lower().strip(), "XX")


def parse_ahotu_date(date_str: str) -> str:
    """Parse Ahotu date format like '15 Mar, 2026 (Sun)' to YYYY-MM-DD"""
    if not date_str:
        return None
    
    # Clean the string
    date_str = re.sub(r'\([^)]*\)', '', date_str).strip()  # Remove day in parentheses
    date_str = re.sub(r'\d+-', '', date_str).strip()  # Remove multi-day ranges like "07-08"
    
    formats = [
        "%d %b, %Y",
        "%d %B, %Y", 
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    return None


def determine_distance(name: str, url: str = "") -> str:
    """Determine distance category from event name"""
    name_lower = name.lower()
    
    if "ultra" in name_lower or "100" in name_lower or "50" in name_lower:
        return "Ultra Trail"
    if "trail" in name_lower:
        return "Trail"
    if "half" in name_lower or "semi" in name_lower or "21k" in name_lower:
        return "Half Marathon"
    if "marathon" in name_lower or "42k" in name_lower:
        return "Marathon"
    if "10k" in name_lower or "10km" in name_lower:
        return "10km"
    if "5k" in name_lower or "5km" in name_lower:
        return "5km"
    
    return "Marathon"


def fetch_ahotu_events(max_results: int = 100, discipline: str = "running") -> List[RaceEvent]:
    """
    Fetch events from Ahotu calendar
    
    Args:
        max_results: Maximum number of events to fetch
        discipline: "running", "trail-running", or "triathlon"
    """
    events = []
    today = datetime.now()
    
    # Map discipline to URL
    discipline_urls = {
        "running": "/calendar/running-ede0cd",
        "trail-running": "/calendar/trail-running",
        "marathon": "/calendar/marathon",
    }
    
    url_path = discipline_urls.get(discipline, "/calendar/running-ede0cd")
    url = f"{AHOTU_BASE_URL}{url_path}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    print(f"  📡 Fetching from Ahotu ({discipline})...")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find event links - Ahotu uses /event/ URLs
        event_links = soup.find_all('a', href=lambda x: x and '/event/' in str(x))
        
        seen_urls = set()
        
        for link in event_links:
            if len(events) >= max_results:
                break
            
            try:
                href = link.get('href', '')
                
                # Skip duplicates
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                # Get text content
                text = link.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                
                # Parse the combined text (format: "RatingMapEvent NameLocation Date")
                # Extract date pattern
                date_match = re.search(r'(\d{1,2}\s+\w+,?\s+\d{4})', text)
                if not date_match:
                    continue
                
                date_str = date_match.group(1)
                parsed_date = parse_ahotu_date(date_str)
                
                if not parsed_date:
                    continue
                
                # Skip past events
                try:
                    event_date = datetime.strptime(parsed_date, "%Y-%m-%d")
                    if event_date < today:
                        continue
                except:
                    continue
                
                # Extract event name (before location/date)
                # Pattern: RatingMap{EventName}{Location}{Date}
                name_match = re.search(r'(?:Map)?([A-Z][^0-9]+?)(?:[A-Z][a-z]+,\s*[A-Z])', text)
                if name_match:
                    name = name_match.group(1).strip()
                else:
                    # Fallback: take text before the date
                    name = text.split(date_str)[0]
                    # Clean up common prefixes
                    name = re.sub(r'^[\d.]+Map', '', name)
                    name = re.sub(r'^Up to \d+% off', '', name)
                    name = name.strip()
                
                if not name or len(name) < 3:
                    continue
                
                # Extract location
                location_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
                city = ""
                country = ""
                if location_match:
                    city = location_match.group(1)
                    country = location_match.group(2)
                
                # Build full URL
                full_url = href if href.startswith('http') else f"{AHOTU_BASE_URL}{href}"
                
                # Determine discipline type
                disc_type = "Trail" if "trail" in discipline else "Running"
                
                event = RaceEvent(
                    id=RaceEvent.generate_id(name, parsed_date),
                    name=name,
                    date=parsed_date,
                    city=city,
                    country=country,
                    countryCode=get_country_code(country),
                    discipline=disc_type,
                    distance=determine_distance(name, full_url),
                    elevationGain=None,
                    description=f"{name} - {city}, {country}",
                    registrationUrl=full_url,
                    imageUrl=name.lower().replace(" ", "_"),
                    price=None,
                    currency=None,
                    registrationStatus=None,
                    gpxUrl=None,
                    websiteUrl=full_url
                )
                events.append(event)
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"  ❌ Ahotu scraper error: {e}")
    
    print(f"  ✅ Ahotu ({discipline}): Fetched {len(events)} events")
    return events


def fetch_all_ahotu_events(max_per_discipline: int = 50) -> List[RaceEvent]:
    """Fetch events from multiple Ahotu disciplines"""
    all_events = []
    
    for discipline in ["running", "trail-running", "marathon"]:
        events = fetch_ahotu_events(max_results=max_per_discipline, discipline=discipline)
        all_events.extend(events)
    
    return all_events


if __name__ == "__main__":
    events = fetch_ahotu_events(max_results=20, discipline="marathon")
    print(f"\nTotal events: {len(events)}")
    for e in events[:10]:
        print(f"  - {e.name} ({e.date}) - {e.city}, {e.country}")
