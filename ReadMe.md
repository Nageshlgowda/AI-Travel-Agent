building an AI Travel Agent platform that works as a multi-agent system. A user interacts through a chat-based web UI, and an orchestrator coordinates multiple AI agents. First, a Requirement Checker extracts and structures travel details into a DTO. Then a Planning Agent creates a complete travel itinerary, including suggested flights, hotels, and activity plans. A Flight Booking Agent searches and ranks flight options using external APIs, while a Hotel Booking Agent does the same for accommodations based on budget and preferences. A Climate Agent analyzes weather conditions for the travel dates and provides recommendations. Finally, the orchestrator collects all outputs and asks for user confirmation before proceeding with booking flights and hotels, ensuring a smooth, intelligent, and interactive travel planning experience.
AI travel agent chat

User (Flash Web UI)
        ↓
Agent Orchestrator (Brain)
        ↓
 ├── Requirement Checker Agent (DTO builder)
 ├── Planning Agent (Itinerary creator)
 ├── Hotel Booking Agent (Search & ranking)
 └── Climate Agent (Weather analysis)



1. What requirements should AI collect?
A. Trip Basics (Mandatory)
Destination (city/country)
Start date
End date
Number of travelers (adult/kids)
Origin location (optional but useful)

B. Budget Details
Total budget
Budget per person (optional)
Currency (USD, INR, etc.)

C. Travel Purpose
Leisure / Business / Adventure / Family / Honeymoon
Trip priority:
Relaxation
Exploration
Luxury
Budget travel

D. Accommodation Preferences
Hotel type:
Budget / Mid-range / Luxury
Room type:
Single / Double / Suite
Preferences:
Beach view
City center
Near airport    

E. Activity Preferences
Interests:
Beaches
Mountains
Nightlife
Shopping
Historical places
Food tours
Activity intensity:
Relaxed / Balanced / Packed schedule

Climate Preferences
Preferred weather:
Sunny / Cold / Moderate
Weather sensitivity:
Can travel in rain? (yes/no)

G. Constraints & Special Needs
Visa required? (yes/no/unknown)
Dietary restrictions (veg/non-veg/vegan)
Mobility constraints
Kids/elderly travelers
Safety concerns

FINAL IDEAL DTO

{
  "destination": "Goa",
  "origin": "New York",
  "start_date": "2026-05-10",
  "end_date": "2026-05-15",
  "travelers": {
    "adult ": 2,
    "kids": 2
  }

  "budget": {
    "total": 1200,
    "currency": "USD"
  },

  "purpose": "leisure",

  "preferences": {
    "hotel_type": "mid-range",
    "room_type": "double",
    "location_preference": "beachfront",

    "interests": ["beach", "nightlife", "food"],
    "activity_level": "balanced"
  },

  "climate": {
    "preferred_weather": "sunny",
    "rain_ok": true
  },

  "constraints": {
    "visa_required": "unknown",
    "diet": "non-veg",
    "kids": false,
    "elderly": false
  }
}

2. Planning Agent

You are an AI Travel Planning Agent inside a multi-agent system.

Your responsibilities:
1. Validate the input DTO (travel requirements)
2. If required fields are missing, DO NOT create a plan
   → Instead, return a "NEED_MORE_INFO" response with questions
3. If DTO is complete, generate a full travel plan

---

REQUIRED DTO FIELDS CHECK

Mandatory fields:
- destination
- start_date
- end_date
- travelers
- budget

Optional but useful:
- preferences (hotel type, interests, activity level)
- origin
- climate preferences

---

CASE 1: INCOMPLETE DTO

If any mandatory field is missing:

Return ONLY JSON:

{
  "status": "NEED_MORE_INFO",
  "missing_fields": [],
  "questions": [
    "Ask user for missing details in simple travel-agent style questions"
  ]
}

Rules:
- Be concise
- Do NOT generate itinerary
- Only ask missing questions

---

CASE 2: COMPLETE DTO

If all mandatory fields exist:

Create a complete travel plan including:

1. Flight suggestion (logical, not real booking)
2. Hotel recommendation summary
3. Weather/climate summary
4. Day-by-day itinerary
5. Budget breakdown

---
 OUTPUT FORMAT (COMPLETE CASE ONLY)

Return ONLY JSON:

