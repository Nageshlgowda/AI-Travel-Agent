"""
Travel Orchestrator
Manages session state, coordinates agents, and drives the conversation flow.

States:
  COLLECTING   → Gathering mandatory fields via multi-turn conversation
  PREFERENCES  → Asking about purpose, hotel type, airline/hotel preferences (one round)
  PLANNING     → Running all agents in parallel, streaming the plan
  CONFIRMING   → Waiting for user to confirm or modify
  BOOKING      → Executing flight + hotel bookings
  DONE         → Completed
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import anthropic
from models.travel_dto import TravelDTO
from agents.requirement_checker import RequirementCheckerAgent
from agents.flight_agent import FlightAgent
from agents.hotel_agent import HotelAgent
from agents.climate_agent import ClimateAgent
from agents.planning_agent import PlanningAgent
from tools.flight_search import book_flight
from tools.hotel_search import book_hotel
from typing import AsyncIterator

CONVERSATION_SYSTEM = """You are a friendly, knowledgeable AI travel agent.
Your job is to have a natural conversation with the traveler to collect their trip details.
Ask for only 1-2 things at a time — never overwhelm the user.
Be warm, professional, and excited about helping them plan their trip.
Do NOT output JSON. Respond naturally in plain text only."""

PREFERENCES_SYSTEM = """You are a friendly AI travel agent.
The traveler has provided all the essential trip details. Now ask them a few quick preference questions
to personalise the trip before you start searching.

Ask about ALL of these in one friendly message (but keep it concise and conversational):
1. Purpose of the trip — e.g. leisure, business, adventure, family, honeymoon
2. Hotel preference — type (budget/mid-range/luxury) and any specific chain they like (e.g. Marriott, Hilton)
3. Preferred airline — any favourite or specific airline, or no preference
4. Any other wishlist — activities, food interests, special requests

