# AgriConnect AI

AgriConnect AI is a two-sided agricultural marketplace connecting farmers and customers via an intelligent AI negotiation engine. The platform empowers farmers to sell their produce easily through voice-based AI interactions (supporting regional languages like Telugu) while automating fair price negotiations based on real market rates.

## Architecture & Tech Stack

### 1. Backend (`backend/`)
A high-performance Python API handling business logic, database ORM, and AI interactions.
- **Framework:** FastAPI (Python 3.11)
- **Database:** PostgreSQL (via SQLAlchemy asyncpg) + Alembic for migrations
- **Caching & Real-time:** Redis (for cache and WebSocket pub/sub)
- **AI Gateway:** Groq API (LLM intent extraction and conversational responses), Faster-Whisper (Speech-to-Text), Vision models for crop grading.
- **Auth:** JWT tokens (Farmer vs Customer roles)

### 2. Farmer App (`frontend-farmer/`)
A mobile-first React application designed for ease of use in rural areas.
- **Framework:** React + Vite
- **Styling:** Tailwind CSS (v4)
- **State Management:** Zustand
- **Key Features:** Voice-based listing creation, real-time AI negotiation interface, deal history tracking (History vs Accepted Deals), and photo grading via Vision API.

### 3. Customer App (`frontend-customer/`)
A consumer-facing marketplace application for buyers to browse catalog items and place orders.

### 4. Admin Dashboard (`admin-dashboard/`)
A management panel strictly used by marketplace operators to manually set the official daily base prices for crops across different regions.

---

## Core System Mechanics

### Voice-Powered Listings (STT & LLM)
Farmers can tap a microphone and speak in natural language. The system uses local Whisper to transcribe the audio and sends it to the LLM Gateway. The AI extracts the specific produce name, quantity, and unit, standardizing it into an English-based product catalog entry.

### AI Negotiation Engine
Instead of manually negotiating with every buyer, the AI acts as a broker:
1. **Strict Admin Pricing:** The Negotiation Engine strictly relies on base prices set in the Admin Panel (`price_table`). If a crop has not been priced by an Admin, the AI gracefully halts the conversation and informs the farmer.
2. **Dynamic Ceilings:** The engine calculates an Effective Price (EP) ceiling based on the Admin's base price, the platform margin (e.g., 12%), and a quality multiplier.
3. **Multi-Round Bidding:** The AI ethically evaluates farmer asks over up to 3 rounds. It strategically counters overbids while recording decisions into the `negotiation_sessions` table.

### Real-Time Interactions
All negotiations are strictly state-managed in PostgreSQL and broadcasted in real-time to the React frontends via WebSockets, allowing the UI to instantly reflect AI counter-offers.

---

## How to Start the Project

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/agriconnect-ai.git
   cd agriconnect-ai
   ```
2. Ensure Docker, Python 3.11, Node.js, and `uv` are installed on your machine.
3. Copy `.env.example` to `.env` in the root directory and add your real API keys.
4. Start the core database and caching infrastructure by running:
   `docker compose up -d`
5. **To start the backend:** Navigate to `backend/`, run `uv sync`, apply migrations with `alembic upgrade head`, and start the server using:
   `uv run uvicorn app.main:app --reload --port 8000`
6. **To start the frontends:** Navigate to `frontend-farmer`, `frontend-customer`, or `admin-dashboard`, run `npm install`, and start them with `npm run dev`.

---

## Environment Variables

For the system to function correctly, your root `.env` file must include the following core variables:
- `DATABASE_URL`: Connection string to PostgreSQL (e.g., `postgresql+asyncpg://user:pass@localhost:5432/agriconnect`).
- `REDIS_URL`: Connection string to Redis.
- `GROQ_API_KEY`: Your API key for the LLM Gateway.
- `JWT_SECRET_KEY`: Secret used for signing authentication tokens.

## Running Tests

The backend includes a comprehensive testing suite configured with Pytest. To run the tests:
1. Navigate to the `backend/` directory.
2. Run the test suite:
   ```bash
   uv run pytest
   ```

## Project Structure

```text
agriconnect-ai/
├── backend/               # FastAPI backend, SQLAlchemy models, AI services
│   ├── app/               # Core application code (routers, services, websockets)
│   ├── alembic/           # Database migration scripts
│   └── tests/             # Pytest testing suite
├── frontend-farmer/       # React App: Voice listings, live negotiations
├── frontend-customer/     # React App: Buyer browsing & checkout
├── admin-dashboard/       # React App: Manual market price seeding
├── docker-compose.yml     # Infrastructure (Postgres, Redis, MinIO)
└── README.md              # Project documentation
```
