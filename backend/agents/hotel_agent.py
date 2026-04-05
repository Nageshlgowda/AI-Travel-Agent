"""
Hotel Booking Agent
Searches and ranks hotels based on budget, preferences, and ratings.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from models.travel_dto import TravelDTO
from tools.hotel_search import search_hotels

SYSTEM_PROMPT = """You are a Hotel Booking Agent. Your task:
1. Call the search_hotels tool with the travel details
2. Score hotels by: budget fit, rating, location, amenities, and traveler preferences
3. Return your top 3 recommendations as JSON

Return ONLY a JSON object (no markdown):
{
  "status": "SUCCESS",
  "top_hotels": [
    {
      "rank": 1,
      "hotel_id": "...",
      "name": "...",
      "category": "...",
      "rating": 4.5,
      "location": "...",
      "price_per_night": 0.0,
      "total_price": 0.0,
      "currency": "USD",
      "amenities": [],
      "breakfast_included": false,
      "free_cancellation": true,
      "reason": "Best rated hotel within budget with great location"
    }
  ],
  "best_choice": {
    "rank": 1,
    "reason": "..."
  },
  "budget_note": "..."
}"""

TOOLS = [
    {
        "name": "search_hotels",
        "description": "Search for available hotels in a city for given dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "check_in": {"type": "string", "description": "Check-in date YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "Check-out date YYYY-MM-DD"},
                "guests": {"type": "integer", "description": "Number of guests"},
                "budget_per_night": {"type": "number", "description": "Max price per night in USD"},
                "hotel_type": {"type": "string", "description": "budget | mid-range | luxury"},
                "location_preference": {"type": "string", "description": "E.g. beachfront, city center"},
            },
            "required": ["city", "check_in", "check_out", "guests"],
        },
    }
]


class HotelAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def search(self, dto: TravelDTO) -> dict:
        """Run the hotel search agentic loop and return ranked results."""
        total_guests = dto.travelers.adults + dto.travelers.kids
        nights_budget_per_night = (
            (dto.budget.total * 0.45) / max(1, _nights(dto.start_date, dto.end_date))
            if dto.budget.total
            else None
        )

        prompt = (
            f"Find the best hotels for this trip:\n"
            f"- City: {dto.destination}\n"
            f"- Check-in: {dto.start_date}\n"
            f"- Check-out: {dto.end_date}\n"
            f"- Guests: {total_guests}\n"
            f"- Hotel preference: {dto.preferences.hotel_type or 'mid-range'}\n"
            f"- Location: {dto.preferences.location_preference or 'any'}\n"
            f"- Max per night: ${nights_budget_per_night:.0f}" if nights_budget_per_night else ""
        )

        messages = [{"role": "user", "content": prompt}]

        while True:
            response = await self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text = next(
                    (b.text for b in response.content if b.type == "text"), "{}"
                )
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError:
                    return {"status": "ERROR", "message": "Could not parse hotel results"}

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use" and block.name == "search_hotels":
                        result = search_hotels(**block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})


def _nights(start_date, end_date) -> int:
    try:
        from datetime import date
        return max(1, (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days)
    except Exception:
        return 3
