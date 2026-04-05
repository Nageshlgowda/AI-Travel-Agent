"""
Mock Hotel Search API.
Swap search_hotels() with a real API (Booking.com, Expedia) keeping the same return shape.
"""
import random
import string
from typing import Any

HOTEL_CHAINS = {
    "luxury": [
        "The Ritz-Carlton", "Four Seasons", "Mandarin Oriental",
        "Park Hyatt", "Aman Resorts", "St. Regis",
    ],
    "mid-range": [
        "Marriott", "Hilton Garden Inn", "Hyatt Place",
        "Courtyard by Marriott", "Holiday Inn", "Novotel",
    ],
    "budget": [
        "ibis", "Premier Inn", "Travelodge",
        "Best Western", "Hampton Inn", "Comfort Inn",
    ],
}

AMENITIES_POOL = [
    "Free WiFi", "Swimming Pool", "Fitness Center", "Spa",
    "Restaurant", "Bar", "Concierge", "Room Service",
    "Airport Shuttle", "Business Center", "Parking",
    "Beachfront", "City View", "Rooftop Terrace",
]

LOCATION_TYPES = ["City Center", "Beachfront", "Near Airport", "Historic District", "Business District"]


def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int,
    budget_per_night: float = None,
    hotel_type: str = "mid-range",
    location_preference: str = None,
) -> dict[str, Any]:
    """Search for available hotels and return ranked options."""
    rng = random.Random(hash(f"{city}{check_in}{check_out}"))

    hotel_type = hotel_type.lower() if hotel_type else "mid-range"
    if hotel_type not in HOTEL_CHAINS:
        hotel_type = "mid-range"

    chains = HOTEL_CHAINS[hotel_type]
    price_range = {
        "budget": (40, 120),
        "mid-range": (100, 280),
        "luxury": (280, 900),
    }[hotel_type]

    hotels = []
    selected_chains = rng.choices(chains, k=6)

    for i, chain in enumerate(selected_chains):
        price_per_night = round(rng.uniform(*price_range), 2)
        rating = round(rng.uniform(3.5, 5.0), 1)
        amenities = rng.sample(AMENITIES_POOL, rng.randint(4, 8))
        location = location_preference or rng.choice(LOCATION_TYPES)

        hotels.append({
            "hotel_id": f"HTL{rng.randint(1000, 9999)}",
            "name": f"{chain} {city}",
            "category": hotel_type.title(),
            "rating": rating,
            "reviews_count": rng.randint(200, 8000),
            "location": location,
            "price_per_night": price_per_night,
            "total_price": round(price_per_night * _nights(check_in, check_out), 2),
            "currency": "USD",
            "amenities": amenities,
            "room_type": rng.choice(["Standard Double", "Deluxe King", "Suite", "Superior Twin"]),
            "free_cancellation": rng.choice([True, False]),
            "breakfast_included": rng.choice([True, False]),
            "distance_to_center": f"{rng.uniform(0.1, 5.0):.1f} km",
        })

    hotels.sort(key=lambda h: (-h["rating"], h["price_per_night"]))

    if budget_per_night:
        affordable = [h for h in hotels if h["price_per_night"] <= budget_per_night]
        if affordable:
            hotels = affordable

    return {
        "status": "success",
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "nights": _nights(check_in, check_out),
        "results_count": len(hotels),
        "hotels": hotels[:5],
    }


def book_hotel(hotel_id: str, guest_name: str, check_in: str, check_out: str) -> dict[str, Any]:
    """Mock hotel booking — returns a confirmation."""
    ref = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return {
        "status": "confirmed",
        "booking_reference": ref,
        "hotel_id": hotel_id,
        "guest_name": guest_name,
        "check_in": check_in,
        "check_out": check_out,
        "message": f"Hotel booked! Reference: {ref}",
    }


def _nights(check_in: str, check_out: str) -> int:
    """Calculate number of nights between two YYYY-MM-DD dates."""
    try:
        from datetime import date
        d1 = date.fromisoformat(check_in)
        d2 = date.fromisoformat(check_out)
        return max(1, (d2 - d1).days)
    except Exception:
        return 3
