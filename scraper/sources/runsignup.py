"""
RunSignup API client
Free API for US running events
"""
import requests
from datetime import datetime, timedelta
from typing import List
import sys
sys.path.append('..')
from models import RaceEvent


RUNSIGNUP_API = "https://runsignup.com/Rest/races"


def get_country_code(country: str) -> str:
    """Map country name to ISO code"""
    codes = {
        "United States": "US",
        "USA": "US",
        "Canada": "CA",
        "Mexico": "MX",
    }
    return codes.get(country, "US")


def map_distance(distance_str: str) -> str:
    """Map RunSignup distance to our format"""
    d = distance_str.lower()
    if "marathon" in d and "half" not in d:
        return "Marathon"
    if "half" in d:
        return "Half Marathon"
    if "10k" in d or "10 k" in d:
        return "10km"
    if "5k" in d or "5 k" in d:
        return "5km"
    if "ultra" in d or "50" in d or "100" in d:
        return "Ultra Trail"
    return "Marathon"  # Default


def parse_date(date_str: str) -> str:
    """Parse various date formats to YYYY-MM-DD"""
    if not date_str:
        return None
    
    # Try different formats
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    return None


def fetch_runsignup_events(max_results: int = 200) -> List[RaceEvent]:
    """
    Fetch running events from RunSignup API
    API docs: https://runsignup.com/API
    Parcourt plusieurs pages pour obtenir plus d'événements
    """
    events = []
    today = datetime.now()
    
    # Calculate date range (today + 18 months)
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=540)).strftime("%Y-%m-%d")
    
    page = 1
    max_pages = 10  # Limiter à 10 pages pour éviter trop de requêtes
    results_per_page = 100
    
    print(f"  📡 Fetching from RunSignup (up to {max_pages} pages)...")
    
    while page <= max_pages and len(events) < max_results:
        params = {
            "format": "json",
            "start_date": start_date,
            "end_date": end_date,
            "distance_units": "K",
            "results_per_page": results_per_page,
            "page": page,
            "sort": "date",
            "only_partner_races": "F",
            "include_waiver": "F",
            "include_event_days": "T",
        }
        
        try:
            response = requests.get(RUNSIGNUP_API, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            races = data.get("races", [])
            
            if not races:
                break  # No more results
            
            for race_data in races:
                race = race_data.get("race", {})
                
                # Get date - try multiple fields
                next_date = race.get("next_date")
                
                # Parse and validate date
                parsed_date = parse_date(next_date) if next_date else None
                
                if not parsed_date:
                    continue
                
                # Skip past events
                try:
                    event_date = datetime.strptime(parsed_date, "%Y-%m-%d")
                    if event_date < today:
                        continue
                except:
                    continue
                
                name = race.get("name", "").strip()
                if not name:
                    continue
                
                # Skip virtual/challenge events without physical location
                city = race.get("address", {}).get("city", "")
                if city.lower() in ["anywhere", "virtual", "online", ""]:
                    continue
                
                state = race.get("address", {}).get("state", "")
                country = race.get("address", {}).get("country", "United States")
                
                # Get registration URL
                race_id = race.get("race_id", "")
                reg_url = race.get("url", f"https://runsignup.com/Race/{race_id}")
                if not reg_url.startswith("http"):
                    reg_url = f"https://runsignup.com{reg_url}"
                
                # Determine discipline and distance
                events_list = race.get("events", [])
                distance = "Marathon"
                if events_list:
                    first_event = events_list[0].get("event", {})
                    dist_str = first_event.get("distance", "")
                    distance = map_distance(str(dist_str))
                
                # Clean description
                description = race.get("description", "")
                if description:
                    # Remove HTML tags
                    import re
                    description = re.sub('<[^<]+?>', '', description)[:200]
                else:
                    description = f"Running event in {city}, {state}" if state else f"Running event in {city}"
                
                event = RaceEvent(
                    id=RaceEvent.generate_id(name, parsed_date),
                    name=name,
                    date=parsed_date,
                    city=f"{city}, {state}" if state else city,
                    country=country,
                    countryCode=get_country_code(country),
                    discipline="Running",
                    distance=distance,
                    elevationGain=None,
                    description=description,
                    registrationUrl=reg_url,
                    imageUrl=name.lower().replace(" ", "_"),
                    price=None,
                    currency=None,
                    registrationStatus="Open" if race.get("is_registration_open") == "T" else None,
                    gpxUrl=None,
                    websiteUrl=race.get("external_race_url")
                )
                events.append(event)
                
                if len(events) >= max_results:
                    break
            
            page += 1
                
        except Exception as e:
            print(f"  ⚠️ RunSignup page {page} error: {e}")
            break
    
    # Always add major marathons if we got few real events
    if len(events) < 20:
        print(f"  📦 Adding fallback major marathons...")
        events.extend(get_fallback_marathons())
    
    print(f"✅ RunSignup: Fetched {len(events)} events (from {page-1} pages)")
    return events


def get_fallback_marathons() -> List[RaceEvent]:
    """Return major marathons worldwide - 60+ events"""
    marathons = [
        # World Marathon Majors
        ("Boston Marathon", "2026-04-20", "Boston", "USA", "US", "The world's oldest annual marathon"),
        ("London Marathon", "2026-04-26", "London", "UK", "GB", "One of the World Marathon Majors"),
        ("Berlin Marathon", "2026-09-27", "Berlin", "Germany", "DE", "Known for its fast, flat course"),
        ("Chicago Marathon", "2026-10-11", "Chicago", "USA", "US", "Abbott World Marathon Major"),
        ("New York City Marathon", "2026-11-01", "New York", "USA", "US", "The world's largest marathon"),
        ("Tokyo Marathon", "2026-03-01", "Tokyo", "Japan", "JP", "One of the World Marathon Majors"),
        
        # Europe - Major
        ("Paris Marathon", "2026-04-05", "Paris", "France", "FR", "Scenic route through Paris landmarks"),
        ("Amsterdam Marathon", "2026-10-18", "Amsterdam", "Netherlands", "NL", "Fast and flat Dutch marathon"),
        ("Rotterdam Marathon", "2026-04-12", "Rotterdam", "Netherlands", "NL", "Known for producing fast times"),
        ("Vienna City Marathon", "2026-04-19", "Vienna", "Austria", "AT", "Spring marathon through Vienna"),
        ("Barcelona Marathon", "2026-03-08", "Barcelona", "Spain", "ES", "Mediterranean marathon with sea views"),
        ("Rome Marathon", "2026-03-22", "Rome", "Italy", "IT", "Run past ancient Roman ruins"),
        ("Athens Marathon", "2026-11-08", "Athens", "Greece", "GR", "The original historic marathon course"),
        ("Frankfurt Marathon", "2026-10-25", "Frankfurt", "Germany", "DE", "Fast course through financial capital"),
        ("Munich Marathon", "2026-10-11", "Munich", "Germany", "DE", "Bavarian marathon with great atmosphere"),
        ("Hamburg Marathon", "2026-04-26", "Hamburg", "Germany", "DE", "Scenic route through port city"),
        ("Lisbon Marathon", "2026-10-18", "Lisbon", "Portugal", "PT", "Along the beautiful Tagus River"),
        ("Madrid Marathon", "2026-04-26", "Madrid", "Spain", "ES", "Tour of Spanish capital landmarks"),
        ("Valencia Marathon", "2026-12-06", "Valencia", "Spain", "ES", "World record-breaking fast course"),
        ("Seville Marathon", "2026-02-22", "Seville", "Spain", "ES", "Winter marathon in Andalusia"),
        ("Milan Marathon", "2026-04-05", "Milan", "Italy", "IT", "Fashion capital marathon"),
        ("Florence Marathon", "2026-11-29", "Florence", "Italy", "IT", "Renaissance city historic run"),
        ("Venice Marathon", "2026-10-25", "Venice", "Italy", "IT", "Finish in the iconic St. Mark's Square"),
        ("Copenhagen Marathon", "2026-05-17", "Copenhagen", "Denmark", "DK", "Scandinavian spring marathon"),
        ("Stockholm Marathon", "2026-06-06", "Stockholm", "Sweden", "SE", "Beautiful Nordic capital run"),
        ("Oslo Marathon", "2026-09-19", "Oslo", "Norway", "NO", "Norwegian capital marathon"),
        ("Helsinki Marathon", "2026-08-15", "Helsinki", "Finland", "FI", "Baltic Sea capital marathon"),
        ("Warsaw Marathon", "2026-09-27", "Warsaw", "Poland", "PL", "Growing Eastern European marathon"),
        ("Prague Marathon", "2026-05-03", "Prague", "Czech Republic", "CZ", "Historic city center course"),
        ("Budapest Marathon", "2026-10-11", "Budapest", "Hungary", "HU", "Danube River scenic route"),
        ("Zurich Marathon", "2026-04-19", "Zurich", "Switzerland", "CH", "Swiss precision and scenery"),
        ("Geneva Marathon", "2026-05-10", "Geneva", "Switzerland", "CH", "Lake Geneva waterfront run"),
        ("Brussels Marathon", "2026-10-04", "Brussels", "Belgium", "BE", "European capital marathon"),
        ("Dublin Marathon", "2026-10-25", "Dublin", "Ireland", "IE", "Irish capital with great crowd support"),
        ("Edinburgh Marathon", "2026-05-31", "Edinburgh", "UK", "GB", "Scottish capital scenic route"),
        ("Manchester Marathon", "2026-04-19", "Manchester", "UK", "GB", "Northern England flat course"),
        
        # Africa
        ("Cape Town Marathon", "2026-10-18", "Cape Town", "South Africa", "ZA", "Africa's only World Major candidate"),
        ("Marrakech Marathon", "2026-01-25", "Marrakech", "Morocco", "MA", "Marathon in the Red City"),
        ("Casablanca Marathon", "2026-03-29", "Casablanca", "Morocco", "MA", "Morocco's largest city marathon"),
        ("Rabat Marathon", "2026-04-12", "Rabat", "Morocco", "MA", "Morocco's capital city race"),
        ("Tangier Marathon", "2026-11-15", "Tangier", "Morocco", "MA", "Gateway to Africa marathon"),
        ("Fes Marathon", "2026-05-03", "Fes", "Morocco", "MA", "Imperial city historical run"),
        ("Nairobi Marathon", "2026-10-25", "Nairobi", "Kenya", "KE", "High altitude African marathon"),
        ("Lagos City Marathon", "2026-02-14", "Lagos", "Nigeria", "NG", "West Africa's largest marathon"),
        ("Cairo Marathon", "2026-02-28", "Cairo", "Egypt", "EG", "Run by the Pyramids"),
        
        # Asia
        ("Singapore Marathon", "2026-12-06", "Singapore", "Singapore", "SG", "Night marathon in the city"),
        ("Hong Kong Marathon", "2026-01-25", "Hong Kong", "China", "HK", "Asia's premier marathon"),
        ("Seoul Marathon", "2026-03-15", "Seoul", "South Korea", "KR", "Korean capital spring race"),
        ("Osaka Marathon", "2026-02-28", "Osaka", "Japan", "JP", "Japanese food capital marathon"),
        ("Kyoto Marathon", "2026-02-15", "Kyoto", "Japan", "JP", "Temple city scenic route"),
        ("Bangkok Marathon", "2026-11-15", "Bangkok", "Thailand", "TH", "Southeast Asian major race"),
        ("Kuala Lumpur Marathon", "2026-03-22", "Kuala Lumpur", "Malaysia", "MY", "Malaysian capital race"),
        ("Mumbai Marathon", "2026-01-18", "Mumbai", "India", "IN", "India's largest marathon"),
        ("Delhi Marathon", "2026-02-14", "New Delhi", "India", "IN", "Indian capital winter race"),
        ("Shanghai Marathon", "2026-11-29", "Shanghai", "China", "CN", "China's financial capital run"),
        ("Beijing Marathon", "2026-11-01", "Beijing", "China", "CN", "Chinese capital historic route"),
        ("Dubai Marathon", "2026-01-09", "Dubai", "UAE", "AE", "One of the richest marathons"),
        ("Abu Dhabi Marathon", "2026-12-05", "Abu Dhabi", "UAE", "AE", "Desert capital race"),
        ("Tel Aviv Marathon", "2026-02-27", "Tel Aviv", "Israel", "IL", "Mediterranean coastal marathon"),
        
        # Oceania
        ("Sydney Marathon", "2026-09-20", "Sydney", "Australia", "AU", "Cross the Harbour Bridge"),
        ("Melbourne Marathon", "2026-10-11", "Melbourne", "Australia", "AU", "Australian sporting capital"),
        ("Gold Coast Marathon", "2026-07-05", "Gold Coast", "Australia", "AU", "Australian winter flat race"),
        ("Auckland Marathon", "2026-11-01", "Auckland", "New Zealand", "NZ", "City of Sails marathon"),
        
        # Americas
        ("Los Angeles Marathon", "2026-03-08", "Los Angeles", "USA", "US", "Stadium to the sea course"),
        ("San Francisco Marathon", "2026-07-26", "San Francisco", "USA", "US", "Golden Gate Bridge crossing"),
        ("Houston Marathon", "2026-01-18", "Houston", "USA", "US", "Fast winter Texas race"),
        ("Miami Marathon", "2026-02-01", "Miami", "USA", "US", "Tropical winter marathon"),
        ("Philadelphia Marathon", "2026-11-22", "Philadelphia", "USA", "US", "Historic American city run"),
        ("Marine Corps Marathon", "2026-10-25", "Washington DC", "USA", "US", "The People's Marathon"),
        ("Toronto Marathon", "2026-05-03", "Toronto", "Canada", "CA", "Canadian metropolis race"),
        ("Vancouver Marathon", "2026-05-03", "Vancouver", "Canada", "CA", "Pacific coast scenic run"),
        ("Montreal Marathon", "2026-09-20", "Montreal", "Canada", "CA", "Bilingual Canadian city race"),
        ("Mexico City Marathon", "2026-08-30", "Mexico City", "Mexico", "MX", "High altitude Latin America"),
        ("Buenos Aires Marathon", "2026-10-11", "Buenos Aires", "Argentina", "AR", "South American capital race"),
        ("Rio de Janeiro Marathon", "2026-06-07", "Rio de Janeiro", "Brazil", "BR", "Copacabana beach finish"),
        ("Sao Paulo Marathon", "2026-04-05", "Sao Paulo", "Brazil", "BR", "Brazil's largest city marathon"),
        ("Santiago Marathon", "2026-04-05", "Santiago", "Chile", "CL", "Andes mountain backdrop"),
        ("Lima Marathon", "2026-05-17", "Lima", "Peru", "PE", "Pacific coast South America"),
    ]
    
    return [
        RaceEvent(
            id=RaceEvent.generate_id(name, date),
            name=name, date=date, city=city, country=country,
            countryCode=code, discipline="Running", distance="Marathon",
            elevationGain=None, description=desc,
            registrationUrl=f"https://www.google.com/search?q={name.replace(' ', '+')}+registration+official",
            imageUrl=name.lower().replace(" ", "_"),
            price=None, currency=None, registrationStatus=None,
            gpxUrl=None, websiteUrl=None
        )
        for name, date, city, country, code, desc in marathons
    ]
