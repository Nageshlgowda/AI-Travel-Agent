"""
Mock Flight Search API.
Swap search_flights() with a real API (Amadeus, Skyscanner) by keeping the same return shape.
"""
import random
import string
from typing import Any

AIRLINES = [
    {"name": "Air France", "code": "AF"},
    {"name": "British Airways", "code": "BA"},
    {"name": "Emirates", "code": "EK"},
    {"name": "Delta Airlines", "code": "DL"},
    {"name": "Lufthansa", "code": "LH"},
    {"name": "Singapore Airlines", "code": "SQ"},
    {"name": "Qatar Airways", "code": "QR"},
    {"name": "United Airlines", "code": "UA"},
    {"name": "Turkish Airlines", "code": "TK"},
    {"name": "Etihad Airways", "code": "EY"},
]

STOPOVER_CITIES = ["Dubai", "London", "Frankfurt", "Doha", "Istanbul", "Singapore", "Amsterdam"]


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    passengers: int,
    max_budget_per_person: float = None,
) -> dict[str, Any]:
    """Search for available flights and return ranked options."""
    rng = random.Random(hash(f"{origin}{destination}{departure_date}"))

    base_price = rng.uniform(180, 1400)
    selected_airlines = rng.sample(AIRLINES, min(6, len(AIRLINES)))
    flights = []

    for airline in selected_airlines:
        price_per_person = round(base_price * rng.uniform(0.75, 1.6), 2)
        price_total = round(price_per_person * passengers, 2)
        duration_h = rng.randint(3, 18)
        duration_m = rng.choice([0, 15, 30, 45])
        stops = rng.choices([0, 1, 2], weights=[50, 35, 15])[0]

        dep_h, dep_m = rng.randint(5, 22), rng.choice([0, 15, 30, 45])
        arr_h = (dep_h + duration_h) % 24
        arr_m = (dep_m + duration_m) % 60

        stop_info = (
            "Non-stop"
            if stops == 0
            else (f"1 stop via {rng.choice(STOPOVER_CITIES)}" if stops == 1 else "2 stops")
        )

        flights.append({
            "flight_id": f"{airline['code']}{rng.randint(100, 999)}",
            "airline": airline["name"],
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": departure_date,
            "departure_time": f"{dep_h:02d}:{dep_m:02d}",
            "arrival_time": f"{arr_h:02d}:{arr_m:02d}",
            "duration": f"{duration_h}h {duration_m}m",
            "stops": stops,
            "stop_info": stop_info,
            "price_per_person": price_per_person,
            "price_total": price_total,
            "currency": "USD",
            "cabin_class": rng.choices(["Economy", "Business"], weights=[80, 20])[0],
            "baggage_included": "23 kg",
            "refundable": rng.choice([True, False]),
            "seats_available": rng.randint(2, 25),
        })

    flights.sort(key=lambda f: f["price_total"])

    if max_budget_per_person:
        affordable = [f for f in flights if f["price_per_person"] <= max_budget_per_person]
        if affordable:
            flights = affordable

    return {
        "status": "success",
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "passengers": passengers,
        "results_count": len(flights),
        "flights": flights[:5],
    }


def book_flight(flight_id: str, passenger_names: list[str]) -> dict[str, Any]:
    """Mock flight booking — returns a confirmation."""
    ref = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return {
        "status": "confirmed",
        "booking_reference": ref,
        "flight_id": flight_id,
        "passengers": passenger_names,
        "message": f"Flight booked! Reference: {ref}",
    }
