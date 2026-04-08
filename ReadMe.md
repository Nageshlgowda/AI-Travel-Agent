# Tripzy — AI Travel Agent

An AI-powered travel planning assistant that chats with you, searches flights and hotels, checks the weather, and generates a complete day-by-day itinerary — all through a simple chat interface.

---

## How It Works

You describe your trip in plain English. Behind the scenes, a team of specialized AI agents work together:

1. **Requirement Checker** — Reads your message and extracts trip details (destination, dates, budget, travelers) into a structured format. Asks follow-up questions if anything is missing.
2. **Flight Agent** — Searches for flights matching your route and budget, ranks the best options.
3. **Hotel Agent** — Searches for hotels matching your preferences and budget, ranks top picks.
4. **Climate Agent** — Checks weather conditions for your destination and travel dates, gives packing/planning advice.
5. **Planning Agent** — Combines everything into a full day-by-day itinerary with a budget breakdown.
6. **Orchestrator** — Drives the conversation, manages state, and asks for your confirmation before booking.

```
You (Chat UI)
     ↓
Orchestrator
     ↓
Requirement Checker → extracts trip DTO
     ↓
Flight Agent + Hotel Agent + Climate Agent  (run in parallel)
     ↓
Planning Agent → generates full itinerary
     ↓
Confirm with user → Book flight + hotel → Show confirmation
```

---

## Tech Stack

| Layer     | Technology                                      |
|-----------|-------------------------------------------------|
| Frontend  | Vanilla HTML / CSS / JavaScript (no build step) |
| Backend   | Python, FastAPI, Server-Sent Events (streaming) |
| AI Models | Anthropic Claude (Haiku + Opus)                 |
| Weather   | OpenWeatherMap API                              |
| WhatsApp  | Twilio WhatsApp Sandbox                         |
| Deploy    | Railway                                         |

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Required for weather data
OPENWEATHER_API_KEY=your_key_here

# Optional — only needed for WhatsApp integration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_NUMBER=+14155238886
```

---

## Run Locally

**1. Clone the repo and install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set up environment variables**

```bash
cp .env.example .env
# Open .env and fill in your API keys
```

**3. Start the server**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**4. Open the app**

Go to [http://localhost:8000](http://localhost:8000) in your browser.

---

## Deploy on Railway

**1. Push your code to GitHub**

**2. Create a new Railway project**
- Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo

**3. Add environment variables**

In your Railway project → Variables, add:
```
ANTHROPIC_API_KEY
OPENWEATHER_API_KEY
TWILIO_ACCOUNT_SID       (optional)
TWILIO_AUTH_TOKEN        (optional)
TWILIO_WHATSAPP_FROM     (optional)
WHATSAPP_NUMBER          (optional)
```

**4. Deploy**

Railway auto-detects the `railway.toml` config and runs:
```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

Your app will be live at the Railway-provided URL within a minute.

---

## Project Structure

```
AI Travel Agent/
├── requirements.txt
├── railway.toml
├── .env
├── frontend/
│   ├── index.html       — Chat UI (markup only)
│   ├── style.css        — All styles
│   ├── app.js           — All frontend logic
│   └── assets/          — Logo and favicon
└── backend/
    ├── main.py              — FastAPI server, SSE streaming, static file routes
    ├── orchestrator.py      — Conversation state machine
    ├── models/
    │   └── travel_dto.py    — Pydantic travel data model
    ├── tools/
    │   ├── flight_search.py — Flight search (mock / swap with Amadeus)
    │   ├── hotel_search.py  — Hotel search (mock / swap with Booking.com)
    │   └── weather_api.py   — Weather via OpenWeatherMap
    └── agents/
        ├── requirement_checker.py — Extracts trip details from conversation
        ├── flight_agent.py        — Searches and ranks flights
        ├── hotel_agent.py         — Searches and ranks hotels
        ├── climate_agent.py       — Weather analysis and advice
        └── planning_agent.py      — Generates full itinerary (streamed)
```