{
  "status": "READY",
  "flight_plan": {
    "description": "",
    "estimated_cost": "",
    "notes": ""
  },

  "hotel_plan": {
    "category": "",
    "suggestions": [],
    "estimated_cost_per_night": ""
  },

  "climate_plan": {
    "summary": "",
    "risk_level": "",
    "advice": []
  },

  "itinerary": {
    "day_1": [],
    "day_2": [],
    "day_3": []
  },

  "budget_breakdown": {
    "flights": "",
    "hotels": "",
    "food": "",
    "activities": "",
    "total_estimate": ""
  },

  "summary": ""
}

---

RULES

- Always respond in JSON only
- Never include explanations
- If missing data → ask questions only
- If complete → produce full structured travel plan
- Ensure realistic travel logic (budget-aware, date-aware)

---

SYSTEM ROLE

You are NOT booking real services.
You are ONLY planning and simulating travel decisions for downstream agents.

Your Planning Agent should:

🧠 Think + Decide
🔧 Call tools (APIs)
📦 Combine results into a plan

User
 ↓
Requirement Checker (DTO)
 ↓
Planning Agent (LLM Brain)
 ↓
TOOL CALLS (APIs)
   ├── Flight API
   ├── Hotel API
   ├── Weather API
 ↓
Data returned
 ↓
LLM composes final plan
 ↓
Orchestrator returns response
 ↓
 confirm with user 

 3. Book Flight agent

 DTO → Validate input
   ↓
Call flight search API
   ↓
Filter by budget
   ↓
Rank flights
   ↓
Select top 3 options
   ↓
Return structured recommendation


{
  "status": "SUCCESS",
  "selected_flights": [
    {
      "airline": "",
      "price": "",
      "duration": "",
      "stops": "",
      "departure_time": "",
      "arrival_time": ""
    }
  ],
  "best_choice": {
    "reason": "",
    "flight_index": 0
  },
  "notes": ""
}

4. AI Booking Hotels Agent
DTO Input
   ↓
Validate required fields
   ↓
Search hotels API
   ↓
Filter by budget
   ↓
Score by preferences
   ↓
Rank results
   ↓
Return top 3–5 hotels

5. after user confirms book both flight and hotel and return deatils to user 




  ---
  Project Structure

  AI Travel Agent/
  ├── requirements.txt
  ├── .env.example
  ├── backend/
  │   ├── main.py              ← FastAPI + SSE streaming server
  │   ├── orchestrator.py      ← State machine (COLLECTING → PLANNING → CONFIRMING → BOOKING)
  │   ├── models/travel_dto.py ← Pydantic DTO with validation
  │   ├── tools/
  │   │   ├── flight_search.py ← Mock flight API (swap with Amadeus/Skyscanner)
  │   │   ├── hotel_search.py  ← Mock hotel API (swap with Booking.com)
  │   │   └── weather_api.py   ← Mock weather API (swap with OpenWeatherMap)
  │   └── agents/
  │       ├── requirement_checker.py ← claude-haiku-4-5, JSON extraction
  │       ├── flight_agent.py        ← claude-haiku-4-5 + tool use loop
  │       ├── hotel_agent.py         ← claude-haiku-4-5 + tool use loop
  │       ├── climate_agent.py       ← claude-haiku-4-5 + tool use loop
  │       └── planning_agent.py      ← claude-opus-4-6 + adaptive thinking, streaming
  └── frontend/index.html      ← Self-contained chat UI (no build step)

  How to Run

  # 1. Install dependencies
  pip install -r requirements.txt

  # 2. Set your API key
  cp .env.example .env
  # edit .env and add: ANTHROPIC_API_KEY=sk-ant-...

  # 3. Start the server
  cd backend
  uvicorn main:app --reload --port 8000

  # 4. Open http://localhost:8000

  Architecture

  ┌─────────────────────┬─────────────────────────────────────┬─────────────────────────────────────────────────────────┐
  │        Agent        │                Model                │                          Role                           │
  ├─────────────────────┼─────────────────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Requirement Checker │ claude-haiku-4-5                    │ Extracts DTO fields from natural language               │
  ├─────────────────────┼─────────────────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Flight Agent        │ claude-haiku-4-5 + tool use         │ Searches & ranks flights                                │
  ├─────────────────────┼─────────────────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Hotel Agent         │ claude-haiku-4-5 + tool use         │ Searches & ranks hotels                                 │
  ├─────────────────────┼─────────────────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Climate Agent       │ claude-haiku-4-5 + tool use         │ Analyzes weather & gives advice                         │
  ├─────────────────────┼─────────────────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Planning Agent      │ claude-opus-4-6 + adaptive thinking │ Synthesizes everything into a full itinerary (streamed) │
  ├─────────────────────┼─────────────────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Orchestrator        │ claude-opus-4-6                     │ Natural conversation driver & state machine             │