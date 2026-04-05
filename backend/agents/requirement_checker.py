"""
Requirement Checker Agent
Extracts travel requirements from the conversation and builds/updates the TravelDTO.
Uses claude-haiku-4-5 for fast, focused extraction.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from models.travel_dto import TravelDTO

SYSTEM_PROMPT = """You are a travel requirement extraction assistant.

Your job: extract travel details from the user's message and return ONLY a JSON object.

Extract any of these fields if mentioned:
- destination (string)
- origin (string)
- start_date (string, convert to YYYY-MM-DD)
- end_date (string, convert to YYYY-MM-DD)
- adults (integer)
- kids (integer)
- total_budget (float)
- currency (string, default "USD")
- purpose (leisure/business/adventure/family/honeymoon)
- hotel_type (budget/mid-range/luxury)
- room_type (single/double/suite)
- location_preference (string)
- preferred_hotel_name (string - specific hotel brand/chain like "Marriott", "Hilton", or "any")
- preferred_airline (string - specific airline like "Emirates", "Delta", or "any")
- interests (array of strings)
- activity_level (relaxed/balanced/packed)
- preferred_weather (string)
- rain_ok (boolean)
- diet (string)
- has_elderly (boolean)

Return ONLY this JSON structure (no markdown, no explanation):
{
  "extracted": {
    "destination": null,
    "origin": null,
    "start_date": null,
    "end_date": null,
    "adults": null,
    "kids": null,
    "total_budget": null,
    "currency": null,
    "purpose": null,
    "hotel_type": null,
    "room_type": null,
    "location_preference": null,
    "preferred_hotel_name": null,
    "preferred_airline": null,
    "interests": null,
    "activity_level": null,
    "preferred_weather": null,
    "rain_ok": null,
    "diet": null,
    "has_elderly": null
  }
}

Only include fields that were explicitly mentioned. Use null for anything not mentioned."""


class RequirementCheckerAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def extract(self, user_message: str, current_dto: TravelDTO) -> TravelDTO:
        """Extract travel requirements from a user message and merge into the DTO."""
        response = await self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        try:
            data = json.loads(text)
            extracted = data.get("extracted", {})
        except json.JSONDecodeError:
            return current_dto

        # Merge extracted fields into the existing DTO
        dto_dict = current_dto.model_dump()

        if extracted.get("destination"):
            dto_dict["destination"] = extracted["destination"]
        if extracted.get("origin"):
            dto_dict["origin"] = extracted["origin"]
        if extracted.get("start_date"):
            dto_dict["start_date"] = extracted["start_date"]
        if extracted.get("end_date"):
            dto_dict["end_date"] = extracted["end_date"]

        if extracted.get("adults") is not None:
            dto_dict["travelers"]["adults"] = int(extracted["adults"])
        if extracted.get("kids") is not None:
            dto_dict["travelers"]["kids"] = int(extracted["kids"])

        if extracted.get("total_budget") is not None:
            dto_dict["budget"]["total"] = float(extracted["total_budget"])
        if extracted.get("currency"):
            dto_dict["budget"]["currency"] = extracted["currency"]

        if extracted.get("purpose"):
            dto_dict["purpose"] = extracted["purpose"]

        if extracted.get("hotel_type"):
            dto_dict["preferences"]["hotel_type"] = extracted["hotel_type"]
        if extracted.get("room_type"):
            dto_dict["preferences"]["room_type"] = extracted["room_type"]
        if extracted.get("location_preference"):
            dto_dict["preferences"]["location_preference"] = extracted["location_preference"]
        if extracted.get("preferred_hotel_name"):
            dto_dict["preferences"]["preferred_hotel_name"] = extracted["preferred_hotel_name"]
        if extracted.get("preferred_airline"):
            dto_dict["preferences"]["preferred_airline"] = extracted["preferred_airline"]
        if extracted.get("interests"):
            dto_dict["preferences"]["interests"] = extracted["interests"]
        if extracted.get("activity_level"):
            dto_dict["preferences"]["activity_level"] = extracted["activity_level"]

        if extracted.get("preferred_weather"):
            dto_dict["climate"]["preferred_weather"] = extracted["preferred_weather"]
        if extracted.get("rain_ok") is not None:
            dto_dict["climate"]["rain_ok"] = bool(extracted["rain_ok"])

        if extracted.get("diet"):
            dto_dict["constraints"]["diet"] = extracted["diet"]
        if extracted.get("has_elderly") is not None:
            dto_dict["constraints"]["has_elderly"] = bool(extracted["has_elderly"])

        return TravelDTO(**dto_dict)
