"""
Planning Agent (Orchestrator Brain)
Synthesizes flight, hotel, and climate data into a full day-by-day travel plan.
Uses claude-opus-4-6 with adaptive thinking for complex synthesis.
Streams the response for real-time output.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from models.travel_dto import TravelDTO
from typing import AsyncIterator

SYSTEM_PROMPT = """You are an expert AI Travel Planning Agent. You have already received:
- The traveler's requirements (DTO)
- Real flight search results
- Real hotel search results
- Real weather/climate analysis

Your job: Create a comprehensive, realistic, and exciting travel plan.

Structure your response as a clean, readable travel itinerary with:
1. **Trip Overview** — destination, dates, travelers, total budget estimate
2. **Recommended Flight** — pick the best option with justification
3. **Recommended Hotel** — pick the best option with justification
4. **Weather & What to Pack** — key points from climate analysis
5. **Day-by-Day Itinerary** — morning / afternoon / evening activities for each day
6. **Budget Breakdown** — flights, hotel, food, activities, total estimate
7. **Practical Tips** — visa, currency, local customs, transport

Be specific, enthusiastic, and helpful. Use markdown formatting."""


class PlanningAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def create_plan_stream(
        self,
        dto: TravelDTO,
        flight_result: dict,
        hotel_result: dict,
        climate_result: dict,
    ) -> AsyncIterator[str]:
        """Stream the full travel plan."""
        context = (
            f"## Traveler Requirements\n{dto.model_dump_json(indent=2)}\n\n"
            f"## Flight Search Results\n{json.dumps(flight_result, indent=2)}\n\n"
            f"## Hotel Search Results\n{json.dumps(hotel_result, indent=2)}\n\n"
            f"## Climate Analysis\n{json.dumps(climate_result, indent=2)}"
        )

        async with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
