"""Flight search client using fli (Google Flights internal API).

Uses SearchDates for monthly cheapest-date scanning, then SearchFlights
for detailed flight info on the best dates.
"""

import logging
import time
import requests
from datetime import datetime, timedelta
from calendar import monthrange

from fli.search import SearchDates, SearchFlights
from fli.models import (
    Airport,
    DateSearchFilters,
    FlightSearchFilters,
    FlightSegment,
    PassengerInfo,
    SeatType,
    TripType,
)
from fli.core import build_flight_segments, build_date_search_segments

log = logging.getLogger(__name__)

# Delay between API calls to avoid rate limiting
QUERY_DELAY = 1

# Google Flights returns prices in currency based on server IP location.
# CI runs on US servers → USD. We need to convert to MYR.
_usd_to_myr = None


def _get_usd_to_myr():
    """Fetch current USD→MYR rate from frankfurter.dev (cached per run)."""
    global _usd_to_myr
    if _usd_to_myr is not None:
        return _usd_to_myr
    try:
        resp = requests.get(
            "https://api.frankfurter.dev/v1/latest?base=USD&symbols=MYR",
            timeout=5,
        )
        resp.raise_for_status()
        _usd_to_myr = resp.json()["rates"]["MYR"]
        log.info(f"USD→MYR rate: {_usd_to_myr}")
    except Exception as e:
        log.warning(f"Failed to fetch USD→MYR rate, using fallback 4.4: {e}")
        _usd_to_myr = 4.4
    return _usd_to_myr


def _detect_currency_multiplier():
    """Detect if Google Flights is returning USD or MYR.

    Does a probe search for a known route (KUL→SIN, always ~MYR 50-300).
    If the returned price is < 15 (i.e. looks like USD ~$12-70), we're getting USD.
    Returns multiplier: ~4.4 for USD→MYR conversion, 1.0 if already MYR.
    Cached for the entire run.
    """
    global _usd_to_myr
    if _usd_to_myr is not None:
        return _usd_to_myr

    # Probe: KUL→SIN is always cheap and available
    try:
        origin = getattr(Airport, "KUL")
        dest = getattr(Airport, "SIN")
        tomorrow = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        segments, trip_type = build_date_search_segments(origin, dest, tomorrow)
        filters = DateSearchFilters(
            flight_segments=segments,
            passenger_info=PassengerInfo(adults=1),
            trip_type=trip_type,
            seat_type=SeatType.ECONOMY,
            from_date=tomorrow,
            to_date=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
        )
        searcher = SearchDates()
        results = searcher.search(filters)
        if results:
            min_price = min(dp.price for dp in results)
            # KUL→SIN in MYR is typically 50-300. In USD it's 12-70.
            if min_price < 25:
                # Getting USD — fetch conversion rate
                try:
                    resp = requests.get(
                        "https://api.frankfurter.dev/v1/latest?base=USD&symbols=MYR",
                        timeout=5,
                    )
                    resp.raise_for_status()
                    rate = resp.json()["rates"]["MYR"]
                except Exception:
                    rate = 4.4
                log.info(f"Currency probe: KUL→SIN min={min_price} → USD detected, rate={rate}")
                _usd_to_myr = rate
                return _usd_to_myr
            else:
                log.info(f"Currency probe: KUL→SIN min={min_price} → MYR detected")
                _usd_to_myr = 1.0
                return _usd_to_myr
    except Exception as e:
        log.warning(f"Currency probe failed, assuming USD with fallback rate: {e}")

    # Fallback: assume USD on CI
    _usd_to_myr = 4.4
    return _usd_to_myr


def _to_myr(price):
    """Convert price to MYR if needed."""
    multiplier = _detect_currency_multiplier()
    if multiplier == 1.0:
        return price
    return round(price * multiplier, 2)


def _make_links(fly_from, fly_to, date_str):
    """Build Google Flights and AirAsia MOVE search links."""
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
    return google_link, airasia_link


def _resolve_airport(code):
    """Resolve IATA code to fli Airport enum, return None if unknown."""
    try:
        return getattr(Airport, code)
    except AttributeError:
        log.warning(f"Unknown airport code: {code}")
        return None


