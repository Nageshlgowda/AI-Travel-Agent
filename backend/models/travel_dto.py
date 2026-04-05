from pydantic import BaseModel
from typing import Optional, List


class Travelers(BaseModel):
    adults: int = 1
    kids: int = 0


class Budget(BaseModel):
    total: Optional[float] = None
    currency: str = "USD"


class Preferences(BaseModel):
    hotel_type: Optional[str] = None        # budget | mid-range | luxury
    room_type: Optional[str] = None         # single | double | suite
    location_preference: Optional[str] = None
    preferred_hotel_name: Optional[str] = None   # e.g. "Marriott", "Hilton", "any"
    preferred_airline: Optional[str] = None      # e.g. "Emirates", "any"
    interests: List[str] = []
    activity_level: Optional[str] = None    # relaxed | balanced | packed


class ClimatePrefs(BaseModel):
    preferred_weather: Optional[str] = None
    rain_ok: bool = True


class Constraints(BaseModel):
    visa_required: Optional[str] = None
    diet: Optional[str] = None
    has_kids: bool = False
    has_elderly: bool = False


class TravelDTO(BaseModel):
    destination: Optional[str] = None
    origin: Optional[str] = None
    start_date: Optional[str] = None        # YYYY-MM-DD
    end_date: Optional[str] = None          # YYYY-MM-DD
    travelers: Travelers = Travelers()
    budget: Budget = Budget()
    purpose: Optional[str] = None
    preferences: Preferences = Preferences()
    climate: ClimatePrefs = ClimatePrefs()
    constraints: Constraints = Constraints()

    def is_complete(self) -> bool:
        return all([
            self.origin,
            self.destination,
            self.start_date,
            self.end_date,
            self.travelers.adults >= 1,
            self.budget.total is not None and self.budget.total > 0,
        ])

    def missing_fields(self) -> List[str]:
        missing = []
        if not self.origin:
            missing.append("origin city (where you're flying from)")
        if not self.destination:
            missing.append("destination city/country")
        if not self.start_date:
            missing.append("start date (YYYY-MM-DD)")
        if not self.end_date:
            missing.append("end date (YYYY-MM-DD)")
        if not (self.budget.total and self.budget.total > 0):
            missing.append("total budget")
        return missing

    def unasked_nice_to_have(self) -> List[str]:
        """Fields not strictly required but worth asking about if not yet provided."""
        items = []
        if self.travelers.adults == 1 and self.travelers.kids == 0:
            items.append("number of travelers (adults and kids)")
        return items

    def to_summary(self) -> str:
        parts = []
        if self.destination:
            parts.append(f"Destination: {self.destination}")
        if self.origin:
            parts.append(f"From: {self.origin}")
        if self.start_date and self.end_date:
            parts.append(f"Dates: {self.start_date} to {self.end_date}")
        parts.append(f"Travelers: {self.travelers.adults} adult(s), {self.travelers.kids} kid(s)")
        if self.budget.total:
            parts.append(f"Budget: {self.budget.total:,.0f} {self.budget.currency}")
        if self.purpose:
            parts.append(f"Purpose: {self.purpose.title()}")
        if self.preferences.hotel_type:
            parts.append(f"Hotel type: {self.preferences.hotel_type.title()}")
        if self.preferences.preferred_hotel_name:
            parts.append(f"Preferred hotel: {self.preferences.preferred_hotel_name}")
        if self.preferences.preferred_airline:
            parts.append(f"Preferred airline: {self.preferences.preferred_airline}")
        return "\n".join(parts)

