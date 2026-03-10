import re
import logging
import time
from datetime import datetime, timedelta
from calendar import monthrange
from fast_flights import FlightData, Passengers, get_flights
from config import QUERY_DELAY, SAMPLE_DAYS_PER_MONTH

log = logging.getLogger(__name__)


def parse_price(price_str):
    """Parse 'MYR\xa0516' or 'RM\xa0516' into float.
    Rejects price insight text like 'MYR 59 cheaper than usual'."""
    if not price_str:
        return None

    s = price_str.strip()

    # Accept MYR or RM prefix
    if s.startswith("MYR"):
        after = s[3:]
    elif s.startswith("RM"):
        after = s[2:]
    else:
        return None

    # After prefix: only whitespace + digits + comma/period allowed
    cleaned = after.replace("\xa0", "").replace(" ", "").replace(",", "")
    if not cleaned or not cleaned.replace(".", "", 1).isdigit():
        return None

    val = float(cleaned)
    # Sanity: reject unreasonably low or high prices
    if val < 20 or val > 10000:
        return None
    return val


def search_flights_for_date(fly_from, fly_to, date_str):
    """Search flights for a specific date. Returns list of flight dicts."""
    try:
        res = get_flights(
            flight_data=[
                FlightData(date=date_str, from_airport=fly_from, to_airport=fly_to),
            ],
            seat="economy",
            trip="one-way",
            passengers=Passengers(adults=1),
            currency="MYR",
            fetch_mode="fallback",
        )
    except Exception as e:
        log.warning(f"  get_flights failed for {fly_from}-{fly_to} {date_str}: {e}")
        return []

    if not res or not res.flights:
        return []

    results = []
    seen = set()
    for f in res.flights:
        log.debug(f"  raw: price={f.price!r} name={f.name!r} dep={f.departure!r} dur={f.duration!r}")

        price = parse_price(f.price)
        if price is None:
            continue

        # Skip entries with no airline name
        if not f.name or f.name.strip() == "":
            continue
        # Skip if stops is not a number
        if not isinstance(f.stops, int):
            continue
        # Skip if missing key fields
        if not f.departure or not f.arrival or not f.duration:
            continue

        # Dedup: same airline + price + departure
        key = (f.name, price, f.departure)
        if key in seen:
            continue
        seen.add(key)

        # Build search links
        d = datetime.strptime(date_str, "%Y-%m-%d")
        aa_date = f"{d.day:02d}%2F{d.month:02d}%2F{d.year}"
        google_link = (
            f"https://www.google.com/travel/flights"
            f"?q=from+{fly_from}+to+{fly_to}+on+{date_str}+one+way&curr=MYR"
        )
        airasia_link = (
            f"https://www.airasia.com/flights/search/"
            f"?origin={fly_from}&destination={fly_to}"
            f"&departDate={aa_date}&tripType=O"
            f"&adult=1&child=0&infant=0&currency=MYR&cabinClass=economy"
        )

        results.append({
            "price": price,
            "fly_date": date_str,
            "airline": f.name,
            "stops": f.stops,
            "departure": f.departure,
            "arrival": f.arrival,
            "duration": f.duration,
            "deep_link": google_link,
            "airasia_link": airasia_link,
        })

    # Sort by price, keep top 5
    results.sort(key=lambda r: r["price"])
    return results[:5]


def _pick_sample_days(year, month, n_samples):
    """Pick evenly spread sample days for a month.
    E.g. for n_samples=5 in a 30-day month: [3, 9, 15, 21, 27]"""
    days_in_month = monthrange(year, month)[1]
    if n_samples >= days_in_month:
        return list(range(1, days_in_month + 1))

    step = days_in_month / (n_samples + 1)
    return [min(int(step * (i + 1)), days_in_month) for i in range(n_samples)]


def scan_month(fly_from, fly_to, year, month):
    """Sample spread-out dates in the month to find cheap flights."""
    sample_days = _pick_sample_days(year, month, SAMPLE_DAYS_PER_MONTH)
    today = datetime.now().date()

    all_results = []
    for day in sample_days:
        date = datetime(year, month, day).date()
        # Skip past dates and dates too close (< 3 days out)
        if date <= today + timedelta(days=2):
            continue

        date_str = date.strftime("%Y-%m-%d")
        try:
            results = search_flights_for_date(fly_from, fly_to, date_str)
            all_results.extend(results)
            if results:
                log.info(f"  {fly_from}-{fly_to} {date_str}: {len(results)} flights, cheapest MYR {results[0]['price']:.0f}")
            else:
                log.info(f"  {fly_from}-{fly_to} {date_str}: no results")
        except Exception as e:
            log.warning(f"  {fly_from}-{fly_to} {date_str}: error - {e}")

        time.sleep(QUERY_DELAY)

    return all_results


def scan_route_months(fly_from, fly_to, months_ahead=4):
    """Scan multiple months ahead for a route. Returns all results."""
    all_results = []
    now = datetime.now()

    for i in range(months_ahead):
        month = now.month + i
        year = now.year
        while month > 12:
            month -= 12
            year += 1

        log.info(f"  Scanning {fly_from}-{fly_to} {year}-{month:02d}...")
        try:
            results = scan_month(fly_from, fly_to, year, month)
            all_results.extend(results)
        except Exception as e:
            log.error(f"Error scanning {fly_from}-{fly_to} {year}-{month:02d}: {e}")

    return all_results