def search_flights_for_date(fly_from, fly_to, date_str):
    """Search flights for a specific date. Returns list of flight dicts."""
    origin = _resolve_airport(fly_from)
    dest = _resolve_airport(fly_to)
    if not origin or not dest:
        return []

    try:
        segments, trip_type = build_flight_segments(origin, dest, date_str)
        filters = FlightSearchFilters(
            flight_segments=segments,
            passenger_info=PassengerInfo(adults=1),
            trip_type=trip_type,
            seat_type=SeatType.ECONOMY,
        )
        searcher = SearchFlights()
        flights = searcher.search(filters)
    except Exception as e:
        log.warning(f"  SearchFlights failed for {fly_from}-{fly_to} {date_str}: {e}")
        return []

    if not flights:
        return []

    google_link, airasia_link = _make_links(fly_from, fly_to, date_str)

    results = []
    seen = set()
    for f in flights:
        price = _to_myr(f.price)
        if price < 20 or price > 10000:
            continue

        # Extract airline from first leg
        airline = f.legs[0].airline.value if f.legs else "Unknown"
        stops = f.stops

        # Departure/arrival from first and last leg
        dep_dt = f.legs[0].departure_datetime
        arr_dt = f.legs[-1].arrival_datetime
        departure = dep_dt.strftime("%H:%M")
        arrival = arr_dt.strftime("%H:%M")

        # Duration
        hours, mins = divmod(f.duration, 60)
        duration = f"{hours}h {mins:02d}m"

        # Dedup: same airline + price + departure
        key = (airline, price, departure)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "price": price,
            "fly_date": date_str,
            "airline": airline,
            "stops": stops,
            "departure": departure,
            "arrival": arrival,
            "duration": duration,
            "deep_link": google_link,
            "airasia_link": airasia_link,
        })

    results.sort(key=lambda r: r["price"])
    return results[:5]


def _search_cheapest_dates(fly_from, fly_to, from_date, to_date):
    """Use SearchDates to find cheapest dates in a range. Returns sorted list of (date_str, price)."""
    origin = _resolve_airport(fly_from)
    dest = _resolve_airport(fly_to)
    if not origin or not dest:
        return []

    try:
        segments, trip_type = build_date_search_segments(origin, dest, from_date)
        filters = DateSearchFilters(
            flight_segments=segments,
            passenger_info=PassengerInfo(adults=1),
            trip_type=trip_type,
            seat_type=SeatType.ECONOMY,
            from_date=from_date,
            to_date=to_date,
        )
        searcher = SearchDates()
        results = searcher.search(filters)
    except Exception as e:
        log.warning(f"  SearchDates failed for {fly_from}-{fly_to} {from_date}~{to_date}: {e}")
        return []

    if not results:
        return []

    dated_prices = []
    for dp in results:
        date_str = dp.date[0].strftime("%Y-%m-%d")
        dated_prices.append((date_str, _to_myr(dp.price)))

    dated_prices.sort(key=lambda x: x[1])
    return dated_prices


def scan_route_months(fly_from, fly_to, months_ahead=4):
    """Scan multiple months ahead for a route using two-step strategy:
    1. SearchDates for each month to find cheapest dates
    2. SearchFlights on top 2 cheapest dates per month for detailed info

    Returns list of flight dicts compatible with monitor.py.
    """
    all_results = []
    now = datetime.now()
    today = now.date()

    for i in range(months_ahead):
        month = now.month + i
        year = now.year
        while month > 12:
            month -= 12
            year += 1

        # Date range for this month
        days_in_month = monthrange(year, month)[1]
        from_date = datetime(year, month, 1).date()
        to_date = datetime(year, month, days_in_month).date()

        # Skip past dates
        if from_date <= today:
            from_date = today + timedelta(days=3)
        if from_date > to_date:
            continue

        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        log.info(f"  Scanning {fly_from}-{fly_to} {year}-{month:02d} (dates)...")

        # Step 1: Get cheapest dates for the month
        try:
            dated_prices = _search_cheapest_dates(fly_from, fly_to, from_str, to_str)
        except Exception as e:
            log.error(f"Error scanning dates {fly_from}-{fly_to} {year}-{month:02d}: {e}")
            continue

        if not dated_prices:
            log.info(f"  {fly_from}-{fly_to} {year}-{month:02d}: no date prices")
            continue

        # Log cheapest date found
        log.info(f"  {fly_from}-{fly_to} {year}-{month:02d}: {len(dated_prices)} dates, cheapest MYR {dated_prices[0][1]:.0f} on {dated_prices[0][0]}")

        # Step 2: Get detailed flights for top 2 cheapest dates
        for date_str, date_price in dated_prices[:2]:
            time.sleep(QUERY_DELAY)
            try:
                flights = search_flights_for_date(fly_from, fly_to, date_str)
                if flights:
                    all_results.extend(flights)
                    log.info(f"  {fly_from}-{fly_to} {date_str}: {len(flights)} flights, cheapest MYR {flights[0]['price']:.0f}")
                else:
                    # Fallback: use the date price from SearchDates
                    google_link, airasia_link = _make_links(fly_from, fly_to, date_str)
                    all_results.append({
                        "price": date_price,
                        "fly_date": date_str,
                        "airline": "Unknown",
                        "stops": 0,
                        "departure": "",
                        "arrival": "",
                        "duration": "",
                        "deep_link": google_link,
                        "airasia_link": airasia_link,
                    })
            except Exception as e:
                log.warning(f"  {fly_from}-{fly_to} {date_str}: error - {e}")

        time.sleep(QUERY_DELAY)

    # Sort all results by price
    all_results.sort(key=lambda r: r["price"])
    return all_results