Frame it as "just a few quick questions to personalise your trip" before you start searching.
Do NOT output JSON. Respond naturally in plain text only."""


class TravelOrchestrator:
    def __init__(self):
        self.state = "COLLECTING"
        self.dto = TravelDTO()
        self.history: list[dict] = []
        self.flight_result: dict = {}
        self.hotel_result: dict = {}
        self.climate_result: dict = {}
        self.plan_text: str = ""
        self.best_flight_id: str = ""
        self.best_hotel_id: str = ""

        self.req_checker = RequirementCheckerAgent()
        self.flight_agent = FlightAgent()
        self.hotel_agent = HotelAgent()
        self.climate_agent = ClimateAgent()
        self.planning_agent = PlanningAgent()
        self.convo_client = anthropic.AsyncAnthropic()

    async def process(self, user_message: str) -> AsyncIterator[dict]:
        """Entry point — routes to the current state handler."""
        if self.state == "COLLECTING":
            async for event in self._handle_collecting(user_message):
                yield event
        elif self.state == "PREFERENCES":
            async for event in self._handle_preferences(user_message):
                yield event
        elif self.state == "CONFIRMING":
            async for event in self._handle_confirming(user_message):
                yield event
        elif self.state == "DONE":
            yield {"type": "text", "content": "Your trip is already booked! Is there anything else I can help you with?"}

    # ── COLLECTING ────────────────────────────────────────────────────────────

    async def _handle_collecting(self, user_message: str) -> AsyncIterator[dict]:
        self.history.append({"role": "user", "content": user_message})
        self.dto = await self.req_checker.extract(user_message, self.dto)
        yield {"type": "dto_update", "data": self.dto.model_dump()}

        if self.dto.is_complete():
            # Mandatory fields done — move to preference questions
            self.state = "PREFERENCES"
            async for event in self._ask_preferences():
                yield event
        else:
            async for event in self._ask_for_missing():
                yield event

    async def _ask_for_missing(self) -> AsyncIterator[dict]:
        """Ask naturally for remaining mandatory + nice-to-have fields."""
        missing = self.dto.missing_fields()
        nice_to_have = self.dto.unasked_nice_to_have()

        context = (
            f"Trip info so far:\n{self.dto.to_summary()}\n\n"
            f"Mandatory fields still needed: {', '.join(missing)}\n"
            + (f"Nice-to-have (ask alongside mandatory): {', '.join(nice_to_have)}\n" if nice_to_have else "")
            + "\nAsk the traveler for the missing info. Max 2 questions at once. "
            "Prioritise mandatory fields first."
        )

        full_response = ""
        async with self.convo_client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=512,
            system=CONVERSATION_SYSTEM,
            messages=self.history + [{"role": "user", "content": context}],
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield {"type": "text", "content": text}

        self.history.append({"role": "assistant", "content": full_response})

    # ── PREFERENCES ───────────────────────────────────────────────────────────

    async def _ask_preferences(self) -> AsyncIterator[dict]:
        """Ask one round of preference questions (purpose, hotel, airline, interests)."""
        context = (
            f"The traveler's confirmed trip details:\n{self.dto.to_summary()}\n\n"
            "Now ask them the preference questions listed in your instructions."
        )

        full_response = ""
        async with self.convo_client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=512,
            system=PREFERENCES_SYSTEM,
            messages=self.history + [{"role": "user", "content": context}],
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield {"type": "text", "content": text}

        self.history.append({"role": "assistant", "content": full_response})

    async def _handle_preferences(self, user_message: str) -> AsyncIterator[dict]:
        """Receive the user's preference answers, extract them, then start planning."""
        self.history.append({"role": "user", "content": user_message})
        self.dto = await self.req_checker.extract(user_message, self.dto)
        yield {"type": "dto_update", "data": self.dto.model_dump()}

        # Acknowledge and kick off planning
        yield {
            "type": "status",
            "message": "Got it! Searching for flights, hotels, and checking the weather now...",
        }
        self.state = "PLANNING"
        async for event in self._run_planning():
            yield event

    # ── PLANNING ──────────────────────────────────────────────────────────────

    async def _run_planning(self) -> AsyncIterator[dict]:
        """Run flight, hotel, climate agents in parallel then stream the full plan."""
        for agent in ["flight", "hotel", "climate"]:
            yield {"type": "agent_status", "agent": agent, "status": "running"}

        flight_task = asyncio.create_task(self.flight_agent.search(self.dto))
        hotel_task = asyncio.create_task(self.hotel_agent.search(self.dto))
        climate_task = asyncio.create_task(self.climate_agent.analyze(self.dto))

        self.flight_result, self.hotel_result, self.climate_result = await asyncio.gather(
            flight_task, hotel_task, climate_task, return_exceptions=True
        )

        if isinstance(self.flight_result, Exception):
            self.flight_result = {"status": "ERROR", "message": str(self.flight_result)}
        if isinstance(self.hotel_result, Exception):
            self.hotel_result = {"status": "ERROR", "message": str(self.hotel_result)}
        if isinstance(self.climate_result, Exception):
            self.climate_result = {"status": "ERROR", "message": str(self.climate_result)}

        yield {"type": "agent_result", "agent": "flight", "status": "done", "data": self.flight_result}
        yield {"type": "agent_result", "agent": "hotel", "status": "done", "data": self.hotel_result}
        yield {"type": "agent_result", "agent": "climate", "status": "done", "data": self.climate_result}

        self._cache_best_picks()

        yield {"type": "agent_status", "agent": "planning", "status": "running"}
        yield {"type": "plan_start"}

        self.plan_text = ""
        async for chunk in self.planning_agent.create_plan_stream(
            self.dto, self.flight_result, self.hotel_result, self.climate_result
        ):
            self.plan_text += chunk
            yield {"type": "text", "content": chunk}

        yield {"type": "agent_result", "agent": "planning", "status": "done", "data": {}}
        yield {"type": "plan_end"}

        self.state = "CONFIRMING"
        yield {
            "type": "confirm_prompt",
            "message": "Would you like me to **book this trip** (flight + hotel)? "
                       "Reply **'Yes, book it'** to confirm or tell me what you'd like to change.",
        }

    def _cache_best_picks(self):
        try:
            top_flights = self.flight_result.get("top_flights", [])
            if top_flights:
                self.best_flight_id = top_flights[0].get("flight_id", "")
        except Exception:
            pass
        try:
            top_hotels = self.hotel_result.get("top_hotels", [])
            if top_hotels:
                self.best_hotel_id = top_hotels[0].get("hotel_id", "")
        except Exception:
            pass

    # ── CONFIRMING ────────────────────────────────────────────────────────────

    async def _handle_confirming(self, user_message: str) -> AsyncIterator[dict]:
        msg_lower = user_message.lower()
        confirm_words = ["yes", "confirm", "book", "proceed", "go ahead", "do it", "sure", "ok", "okay"]

        if any(word in msg_lower for word in confirm_words):
            self.state = "BOOKING"
            async for event in self._execute_booking():
                yield event
        else:
            # User wants changes — re-extract and re-plan
            self.history.append({"role": "user", "content": user_message})
            self.dto = await self.req_checker.extract(user_message, self.dto)
            yield {"type": "dto_update", "data": self.dto.model_dump()}
            yield {
                "type": "status",
                "message": "Updating your plan with the changes...",
            }
            self.state = "PLANNING"
            async for event in self._run_planning():
                yield event

    # ── BOOKING ───────────────────────────────────────────────────────────────

    async def _execute_booking(self) -> AsyncIterator[dict]:
        yield {"type": "status", "message": "Booking your flight and hotel..."}

        total_pax = self.dto.travelers.adults + self.dto.travelers.kids
        passenger_names = [f"Traveler {i+1}" for i in range(total_pax)]

        flight_conf = book_flight(
            flight_id=self.best_flight_id or "FL001",
            passenger_names=passenger_names,
        )
        hotel_conf = book_hotel(
            hotel_id=self.best_hotel_id or "HTL001",
            guest_name=passenger_names[0],
            check_in=self.dto.start_date,
            check_out=self.dto.end_date,
        )

        self.state = "DONE"

        yield {
            "type": "booking_confirmation",
            "data": {
                "flight": flight_conf,
                "hotel": hotel_conf,
                "destination": self.dto.destination,
                "dates": f"{self.dto.start_date} → {self.dto.end_date}",
                "travelers": total_pax,
            },
        }
        yield {
            "type": "text",
            "content": (
                f"\n\n**Booking Confirmed!** 🎉\n\n"
                f"✈️ **Flight Reference:** `{flight_conf['booking_reference']}`\n"
                f"🏨 **Hotel Reference:** `{hotel_conf['booking_reference']}`\n\n"
                f"Have an amazing trip to **{self.dto.destination}**! "
                f"Your booking details have been saved above."
            ),
        }
