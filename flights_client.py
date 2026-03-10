import re
import logging
import time
from datetime import datetime, timedelta
from calendar import monthrange
from fast_flights import FlightData, Passengers, get_flights

log = logging.getLogger(__name__)

# Delay between queries to avoid rate limiting
QUERY_DELAY = 3  # seconds


def parse_price(price_str):
    """Parse 'MYR\xa0516' or 'MYR 516' into float. Returns None if unparseable."""
    if not price_str or "unavailable" in price_str.lower():
        return None
    nums = re.sub(r"[^\d.]", "", price_str)
    return float(nums) if nums else None


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
        price = parse_price(f.price)
        if price is None or price == 0:
            continue
        # Dedup: same airline+price+departure
        key = (f.name, price, f.departure)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "price": price,
            "fly_date": date_str,
            "airline": f.name or "Unknown",
            "stops": f.stops if f.stops is not None else 0,
            "deep_link": f"https://www.google.com/travel/flights?q=Flights+from+{fly_from}+to+{fly_to}+on+{date_str}",
        })

    # Sort by price, keep top 5
    results.sort(key=lambda r: r["price"])
    return results[:5]


def scan_month(fly_from, fly_to, year, month):
    """Sample 4 dates in the month to find cheap flights."""
    days_in_month = monthrange(year, month)[1]
    # Sample: mid-month and end-month
    sample_days = [15, 28]
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
