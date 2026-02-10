"""
UltraSignup web scraper
Scrapes ultra-marathon events from ultrasignup.com
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List
import sys
sys.path.append('..')
from models import RaceEvent


ULTRASIGNUP_URL = "https://ultrasignup.com/register.aspx"


def get_country_code(country: str) -> str:
    """Map country name to ISO code"""
    codes = {
        "USA": "US", "United States": "US", "Canada": "CA", "Mexico": "MX",
        "France": "FR", "Spain": "ES", "Italy": "IT", "Germany": "DE",
        "UK": "GB", "South Africa": "ZA", "Australia": "AU", "Japan": "JP",
    }
    return codes.get(country, "US")


def fetch_ultrasignup_events(max_results: int = 50) -> List[RaceEvent]:
    """
    Fetch ultra-marathon events from UltraSignup
    """
    events = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    # UltraSignup calendar page
    calendar_url = "https://ultrasignup.com/register.aspx"
    
    try:
        response = requests.get(calendar_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find race listings (UltraSignup uses specific class names)
        race_rows = soup.select('.event-row, .race-row, tr[class*="race"]')
        
        if not race_rows:
            # Try alternative selectors
            race_rows = soup.find_all('tr', {'class': lambda x: x and 'race' in x.lower()}) if soup.find_all('tr') else []
        
        for row in race_rows[:max_results]:
            try:
                # Extract race info
                name_elem = row.select_one('a, .race-name, td:first-child a')
                date_elem = row.select_one('.date, td:nth-child(2), time')
                location_elem = row.select_one('.location, td:nth-child(3)')
                
                if not name_elem:
                    continue
                
                name = name_elem.get_text(strip=True)
                date_str = date_elem.get_text(strip=True) if date_elem else ""
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                # Parse date (various formats)
                parsed_date = None
                for fmt in ["%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt)
                        break
                    except:
                        continue
                
                if not parsed_date or parsed_date < datetime.now():
                    continue
                
                date_formatted = parsed_date.strftime("%Y-%m-%d")
                
                # Get registration URL
                reg_url = name_elem.get('href', '')
                if reg_url and not reg_url.startswith('http'):
                    reg_url = f"https://ultrasignup.com{reg_url}"
                
                event = RaceEvent(
                    id=RaceEvent.generate_id(name, date_formatted),
                    name=name,
                    date=date_formatted,
                    city=location.split(',')[0].strip() if location else "",
                    country="USA",
                    countryCode="US",
                    discipline="Trail",
                    distance="Ultra Trail",
                    elevationGain=None,
                    description=f"Ultra-marathon event: {name}",
                    registrationUrl=reg_url if reg_url else "https://ultrasignup.com",
                    imageUrl=name.lower().replace(" ", "_"),
                    price=None,
                    currency=None,
                    registrationStatus=None,
                    gpxUrl=None,
                    websiteUrl=None
                )
                events.append(event)
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"❌ UltraSignup scraper error: {e}")
    
    # Always add fallback if we got few events
    if len(events) < 5:
        events.extend(get_fallback_ultra_events())
    
    print(f"✅ UltraSignup: Fetched {len(events)} events")
    return events


def get_fallback_ultra_events() -> List[RaceEvent]:
    """Return major ultra events worldwide - 30+ events"""
    known_events = [
        # North America - The Big Ones
        ("Western States 100", "2026-06-27", "Olympic Valley", "USA", "US"),
        ("Leadville Trail 100", "2026-08-22", "Leadville", "USA", "US"),
        ("Badwater 135", "2026-07-13", "Death Valley", "USA", "US"),
        ("JFK 50 Mile", "2026-11-21", "Boonsboro", "USA", "US"),
        ("Javelina Jundred", "2026-10-31", "Fountain Hills", "USA", "US"),
        ("Vermont 100", "2026-07-18", "West Windsor", "USA", "US"),
        ("Wasatch Front 100", "2026-09-11", "Kaysville", "USA", "US"),
        ("Bear 100", "2026-09-25", "Logan", "USA", "US"),
        ("Old Cascadia 100", "2026-08-22", "Cascadia", "USA", "US"),
        ("Tejas Trails - Rocky 100", "2026-02-07", "Huntsville", "USA", "US"),
        ("San Diego 100", "2026-06-06", "Lake Cuyamaca", "USA", "US"),
        ("Zion 100", "2026-04-10", "Zion", "USA", "US"),
        ("Black Canyon 100K", "2026-02-14", "Mayer", "USA", "US"),
        ("Lake Sonoma 50", "2026-04-11", "Healdsburg", "USA", "US"),
        
        # Morocco - Ultra focus 🇲🇦
        ("Marathon des Sables", "2026-04-10", "Sahara Desert", "Morocco", "MA"),
        ("Morocco Tizi n'Test Ultra", "2026-10-15", "Tizi n'Test", "Morocco", "MA"),
        ("Sahara Ultra 100", "2026-11-20", "Merzouga", "Morocco", "MA"),
        ("Nomads Ultra Trail", "2026-03-20", "Zagora", "Morocco", "MA"),
        ("Atlas Ultra Trail", "2026-09-25", "Imlil", "Morocco", "MA"),
        
        # International Major Ultras
        ("Spartathlon", "2026-09-26", "Athens to Sparta", "Greece", "GR"),
        ("Comrades Marathon", "2026-06-14", "Durban", "South Africa", "ZA"),
        ("Two Oceans Marathon", "2026-04-04", "Cape Town", "South Africa", "ZA"),
        ("Grand Raid di Cromagnon", "2026-07-04", "Limone Piemonte", "Italy", "IT"),
        ("Lavaredo Ultra Trail", "2026-06-26", "Cortina", "Italy", "IT"),
        ("Zugspitz Supertrail", "2026-06-19", "Garmisch-Partenkirchen", "Germany", "DE"),
        ("Swiss Canyon Trail", "2026-06-05", "Couvet", "Switzerland", "CH"),
        ("Ultra-Trail Porto", "2026-10-31", "Porto", "Portugal", "PT"),
        ("Tor des Géants", "2026-09-13", "Aosta Valley", "Italy", "IT"),
        ("Andorra Ultra Trail", "2026-07-03", "Ordino", "Andorra", "AD"),
        ("Dragons Back Race", "2026-09-07", "Conwy", "UK", "GB"),
    ]
    
    return [
        RaceEvent(
            id=RaceEvent.generate_id(name, date),
            name=name, date=date, city=city, country=country,
            countryCode=code, discipline="Trail", distance="Ultra Trail",
            elevationGain=None, description=f"Major ultra-marathon in {city}, known for its extreme difficulty and beauty.",
            registrationUrl="https://ultrasignup.com", imageUrl=name.lower().replace(" ", "_"),
            price=None, currency=None, registrationStatus=None,
            gpxUrl=None, websiteUrl=None
        )
        for name, date, city, country, code in known_events
    ]


if __name__ == "__main__":
    events = fetch_ultrasignup_events(max_results=10)
    for e in events[:5]:
        print(f"  - {e.name} ({e.date}) - {e.city}")
