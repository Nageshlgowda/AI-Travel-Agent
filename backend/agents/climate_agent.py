"""
Climate Agent
Analyzes weather conditions for the travel dates and provides packing/activity recommendations.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from models.travel_dto import TravelDTO
from tools.weather_api import get_weather

SYSTEM_PROMPT = """You are a Climate & Weather Analysis Agent for travel planning.
1. Call the get_weather tool for the destination
2. Analyze the forecast and assess travel conditions
3. Return your analysis as JSON

Return ONLY a JSON object (no markdown):
{
  "status": "SUCCESS",
  "destination": "...",
  "period": "...",
  "climate_summary": "2-3 sentence summary of weather conditions",
  "risk_level": "LOW | MEDIUM | HIGH",
  "temperature": {"high_c": 0, "low_c": 0, "note": "..."},
  "rain_assessment": "...",
  "uv_note": "...",
  "packing_list": ["item1", "item2"],
  "activity_advice": {
    "best_for": ["activity1", "activity2"],
    "avoid": ["activity3"],
    "best_time_of_day": "..."
  },
  "overall_verdict": "Great time to visit | Acceptable | Challenging conditions"
}"""

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get weather forecast and travel climate analysis for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["city", "start_date", "end_date"],
        },
    }
]


class ClimateAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def analyze(self, dto: TravelDTO) -> dict:
        """Run climate analysis agentic loop and return weather recommendations."""
        prompt = (
            f"Analyze weather for this trip:\n"
            f"- Destination: {dto.destination}\n"
            f"- Dates: {dto.start_date} to {dto.end_date}\n"
            f"- Preferred weather: {dto.climate.preferred_weather or 'any'}\n"
            f"- Rain sensitivity: {'avoids rain' if not dto.climate.rain_ok else 'rain is fine'}\n"
            f"- Activities planned: {', '.join(dto.preferences.interests) or 'general sightseeing'}"
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
                    return {"status": "ERROR", "message": "Could not parse climate results"}

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use" and block.name == "get_weather":
                        result = get_weather(**block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
