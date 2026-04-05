"""
Flight Booking Agent
Searches and ranks flights using tool use. Returns top 3 recommendations.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from models.travel_dto import TravelDTO
from tools.flight_search import search_flights

SYSTEM_PROMPT = """You are a Flight Booking Agent. Your task:
1. Call the search_flights tool with the travel details
2. Analyse the results (price, duration, stops, airline reputation)
3. Return your top 3 recommendations as JSON

Return ONLY a JSON object (no markdown):
{
  "status": "SUCCESS",
  "top_flights": [
    {
      "rank": 1,
      "flight_id": "...",
      "airline": "...",
      "departure_time": "...",
      "arrival_time": "...",
      "duration": "...",
      "stops": 0,
      "price_per_person": 0.0,
      "price_total": 0.0,
      "currency": "USD",
      "cabin_class": "Economy",
      "reason": "Best value — direct flight at lowest price"
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
        "name": "search_flights",
        "description": "Search for available flights between two cities on a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city or airport code"},
                "destination": {"type": "string", "description": "Arrival city or airport code"},
                "departure_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "passengers": {"type": "integer", "description": "Total number of passengers"},
                "max_budget_per_person": {"type": "number", "description": "Maximum price per person in USD"},
            },
            "required": ["origin", "destination", "departure_date", "passengers"],
        },
    }
]


class FlightAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def search(self, dto: TravelDTO) -> dict:
        """Run the flight search agentic loop and return ranked results."""
        total_passengers = dto.travelers.adults + dto.travelers.kids
        budget_per_person = (
            (dto.budget.total * 0.35) / total_passengers
            if dto.budget.total
            else None
        )

        prompt = (
            f"Find the best flights for this trip:\n"
            f"- From: {dto.origin or 'origin not specified'}\n"
            f"- To: {dto.destination}\n"
            f"- Departure: {dto.start_date}\n"
            f"- Return: {dto.end_date}\n"
            f"- Passengers: {total_passengers} ({dto.travelers.adults} adults, {dto.travelers.kids} kids)\n"
            f"- Max budget per person for flights: ${budget_per_person:.0f}" if budget_per_person else ""
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
                # Strip markdown fences
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError:
                    return {"status": "ERROR", "message": "Could not parse flight results"}

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use" and block.name == "search_flights":
                        result = search_flights(**block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
