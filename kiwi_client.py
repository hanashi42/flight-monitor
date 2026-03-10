import requests
from datetime import datetime, timedelta
from calendar import monthrange
from config import KIWI_API_KEY, KIWI_BASE_URL, CURRENCY


HEADERS = {"apikey": KIWI_API_KEY}


def search_flights(fly_from, fly_to, date_from, date_to, max_stopovers=2):
    """Search flights for a date range. Returns list of flight dicts."""
    params = {
        "fly_from": fly_from,
        "fly_to": fly_to,
        "date_from": date_from.strftime("%d/%m/%Y"),
        "date_to": date_to.strftime("%d/%m/%Y"),
        "curr": CURRENCY,
        "max_stopovers": max_stopovers,
        "sort": "price",
        "limit": 5,
        "one_for_city": 0,
        "flight_type": "oneway",
    }
    resp = requests.get(
        f"{KIWI_BASE_URL}/v2/search",
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])

    results = []
    for flight in data:
        airlines = ", ".join(set(r.get("airline", "?") for r in flight.get("route", [])))
        results.append({
            "price": flight["price"],
            "fly_date": datetime.utcfromtimestamp(flight["dTime"]).strftime("%Y-%m-%d"),
            "airline": airlines,
            "stops": len(flight.get("route", [])) - 1,
            "deep_link": flight.get("deep_link", ""),
        })
    return results


def scan_month(fly_from, fly_to, year, month):
    """Scan a whole month, return cheapest flights found."""
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, monthrange(year, month)[1])
    return search_flights(fly_from, fly_to, first_day, last_day)


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
            print(f"Error scanning {fly_from}-{fly_to} {year}-{month:02d}: {e}")
    return all_results
