import re
import logging
import time
from datetime import datetime, timedelta
from calendar import monthrange
from fast_flights import FlightData, Passengers, get_flights

log = logging.getLogger(__name__)

# Delay between queries to avoid rate limiting
QUERY_DELAY = 2  # seconds


def parse_price(price_str):
    """Parse 'MYR\xa0516' into float. Only accepts real ticket price format.
    Rejects price insight text like 'MYR 59 cheaper than usual'."""
    if not price_str:
        return None
    if not price_str.startswith("MYR"):
        return None
    # After "MYR", should only be whitespace + digits + comma/period
    after_myr = price_str[3:]
    cleaned = after_myr.replace("\xa0", "").replace(" ", "").replace(",", "")
    if not cleaned or not cleaned.replace(".", "", 1).isdigit():
        return None
    return float(cleaned)


def search_flights_for_date(fly_from, fly_to, date_str):
    """Search flights for a specific date. Returns list of flight dicts."""
    res = get_flights(
        flight_data=[
            FlightData(date=date_str, from_airport=fly_from, to_airport=fly_to),
        ],
        seat="economy",
        trip="one-way",
        passengers=Passengers(adults=1),
        fetch_mode="local",
    )

    results = []
    seen = set()
    for f in res.flights:
        log.debug(f"  raw: price={f.price!r} name={f.name!r} dep={f.departure!r} dur={f.duration!r}")
        price = parse_price(f.price)
        if price is None or price < 20:
            continue
        # Skip entries with no airline name (page UI elements)
        if not f.name or f.name.strip() == "":
            continue
        # Skip if stops is not a number
        if not isinstance(f.stops, int):
            continue
        # Skip if missing departure/arrival/duration (UI artifacts)
        if not f.departure or not f.arrival or not f.duration:
            continue
        # Dedup: same airline+price+departure
        key = (f.name, price, f.departure)
        if key in seen:
            continue
        seen.add(key)

        # Build AirAsia MOVE search link (date format: DD%2FMM%2FYYYY)
        d = datetime.strptime(date_str, "%Y-%m-%d")
        aa_date = f"{d.day:02d}%2F{d.month:02d}%2F{d.year}"
        airasia_link = f"https://www.airasia.com/flights/search/?origin={fly_from}&destination={fly_to}&departDate={aa_date}&tripType=O&adult=1&child=0&infant=0&currency=MYR&cabinClass=economy"

        results.append({
            "price": price,
            "fly_date": date_str,
            "airline": f.name,
            "stops": f.stops,
            "deep_link": f"https://www.google.com/travel/flights?q=from+{fly_from}+to+{fly_to}+on+{date_str}+one+way&curr=MYR",
            "airasia_link": airasia_link,
        })

    # Sort by price, keep top 5
    results.sort(key=lambda r: r["price"])
    return results[:5]


def scan_month(fly_from, fly_to, year, month):
    """Sample dates in the month to find cheap flights."""
    days_in_month = monthrange(year, month)[1]
    # Sample: mid-month only (1 query per month to keep scan fast)
    sample_days = [15]
    sample_days = [d for d in sample_days if d <= days_in_month]

    all_results = []
    today = datetime.now().date()

    for day in sample_days:
        date = datetime(year, month, day).date()
        if date <= today:
            continue
        date_str = date.strftime("%Y-%m-%d")

        try:
            results = search_flights_for_date(fly_from, fly_to, date_str)
            all_results.extend(results)
            log.info(f"  {fly_from}-{fly_to} {date_str}: {len(results)} flights, cheapest MYR {results[0]['price']:.0f}" if results else f"  {fly_from}-{fly_to} {date_str}: no results")
        except Exception as e:
            log.warning(f"  {fly_from}-{fly_to} {date_str}: error - {e}")

        time.sleep(QUERY_DELAY)

    return all_results


def scan_route_months(fly_from, fly_to, months_ahead=6):
    """Scan multiple months ahead for a route. Returns all results."""
    all_results = []
    now = datetime.now()
    for i in range(months_ahead):
        month = now.month + i
        year = now.year
        while month > 12:
            month -= 12
            year += 1
        try:
            results = scan_month(fly_from, fly_to, year, month)
            all_results.extend(results)
        except Exception as e:
            log.error(f"Error scanning {fly_from}-{fly_to} {year}-{month:02d}: {e}")
    return all_results
