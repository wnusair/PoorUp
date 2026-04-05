# PoorUp

A multiplayer economic-political strategy game. Roll dice. Build empires. Topple governments.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · Flask · Flask-SocketIO · eventlet |
| Database | PostgreSQL 16 |
| Cache / Sessions | Redis 7 |
| Frontend | React 18 · Vite · Tailwind CSS · Socket.IO client |
| Real-time | Flask-SocketIO (WebSocket + polling) |

---

## Quick Start (Docker)

```bash
# 1. Clone / enter the repo
cd PoorUp

# 2. Copy env file
cp backend/.env.example backend/.env
# Edit backend/.env if needed (defaults work with docker-compose)

# 3. Start everything
docker-compose up --build

# Frontend → http://localhost:5173
# Backend  → http://localhost:5000
# DB       → localhost:5432  (user: postgres / pass: postgres / db: poorup)
```

This compose file is the local development stack. It runs the Vite dev server and exposes the backend directly on port 5000.

## Production Deployment

For a Debian host behind the domain `poorup.wnusair.org`, use the production compose file instead:

```bash
cd PoorUp

cp backend/.env.example backend/.env
# Set a real SECRET_KEY before starting.

export POSTGRES_PASSWORD='replace-this-with-a-real-password'

docker compose -f docker-compose.prod.yml up -d --build
```

Production behavior:

- The frontend is built once and served by Nginx on port 80.
- Nginx proxies `/api` and `/socket.io` to the backend container.
- The backend runs with `FLASK_ENV=production` and no dev reloader.
- PostgreSQL and Redis stay internal to Docker and are not published publicly.

Point the DNS A record for `poorup.wnusair.org` at your Debian server before starting the stack. If you want HTTPS, terminate TLS on the host with Nginx, Caddy, or another reverse proxy in front of this stack, or extend the included Nginx config with your certificates.

---

## Manual Setup (without Docker)

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 running locally
- Redis 7 running locally

### Backend

```bash
cd backend

# Create virtualenv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Copy env
cp .env.example .env
# Edit DATABASE_URL and REDIS_URL to match your local setup

# Create the database
psql -U postgres -c "CREATE DATABASE poorup;"
psql -U postgres -d poorup -f migrations/001_initial_schema.sql

# Run
python app.py
```

### Frontend

```bash
cd frontend

npm install

# Copy env
cp .env.example .env
# VITE_API_URL=http://localhost:5000/api
# VITE_SOCKET_URL=http://localhost:5000

npm run dev
# → http://localhost:5173
```

---

## Game Modes

| Mode | Description |
|---|---|
| `standard` | Full PoorUp ruleset — all political/economic systems active |
| `classic` | Stripped-down Monopoly rules only |
| `chaos` | All modifiers randomized every round |
| `sandbox` | No win condition |

## Government Types

| Type | Tax | Welfare | Stability |
|---|---|---|---|
| Minarchism | 5% (flat) | $0 (locked) | Starts high, decays fast |
| Liberal Democracy | 15–25% | $10–50/round | Moderate fluctuation |
| Social Democracy | 40–50% | $60–100/round | Starts low, recovers |

---

## Project Structure

```
PoorUp/
  backend/
    app/
      routes/        # auth, lobby, game, admin
      sockets/       # Socket.IO event handlers
      models/        # SQLAlchemy models
      engine/        # game_loop, economy, events, uprising
      utils/         # dice, color_utils, profanity_filter
    migrations/      # SQL DDL + seed data
    app.py           # Entry point
    config.py        # Configuration
  frontend/
    src/
      components/    # Board, Game, Log, Trade, Team, Modals, Auction, Auth, Lobby
      pages/         # HomePage, LobbyPage, GamePage
      hooks/         # useSocket, useGameState, useAuth
      utils/         # api, constants, formatters
  docker-compose.yml
```

---

## API Reference

### Auth
```
POST /api/auth/register    { username, password }
POST /api/auth/login       { username, password }
POST /api/auth/logout
GET  /api/auth/me
```

### Lobby
```
POST  /api/lobby/create
POST  /api/lobby/join                    { room_code }
GET   /api/lobby/<room_code>
PATCH /api/lobby/<room_code>/settings    { ...settings }
POST  /api/lobby/<room_code>/start
```

### Game
```
GET   /api/game/<id>/state
POST  /api/game/<id>/roll
POST  /api/game/<id>/buy
POST  /api/game/<id>/decline
POST  /api/game/<id>/develop             { property_id }
POST  /api/game/<id>/mortgage            { property_id }
POST  /api/game/<id>/unmortgage          { property_id }
POST  /api/game/<id>/trade               { receiver_id, offered_money, ... }
PATCH /api/game/<id>/trade/<tid>         { action: accept|reject|counter }
POST  /api/game/<id>/lobby               { policy_id, contribution }
POST  /api/game/<id>/team/create         { team_name, team_color }
POST  /api/game/<id>/team/invite         { target_player_id }
PATCH /api/game/<id>/team/respond        { team_id, accept }
DEL   /api/game/<id>/team
GET   /api/game/<id>/log
POST  /api/game/<id>/jail/pay
POST  /api/game/<id>/jail/card
```

## Socket.IO Events

All real-time events are listed in `INSTRUCTIONS.md` §24. Key events:

| Direction | Event | Description |
|---|---|---|
| S→C | `game_start` | Game initialized |
| S→C | `turn_start` | New player's turn |
| S→C | `dice_rolled` | Dice result |
| S→C | `uprising_event` | Uprising triggered |
| S→C | `hyper_inflation_alert` | Round 50+ inflation |
| C→S | `roll_dice` | Roll dice |
| C→S | `buy_property` | Purchase property |
| C→S | `auction_bid` | Place auction bid |
