# PoorUp — Full Development Instructions

> **Stack:** Python (Flask) · PostgreSQL · Redis · React (or Vue.js) · Socket.IO  
> **Genre:** Economic-political board strategy (Monopoly-inspired)  
> **Version:** 1.0 — Full Feature Specification

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack & Architecture](#2-tech-stack--architecture)
3. [Database Schema & Relationships](#3-database-schema--relationships)
4. [Pre-Game Lobby System](#4-pre-game-lobby-system)
5. [The Game Board — World Map Properties](#5-the-game-board--world-map-properties)
6. [Player Identity & Customization](#6-player-identity--customization)
7. [Core Game Loop](#7-core-game-loop)
8. [Economic Systems & Government Types](#8-economic-systems--government-types)
9. [Dynamic Variables — Randomization & Live Updates](#9-dynamic-variables--randomization--live-updates)
10. [Rent Collection](#10-rent-collection)
11. [Taxation System](#11-taxation-system)
12. [Welfare & Stability System](#12-welfare--stability-system)
13. [Rage Multiplier & Uprising Events](#13-rage-multiplier--uprising-events)
14. [Chance & Community Chest Cards](#14-chance--community-chest-cards)
15. [Lobbying System](#15-lobbying-system)
16. [Trading System](#16-trading-system)
17. [Team System](#17-team-system)
18. [Auctions & Mortgages](#18-auctions--mortgages)
19. [The Game Log](#19-the-game-log)
20. [Late-Game Triggers](#20-late-game-triggers)
21. [Disconnect & Session Handling](#21-disconnect--session-handling)
22. [QOL — Visual Identity & UI Standards](#22-qol--visual-identity--ui-standards)
23. [Flask Route Map](#23-flask-route-map)
24. [Socket.IO Event Reference](#24-socketio-event-reference)
25. [Development Roadmap](#25-development-roadmap)
26. [Implementation Warnings & Gotchas](#26-implementation-warnings--gotchas)

---

## 1. Project Overview

**PoorUp** is a multiplayer economic strategy game modeled after Monopoly, but extended with a live political-economic simulation layer. Players roll dice, move around a world-map game board, buy and develop properties, pay taxes, collect rent, and interact with a dynamic government system that changes the rules of the game in real time.

Unlike vanilla Monopoly, PoorUp adds:

- A government type chosen at lobby creation that determines tax rates, welfare, and stability
- Dynamic inflation, interest rates, and stability variables that drift throughout the game
- Player lobbying to shape active policy
- Full team mechanics, including property sharing and immunity
- A public trade negotiation system visible to all players
- Uprising/revolution events triggered by economic inequality
- A complete pre-game lobby where the host can enable or disable nearly every mechanic

The game must feel like Monopoly at its base: roll dice, land on spaces, make decisions, pay fees. All math is automated and logged for all players to see.

---

## 2. Tech Stack & Architecture

### Backend — Flask

Use **Flask** with **Flask-SocketIO** for real-time communication. Flask handles all game logic, state transitions, and route endpoints.

```
/app
  /routes
    auth.py         # Login, register
    lobby.py        # Pre-game lobby management
    game.py         # In-game REST endpoints (trade offers, policy votes, etc.)
    admin.py        # Host controls
  /sockets
    game_events.py  # All Socket.IO event handlers
  /models
    player.py
    property.py
    government.py
    policy.py
    trade.py
    team.py
    card.py
    log.py
  /engine
    game_loop.py    # Turn processor
    economy.py      # Tax, rent, welfare, rage calculations
    events.py       # Chance/Community Chest card draw logic
    uprising.py     # Uprising trigger and resolution
  /utils
    color_utils.py
    profanity_filter.py
    dice.py
  config.py
  app.py
```

### Database

| Layer | Technology | Purpose |
|---|---|---|
| Persistent | **PostgreSQL** | Player accounts, match history, property records |
| Volatile | **Redis** | Active game state, turn queues, live variable cache |
| Sessions | Flask-Session (Redis) | Player session management |

### Frontend

- **React** (preferred) or Vue.js
- Component library: Tailwind CSS or Material UI
- Real-time: **Socket.IO client**
- Board rendering: SVG or HTML Canvas — the board is a rectangular loop of property tiles

### Real-Time Communication

All live game events (dice rolls, purchases, rent payments, trade proposals, uprisings, log entries) are broadcast via **Socket.IO** to every player in the room.

---

## 3. Database Schema & Relationships

### PostgreSQL Tables

#### `users`
```sql
id              SERIAL PRIMARY KEY
username        VARCHAR(12) UNIQUE NOT NULL   -- 12 char max, profanity filtered
password_hash   TEXT NOT NULL
created_at      TIMESTAMP
```

#### `matches`
```sql
id                  SERIAL PRIMARY KEY
room_code           VARCHAR(8) UNIQUE
host_user_id        INTEGER REFERENCES users(id)
government_type     VARCHAR(30)       -- 'minarchism' | 'liberal_democracy' | 'social_democracy'
status              VARCHAR(20)       -- 'lobby' | 'active' | 'completed'
settings_json       JSONB             -- All lobby toggles stored here
current_round       INTEGER DEFAULT 0
created_at          TIMESTAMP
```

#### `match_players`
```sql
id                  SERIAL PRIMARY KEY
match_id            INTEGER REFERENCES matches(id)
user_id             INTEGER REFERENCES users(id)
color_hex           VARCHAR(7)        -- e.g. '#E63946'
balance             NUMERIC(14,2)
influence_score     NUMERIC(8,2) DEFAULT 0
approval_rating     NUMERIC(5,2) DEFAULT 50.0
current_position    INTEGER DEFAULT 0
is_jailed           BOOLEAN DEFAULT FALSE
jail_turns_remaining INTEGER DEFAULT 0
team_id             INTEGER REFERENCES teams(id) NULLABLE
is_bankrupt         BOOLEAN DEFAULT FALSE
is_connected        BOOLEAN DEFAULT TRUE
```

#### `properties`
```sql
id              SERIAL PRIMARY KEY
match_id        INTEGER REFERENCES matches(id)
name            VARCHAR(60)
region          VARCHAR(40)           -- e.g. 'China', 'USA', 'Europe'
group_color     VARCHAR(7)            -- Color shared by the property set
board_position  INTEGER
base_price      NUMERIC(10,2)
current_value   NUMERIC(10,2)
dev_level       INTEGER DEFAULT 0     -- 0 = unimproved, 1-4 = buildings, 5 = hotel equiv
owner_id        INTEGER REFERENCES match_players(id) NULLABLE
is_mortgaged    BOOLEAN DEFAULT FALSE
```

#### `governments`
```sql
id                  SERIAL PRIMARY KEY
match_id            INTEGER REFERENCES matches(id) UNIQUE
gov_type            VARCHAR(30)
stability           NUMERIC(5,2)      -- 0.0 - 1.0
treasury_balance    NUMERIC(14,2)
welfare_payout      NUMERIC(10,2)
tax_multiplier      NUMERIC(5,3)
inflation_rate      NUMERIC(5,4)
interest_rate       NUMERIC(5,4)
```

#### `policies`
```sql
id              SERIAL PRIMARY KEY
match_id        INTEGER REFERENCES matches(id)
policy_name     VARCHAR(80)
target_stat     VARCHAR(40)       -- e.g. 'income_tax', 'welfare_payout', 'rent_multiplier'
effect_value    NUMERIC(8,4)
is_active       BOOLEAN DEFAULT FALSE
```

#### `lobbies` (active player contributions to policy)
```sql
id              SERIAL PRIMARY KEY
match_id        INTEGER REFERENCES matches(id)
policy_id       INTEGER REFERENCES policies(id)
player_id       INTEGER REFERENCES match_players(id)
contribution    NUMERIC(10,2)
```

#### `trades`
```sql
id              SERIAL PRIMARY KEY
match_id        INTEGER REFERENCES matches(id)
initiator_id    INTEGER REFERENCES match_players(id)
receiver_id     INTEGER REFERENCES match_players(id)
offered_money   NUMERIC(10,2) DEFAULT 0
requested_money NUMERIC(10,2) DEFAULT 0
offered_props   INTEGER[]     -- array of property IDs
requested_props INTEGER[]
status          VARCHAR(20)   -- 'pending' | 'accepted' | 'rejected' | 'countered' | 'cancelled'
created_at      TIMESTAMP
resolved_at     TIMESTAMP NULLABLE
```

#### `teams`
```sql
id              SERIAL PRIMARY KEY
match_id        INTEGER REFERENCES matches(id)
team_name       VARCHAR(30)
team_color      VARCHAR(7)
created_by      INTEGER REFERENCES match_players(id)
```

#### `game_log`
```sql
id          SERIAL PRIMARY KEY
match_id    INTEGER REFERENCES matches(id)
round       INTEGER
turn        INTEGER
player_id   INTEGER REFERENCES match_players(id) NULLABLE
event_type  VARCHAR(40)
description TEXT
timestamp   TIMESTAMP DEFAULT now()
```

#### `cards`
```sql
id              SERIAL PRIMARY KEY
deck_type       VARCHAR(20)   -- 'chance' | 'community_chest'
card_text       TEXT
effect_type     VARCHAR(40)
effect_value    NUMERIC(10,2) NULLABLE
```

### Redis Keys (Active Game State)

```
game:{match_id}:state         -- JSON blob of full live game state
game:{match_id}:turn_order    -- List of player IDs in turn order
game:{match_id}:current_turn  -- Player ID whose turn it is
game:{match_id}:dice          -- Last dice roll result
game:{match_id}:rage          -- Current rage multiplier
game:{match_id}:econ          -- Live economic variables JSON
game:{match_id}:log_buffer    -- Recent log entries (last 50)
```

---

## 4. Pre-Game Lobby System

Before any game begins, the **host** creates a room and a **lobby** is shown to all joining players. This lobby is where all game parameters are set.

### Lobby Features

#### Player Setup (per player)
- Choose a **display name** (12-char max, profanity-filtered at submission)
- Choose a **color** from the preset palette (see Section 22)
- Ready toggle

#### Host Controls — Game Configuration

All settings are stored in `matches.settings_json` as a JSONB object. Below is the full schema:

```json
{
  "starting_money": 1500,
  "government_type": "liberal_democracy",
  "game_mode": "standard",
  "auction_enabled": true,
  "mortgage_enabled": true,
  "teams_enabled": true,
  "uprisings_enabled": true,
  "tax_every_turn": false,
  "income_tax_on_pass_go": true,
  "property_tax_every_n_rounds": 5,
  "lobbying_enabled": true,
  "trading_enabled": true,
  "chance_cards_enabled": true,
  "community_chest_enabled": true,
  "hyper_inflation_trigger": true,
  "hyper_inflation_round": 50,
  "go_salary": 200,
  "max_players": 6,
  "turn_time_limit_seconds": 90,
  "allow_spectators": true,
  "rage_system_enabled": true,
  "welfare_system_enabled": true,
  "policy_voting_enabled": true,
  "jail_enabled": true,
  "free_parking_pot_enabled": false,
  "double_on_go": false
}
```

#### Game Mode Options

| Mode | Description |
|---|---|
| `standard` | Full PoorUp ruleset — all political/economic systems active |
| `classic` | Stripped-down Monopoly rules only, no government mechanics |
| `chaos` | All modifiers randomized every round |
| `sandbox` | No win condition, purely exploratory |

#### Lobby UI Flow

1. Host creates room → receives a 6-character room code
2. Players join via room code
3. Host sees all player slots, each showing color + name
4. Host configures settings via a settings panel (toggles, dropdowns, number inputs)
5. Host selects **Government Type** — this determines the entire economic template for the game
6. When all players are ready, host clicks **Start Game**
7. Server validates all settings, initializes game state, emits `game_start` to all clients

---

## 5. The Game Board — World Map Properties

The board is a rectangular loop of **48 spaces** organized into regional property groups. Each group has a shared `group_color`.

### Board Layout

Properties are grouped by world region. Within each region, there are 2–3 properties that share a color group. Owning all properties in a group enables development.

#### Full Property List

| Position | Name | Region | Group Color | Base Price |
|---|---|---|---|---|
| 0 | START | — | — | — |
| 1 | Lagos | Africa | `#8B4513` | 60 |
| 2 | Nairobi | Africa | `#8B4513` | 60 |
| 3 | Community Chest | — | — | — |
| 4 | Cairo | Africa | `#D2691E` | 100 |
| 5 | Income Tax | — | — | — |
| 6 | Mumbai Airport | Transit | `#808080` | 200 |
| 7 | Delhi | South Asia | `#FF69B4` | 100 |
| 8 | Chance | — | — | — |
| 9 | Karachi | South Asia | `#FF69B4` | 120 |
| 10 | Dhaka | South Asia | `#FF1493` | 140 |
| 11 | Jail / Just Visiting | — | — | — |
| 12 | Istanbul | Middle East | `#FFA500` | 140 |
| 13 | Tehran | Middle East | `#FFA500` | 160 |
| 14 | Riyadh | Middle East | `#FF8C00` | 180 |
| 15 | Dubai Airport | Transit | `#808080` | 200 |
| 16 | Moscow | Eastern Europe | `#FF0000` | 180 |
| 17 | Community Chest | — | — | — |
| 18 | St. Petersburg | Eastern Europe | `#FF0000` | 200 |
| 19 | Kiev | Eastern Europe | `#DC143C` | 220 |
| 20 | Free Space | — | — | — |
| 21 | Berlin | Western Europe | `#FFFF00` | 220 |
| 22 | Chance | — | — | — |
| 23 | Paris | Western Europe | `#FFFF00` | 240 |
| 24 | London | Western Europe | `#FFD700` | 260 |
| 25 | London Heathrow | Transit | `#808080` | 200 |
| 26 | Shanghai | China | `#FF4500` | 260 |
| 27 | Beijing | China | `#FF4500` | 280 |
| 28 | Chongqing | China | `#FF6347` | 300 |
| 29 | Community Chest | — | — | — |
| 30 | Go To Jail | — | — | — |
| 31 | Tokyo | East Asia | `#9400D3` | 300 |
| 32 | Seoul | East Asia | `#9400D3` | 320 |
| 33 | Chance | — | — | — |
| 34 | Sydney | Oceania | `#00CED1` | 320 |
| 35 | Melbourne | Oceania | `#00CED1` | 340 |
| 36 | JFK Airport | Transit | `#808080` | 200 |
| 37 | São Paulo | Latin America | `#006400` | 350 |
| 38 | Buenos Aires | Latin America | `#006400` | 370 |
| 39 | Luxury Tax | — | — | — |
| 40 | New York | North America | `#0000CD` | 400 |
| 41 | Los Angeles | North America | `#0000CD` | 400 |
| 42 | Community Chest | — | — | — |
| 43 | Chicago | North America | `#00008B` | 420 |
| 44 | Chance | — | — | — |
| 45 | Washington D.C. | North America | `#00008B` | 440 |
| 46 | Silicon Valley | North America | `#000080` | 450 |
| 47 | Super Tax | — | — | — |

> **China Note:** Shanghai, Beijing, and Chongqing are a **triple-property group** — all three must be owned before development is unlocked. This is intentional and makes China the hardest and most powerful monopoly on the board.

### Special Spaces

| Space | Effect |
|---|---|
| START (0) | Collect GO salary on pass. Income tax applied if setting enabled. |
| Jail (11) | Just visiting unless sent here. Requires 3 turns or bail payment to leave. |
| Free Space (20) | No effect. If Free Parking Pot is enabled, collect the pot. |
| Go To Jail (30) | Immediately move to position 11, do not collect GO salary. |
| Income Tax (5) | Pay configurable flat rate or % of net worth (whichever is higher). |
| Luxury Tax (39) | Flat fee automatically deducted. Scales with `tax_multiplier`. |
| Super Tax (47) | Higher flat fee. Scales with `tax_multiplier`. |
| Transit (6,15,25,36) | Airports — if opponent owns all 4, rent doubles per additional owned. |

---

## 6. Player Identity & Customization

### Username Rules
- Maximum **12 characters**
- Alphanumeric + underscores only
- Run through a profanity filter on submission. If flagged, return a `400` with the message `"Username not allowed."`
- Must be unique within the match

### Color System

Players select from a **preset palette** of high-contrast colors. No two players in the same match can share a color. The palette is:

```python
PLAYER_COLOR_PALETTE = [
    "#E63946",  # Crimson Red
    "#2196F3",  # Electric Blue
    "#4CAF50",  # Lime Green
    "#FF9800",  # Amber Orange
    "#9C27B0",  # Deep Purple
    "#00BCD4",  # Cyan
    "#F44336",  # Scarlet
    "#FFEB3B",  # Bright Yellow (dark text only)
    "#795548",  # Earthy Brown
    "#607D8B",  # Steel Blue-Grey
]
```

When a player selects a color in the lobby, it is immediately locked and removed from other players' available options via a Socket.IO `color_taken` broadcast.

### Color Application Rules
- Player token on the board renders in their `color_hex`
- All properties owned by the player get a **colored border/tab** in their `color_hex` on the property tile
- In the trade panel, sidebar, and leaderboard, the player's name renders with a small colored dot or background badge
- If a player is on a team, a **secondary badge** shows the team color alongside their personal color

---

## 7. Core Game Loop

### Turn Structure

Each turn follows this strict sequence:

```
1.  START_TURN          → Emit turn_start event to all players
2.  ROLL_DICE           → Player rolls (or timeout auto-rolls)
3.  MOVE                → Move token N spaces forward
4.  LAND_RESOLUTION     → Resolve the space landed on (buy, rent, card, tax, jail, etc.)
5.  MANDATORY_TAXES     → Apply any per-turn taxes based on settings (income tax if tax_every_turn)
6.  ECONOMIC_UPDATE     → Drift inflation, interest rate, stability by small random delta
7.  RAGE_CALCULATION    → Recalculate Rage Multiplier
8.  UPRISING_CHECK      → If rage > threshold AND uprisings enabled, trigger uprising
9.  POLICY_APPLY        → Apply any pending lobbying results
10. LOG_FLUSH           → Push all events from this turn to game_log and broadcast to clients
11. CHECK_BANKRUPTCY    → Check all players for bankruptcy condition
12. CHECK_WIN           → Check win condition (last player standing, or round limit)
13. END_TURN            → Advance turn to next player
```

### Dice Rolling

```python
import random

def roll_dice():
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    is_doubles = (d1 == d2)
    return d1, d2, is_doubles
```

- Rolling **doubles** grants an extra turn
- Rolling doubles **3 times in a row** sends the player to Jail
- Track `consecutive_doubles` per player in Redis state

### Movement

```python
def move_player(current_position, roll, board_size=48):
    new_position = (current_position + roll) % board_size
    passed_go = new_position < current_position  # Wrapped around the board
    return new_position, passed_go
```

If `passed_go` is `True`, award the GO salary and apply income tax if the setting is enabled.

### Space Resolution Logic

```python
def resolve_space(player, position, game_state):
    space = game_state['board'][position]
    
    if space['type'] == 'property':
        if space['owner_id'] is None:
            prompt_buy_or_auction(player, space, game_state)
        elif space['owner_id'] == player['id']:
            log("Landed on own property. No action.")
        elif is_team_immune(player, space['owner_id'], game_state):
            log("Team immunity. No rent charged.")
        elif space['is_mortgaged']:
            log("Property is mortgaged. No rent.")
        else:
            collect_rent(player, space, game_state)
    
    elif space['type'] == 'tax':
        apply_tax(player, space, game_state)
    
    elif space['type'] == 'chance':
        draw_chance_card(player, game_state)
    
    elif space['type'] == 'community_chest':
        draw_community_chest_card(player, game_state)
    
    elif space['type'] == 'go_to_jail':
        send_to_jail(player, game_state)
    
    elif space['type'] == 'transit':
        if space['owner_id'] is None:
            prompt_buy_or_auction(player, space, game_state)
        elif space['owner_id'] != player['id']:
            collect_transit_rent(player, space, game_state)
    
    elif space['type'] in ['start', 'jail', 'free']:
        pass  # No effect, already handled
```

---

## 8. Economic Systems & Government Types

The government type is selected in the lobby and **cannot be changed mid-game**. It sets the initial values of all economic variables and governs how they behave.

### Government Types

#### Minarchism

A minimal government. No social safety net, low taxes, but highly unstable.

| Variable | Value |
|---|---|
| Welfare Payout | `0` (hard-coded — never changes) |
| Tax Multiplier | `0.05` (static) |
| Starting Stability | `0.90` |
| Stability Decay Rate | High — decays faster as inequality increases |
| Treasury Balance | `0` (no public spending) |
| Available Policies | None (no government tools exist) |
| Rage Growth Rate | Very High |

**Implementation note:** All welfare function calls under Minarchism must return `0` or `None`. The `Public Approval` stat should decay unless players invest in a **private security** mechanism (optional late-game feature). Do not allow lobbying to add welfare policies in this mode.

#### Liberal Democracy

A moderate system. Taxes and welfare fluctuate within defined ranges.

| Variable | Value |
|---|---|
| Welfare Payout | `random.uniform(10, 50)` per turn |
| Tax Multiplier | `random.uniform(0.15, 0.25)` |
| Starting Stability | `0.70` |
| Stability Decay Rate | Moderate — fluctuates up and down |
| Treasury Balance | Funded by taxes |
| Available Policies | All policies available |
| Rage Growth Rate | Moderate |

#### Social Democracy

A high-tax, high-welfare system with strong stability.

| Variable | Value |
|---|---|
| Welfare Payout | `random.uniform(60, 100)` per turn |
| Tax Multiplier | `random.uniform(0.40, 0.50)` |
| Starting Stability | `0.50` (starts lower due to high spending pressure) |
| Stability Decay Rate | Low — stability recovers when welfare is paid |
| Treasury Balance | Funded by high taxes |
| Available Policies | All policies available |
| Rage Growth Rate | Low |

### Government Initialization

```python
def initialize_government(gov_type, settings):
    if gov_type == 'minarchism':
        return {
            'welfare_payout': 0,
            'tax_multiplier': 0.05,
            'stability': 0.90,
            'inflation_rate': round(random.uniform(0.01, 0.04), 4),
            'interest_rate': round(random.uniform(0.03, 0.07), 4),
            'treasury_balance': 0
        }
    elif gov_type == 'liberal_democracy':
        return {
            'welfare_payout': round(random.uniform(10, 50), 2),
            'tax_multiplier': round(random.uniform(0.15, 0.25), 3),
            'stability': 0.70,
            'inflation_rate': round(random.uniform(0.02, 0.06), 4),
            'interest_rate': round(random.uniform(0.04, 0.09), 4),
            'treasury_balance': 500
        }
    elif gov_type == 'social_democracy':
        return {
            'welfare_payout': round(random.uniform(60, 100), 2),
            'tax_multiplier': round(random.uniform(0.40, 0.50), 3),
            'stability': 0.50,
            'inflation_rate': round(random.uniform(0.03, 0.07), 4),
            'interest_rate': round(random.uniform(0.05, 0.10), 4),
            'treasury_balance': 2000
        }
```

---

## 9. Dynamic Variables — Randomization & Live Updates

### Variables That Drift Each Turn

Every turn (Step 6 of the game loop), the following variables shift by a small random delta. This simulates a living economy.

```python
import random

def drift_economy(econ, gov_type, game_state):
    """
    Called once per turn after the active player's turn resolves.
    All drift values are small and bounded to prevent runaway values.
    """
    
    # Inflation drifts ±0.005, clamped to [0.005, 0.25]
    econ['inflation_rate'] = clamp(
        econ['inflation_rate'] + random.uniform(-0.005, 0.005),
        0.005, 0.25
    )
    
    # Interest rate drifts ±0.003, clamped to [0.01, 0.20]
    econ['interest_rate'] = clamp(
        econ['interest_rate'] + random.uniform(-0.003, 0.003),
        0.01, 0.20
    )
    
    # Stability drift depends on government type
    inequality = compute_gini_coefficient(game_state['players'])
    welfare = econ['welfare_payout']
    
    if gov_type == 'minarchism':
        # Stability decays proportionally to inequality
        econ['stability'] = clamp(econ['stability'] - (inequality * 0.03), 0.01, 1.0)
    elif gov_type == 'liberal_democracy':
        # Stability fluctuates — slight decay from inequality, slight recovery from welfare
        delta = (welfare / 100.0 * 0.01) - (inequality * 0.015)
        econ['stability'] = clamp(econ['stability'] + delta + random.uniform(-0.01, 0.01), 0.1, 1.0)
    elif gov_type == 'social_democracy':
        # Stability recovers when welfare is being paid and treasury is solvent
        if econ['treasury_balance'] > 0:
            econ['stability'] = clamp(econ['stability'] + 0.005, 0.1, 1.0)
        else:
            econ['stability'] = clamp(econ['stability'] - 0.02, 0.1, 1.0)
    
    # Welfare payout is fixed at 0 under Minarchism — never change it
    if gov_type != 'minarchism':
        econ['welfare_payout'] = clamp(
            econ['welfare_payout'] + random.uniform(-5, 5),
            0, 150
        )
    
    return econ


def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def compute_gini_coefficient(players):
    """
    Returns a value 0.0 (perfect equality) to 1.0 (maximum inequality).
    Used to drive stability decay.
    """
    balances = sorted([p['balance'] for p in players if not p['is_bankrupt']])
    n = len(balances)
    if n == 0:
        return 0
    total = sum(balances)
    if total == 0:
        return 0
    cumulative = 0
    gini_sum = 0
    for i, b in enumerate(balances):
        cumulative += b
        gini_sum += (2 * (i + 1) - n - 1) * b
    return gini_sum / (n * total)
```

### Property Value Drift

Property values also drift based on inflation:

```python
def update_property_values(properties, inflation_rate):
    for prop in properties:
        if prop['type'] == 'property' and not prop['is_mortgaged']:
            drift = random.uniform(-0.02, 0.02) + (inflation_rate * 0.5)
            prop['current_value'] = round(
                max(prop['base_price'] * 0.5, prop['current_value'] * (1 + drift)), 2
            )
    return properties
```

---

## 10. Rent Collection

Rent is **automatically applied** the moment a player lands on an owned property. There is no manual step.

### Rent Formula

```python
def calculate_rent(property, econ, game_state):
    base_rent = property['base_price'] * 0.1
    dev_multiplier = 1 + property['dev_level']
    inflation_multiplier = 1 + econ['inflation_rate']
    
    rent = base_rent * dev_multiplier * inflation_multiplier
    
    # Check if owner has a full group monopoly — double rent if no development
    if has_full_monopoly(property['owner_id'], property['group_color'], game_state):
        if property['dev_level'] == 0:
            rent *= 2
    
    return round(rent, 2)
```

### Development Levels & Rent Multipliers

Development is only available when a player owns the full property group.

| Dev Level | Description | Rent Multiplier |
|---|---|---|
| 0 | Unimproved | 1× |
| 1 | 1 Building | 5× base |
| 2 | 2 Buildings | 10× base |
| 3 | 3 Buildings | 20× base |
| 4 | 4 Buildings | 30× base |
| 5 | Hotel | 50× base |

```python
RENT_MULTIPLIERS = {0: 1.0, 1: 5.0, 2: 10.0, 3: 20.0, 4: 30.0, 5: 50.0}

def calculate_rent_with_dev(property, econ):
    base_rent = property['base_price'] * 0.1
    multiplier = RENT_MULTIPLIERS[property['dev_level']]
    inflation_adj = 1 + econ['inflation_rate']
    return round(base_rent * multiplier * inflation_adj, 2)
```

### Transit (Airport) Rent

```python
def calculate_transit_rent(owner_id, game_state):
    owned_transits = count_transits_owned_by(owner_id, game_state)
    rent_table = {1: 25, 2: 50, 3: 100, 4: 200}
    return rent_table.get(owned_transits, 25)
```

### Rent Transfer

```python
def collect_rent(payer, property, game_state, econ):
    owner = get_player(property['owner_id'], game_state)
    rent_amount = calculate_rent_with_dev(property, econ)
    
    if payer['balance'] < rent_amount:
        # Player cannot pay full rent — they pay what they can, then enter bankruptcy proceedings
        partial = payer['balance']
        transfer_funds(payer, owner, partial, game_state)
        trigger_bankruptcy(payer, game_state)
        log_event(game_state, 'rent_bankruptcy', 
                  f"{payer['username']} could not pay ${rent_amount} rent to {owner['username']}")
    else:
        transfer_funds(payer, owner, rent_amount, game_state)
        log_event(game_state, 'rent_collected',
                  f"{payer['username']} paid ${rent_amount} rent to {owner['username']} "
                  f"for {property['name']}")
```

---

## 11. Taxation System

### Income Tax (on passing GO)

Applied every time a player passes or lands on START, if enabled.

```python
def apply_income_tax(player, econ, settings):
    if not settings.get('income_tax_on_pass_go', True):
        return 0
    
    flat_rate = 200
    percent_rate = player['balance'] * econ['tax_multiplier']
    tax = max(flat_rate, percent_rate)    # Player pays the higher amount
    
    deduct(player, tax)
    deposit_treasury(tax, econ)
    log_event(game_state, 'income_tax', f"{player['username']} paid ${tax:.2f} income tax")
    return tax
```

### Property Tax (every N rounds globally)

Applied to all players at the same time, every N rounds (configurable in lobby, default: 5).

```python
def apply_global_property_tax(game_state, econ):
    for player in active_players(game_state):
        tax_total = 0
        for prop in get_player_properties(player['id'], game_state):
            if not prop['is_mortgaged']:
                prop_tax = prop['current_value'] * 0.01 * econ['tax_multiplier']
                tax_total += prop_tax
        deduct(player, tax_total)
        deposit_treasury(tax_total, econ)
        log_event(game_state, 'property_tax',
                  f"{player['username']} paid ${tax_total:.2f} property tax")
```

### Tax Every Turn (optional setting)

If `tax_every_turn` is enabled in lobby settings, a small flat tax is applied at the end of each player's turn:

```python
def apply_per_turn_tax(player, econ, settings):
    if not settings.get('tax_every_turn', False):
        return
    flat_tax = round(50 * econ['tax_multiplier'], 2)
    deduct(player, flat_tax)
    deposit_treasury(flat_tax, econ)
    log_event(game_state, 'turn_tax', f"{player['username']} paid ${flat_tax:.2f} turn tax")
```

### Luxury Tax & Super Tax

These are fixed-position board spaces, not toggles. They scale with the current tax multiplier:

```python
LUXURY_TAX_BASE = 100
SUPER_TAX_BASE  = 200

def apply_luxury_tax(player, econ):
    amount = LUXURY_TAX_BASE * (1 + econ['tax_multiplier'])
    deduct(player, amount)
    deposit_treasury(amount, econ)
    log_event(game_state, 'luxury_tax', f"{player['username']} paid ${amount:.2f} luxury tax")

def apply_super_tax(player, econ):
    amount = SUPER_TAX_BASE * (1 + econ['tax_multiplier'])
    deduct(player, amount)
    deposit_treasury(amount, econ)
    log_event(game_state, 'super_tax', f"{player['username']} paid ${amount:.2f} super tax")
```

---

## 12. Welfare & Stability System

### Welfare Payout

Welfare is distributed from the treasury to all players at the **start of each round** (after all players have taken one turn).

```python
def distribute_welfare(game_state, econ, gov_type):
    if gov_type == 'minarchism':
        return  # No welfare. Period. Function exits immediately.
    
    if not game_state['settings'].get('welfare_system_enabled', True):
        return
    
    payout = econ['welfare_payout']
    
    if econ['treasury_balance'] < payout * len(active_players(game_state)):
        # Treasury is broke — stability takes a major hit
        econ['stability'] = clamp(econ['stability'] - 0.10, 0.01, 1.0)
        log_event(game_state, 'welfare_failed',
                  "Treasury insufficient — welfare could not be paid. Stability dropped.")
        return
    
    for player in active_players(game_state):
        deposit(player, payout)
        econ['treasury_balance'] -= payout
    
    log_event(game_state, 'welfare_paid', f"${payout:.2f} welfare distributed to all players")
```

### Public Approval

Each player has an `approval_rating` (0–100). This affects lobbying power.

- Under **Minarchism**: Approval decays by 1–3 per round and can only be restored by spending money on private security (if enabled)
- Under **Liberal Democracy**: Approval fluctuates ±5 per round based on economic conditions
- Under **Social Democracy**: Approval is relatively stable but drops if treasury goes bankrupt

```python
def update_approval_ratings(game_state, econ, gov_type):
    for player in active_players(game_state):
        if gov_type == 'minarchism':
            player['approval_rating'] = clamp(player['approval_rating'] - random.uniform(1, 3), 0, 100)
        elif gov_type == 'liberal_democracy':
            delta = random.uniform(-5, 5) + (econ['stability'] * 5) - (econ['inflation_rate'] * 20)
            player['approval_rating'] = clamp(player['approval_rating'] + delta, 0, 100)
        elif gov_type == 'social_democracy':
            treasury_ok = econ['treasury_balance'] > 0
            delta = 2 if treasury_ok else -5
            player['approval_rating'] = clamp(player['approval_rating'] + delta, 0, 100)
```

---

## 13. Rage Multiplier & Uprising Events

### Rage Calculation

Calculated once per turn (Step 7 of the game loop):

```python
def calculate_rage(game_state, econ):
    if not game_state['settings'].get('rage_system_enabled', True):
        return 0
    
    total_wealth = sum(p['balance'] for p in active_players(game_state))
    welfare = econ['welfare_payout']
    stability = econ['stability']
    
    if welfare == 0:
        # Under Minarchism, use a substitute floor to avoid divide-by-zero
        effective_welfare = 1
    else:
        effective_welfare = welfare
    
    rage = (total_wealth / effective_welfare) * (1 - stability)
    return round(rage, 4)
```

### Uprising Trigger

```python
RAGE_THRESHOLD = 500  # Tunable constant

def check_uprising(game_state, rage):
    if not game_state['settings'].get('uprisings_enabled', True):
        return
    
    if rage > RAGE_THRESHOLD:
        trigger_uprising(game_state)

def trigger_uprising(game_state):
    # Pick a random region with developed properties
    regions = get_active_regions(game_state)
    target_region = random.choice(regions)
    
    # All properties in the region lose 1 dev level
    for prop in get_region_properties(target_region, game_state):
        if prop['dev_level'] > 0:
            prop['dev_level'] -= 1
    
    # Stability drops
    game_state['econ']['stability'] = clamp(
        game_state['econ']['stability'] - 0.15, 0.01, 1.0
    )
    
    # Treasury receives a small amount (seized assets)
    game_state['econ']['treasury_balance'] += 100
    
    log_event(game_state, 'uprising',
              f"UPRISING in {target_region}! Properties degraded. Stability fell.")
    
    # Broadcast uprising visual to all clients
    socketio.emit('uprising_event', {
        'region': target_region,
        'message': f"An uprising has erupted in {target_region}!"
    }, room=game_state['room_code'])
```

---

## 14. Chance & Community Chest Cards

### Card Storage

Cards are stored in the `cards` table and loaded into a shuffled deck at game start. Each deck is stored in Redis as a list and cycled.

```python
def initialize_card_decks(match_id):
    chance_cards = fetch_cards('chance')
    community_cards = fetch_cards('community_chest')
    random.shuffle(chance_cards)
    random.shuffle(community_cards)
    redis.set(f"game:{match_id}:chance_deck", json.dumps(chance_cards))
    redis.set(f"game:{match_id}:community_deck", json.dumps(community_cards))
```

### Chance Cards (16 cards)

| Card | Effect |
|---|---|
| Advance to START | Move to position 0, collect GO salary |
| Advance to Shanghai | Move to Shanghai |
| Advance to London | Move to London |
| Advance to nearest Airport | Move to nearest transit space |
| Bank pays dividend | Collect $50 |
| Get Out of Jail Free | Store card — use to leave jail for free |
| Go Back 3 Spaces | Move 3 spaces backward |
| Go to Jail | Immediately go to jail |
| Make general repairs | Pay $25 per building, $100 per hotel |
| Pay $15 poor tax | Pay $15 flat |
| Take a trip to Dubai Airport | Move to position 15 |
| Take a walk to Free Space | Move to position 20 |
| You are assessed street repairs | Pay $40 per building, $115 per hotel |
| Receive consulting fee | Collect $25 |
| Elected board chairperson | Pay $50 to each player |
| Loan matures | Collect $150 |

### Community Chest Cards (16 cards)

| Card | Effect |
|---|---|
| Advance to START | Collect GO salary |
| Bank error in your favor | Collect $200 |
| Doctor's fee | Pay $50 |
| From sale of stock | Collect $50 |
| Get Out of Jail Free | Store card |
| Go to Jail | Go directly to jail |
| Grand Opera Night | Collect $50 from each player |
| Holiday Fund matures | Collect $100 |
| Income tax refund | Collect $20 |
| It is your birthday | Collect $10 from each player |
| Life insurance matures | Collect $100 |
| Hospital fees | Pay $100 |
| School fees | Pay $150 |
| Receive consultancy fee | Collect $25 |
| You inherit $100 | Collect $100 |
| Welfare bonus | Collect current welfare payout × 2 |

### Card Resolution

```python
def draw_chance_card(player, game_state):
    if not game_state['settings'].get('chance_cards_enabled', True):
        return
    
    deck = redis.lrange(f"game:{game_state['match_id']}:chance_deck", 0, -1)
    card = json.loads(deck[0])
    # Rotate deck — move drawn card to the bottom
    redis.rpush(f"game:{game_state['match_id']}:chance_deck", deck[0])
    redis.lpop(f"game:{game_state['match_id']}:chance_deck")
    
    resolve_card_effect(player, card, game_state)
    log_event(game_state, 'chance_card', f"{player['username']} drew: '{card['card_text']}'")
    socketio.emit('card_drawn', {'type': 'chance', 'card': card, 'player': player['username']},
                  room=game_state['room_code'])
```

---

## 15. Lobbying System

### How Lobbying Works

Lobbying is a **cooperative spending mechanic** where players pool money to attempt to change an active government policy.

1. A player opens the **Lobby Modal** (available anytime during their turn, or between turns if host allows it)
2. They choose a **Lobbying Target** from the available policy list
3. They commit a **contribution amount** from their balance
4. Other players can join the same lobby target, making contributions additive
5. At the end of the round, success is calculated

### Available Lobbying Targets

| Target | Effect if Successful |
|---|---|
| Lower Corporate Tax | Reduce `tax_multiplier` by 0.05 |
| Raise Welfare | Increase `welfare_payout` by 15 |
| Cut Welfare | Reduce `welfare_payout` by 15 |
| Rent Control | Cap all rent at 80% of calculated value |
| Deregulate Housing | Remove rent cap and increase dev value multiplier by 10% |
| Stabilization Fund | Add $300 to treasury immediately |
| Increase Income Tax | Increase `tax_multiplier` by 0.05 |
| Economic Stimulus | All players receive $100 from treasury |

> Lobbying targets are unavailable under **Minarchism** (no government mechanisms exist to lobby).

### Success Calculation

```python
def resolve_lobbying(match_id, game_state, econ):
    lobby_entries = fetch_lobby_entries(match_id)
    
    # Group by policy target
    grouped = group_by_policy(lobby_entries)
    
    for policy_id, entries in grouped.items():
        total_contribution = sum(e['contribution'] for e in entries)
        num_players = len(entries)
        
        # Base success chance is 20%, increases with money and player count
        base_chance = 0.20
        money_bonus = min(total_contribution / 1000, 0.50)  # max +50% from money
        player_bonus = (num_players - 1) * 0.10             # +10% per additional player
        
        success_chance = min(base_chance + money_bonus + player_bonus, 0.95)
        
        if random.random() < success_chance:
            apply_policy(policy_id, game_state, econ)
            log_event(game_state, 'lobby_success', 
                      f"Lobbying for '{get_policy_name(policy_id)}' succeeded!")
        else:
            log_event(game_state, 'lobby_failed',
                      f"Lobbying for '{get_policy_name(policy_id)}' failed.")
        
        # Money is spent regardless of success
        for entry in entries:
            deduct(get_player(entry['player_id'], game_state), entry['contribution'])
```

---

## 16. Trading System

Trading is **fully transparent** — all trade proposals are visible to all players in the game log and trade feed in real time.

### Trade Components

A trade can include any combination of:
- **Money** (from initiator to receiver and/or receiver to initiator)
- **Properties** (from initiator's owned properties and/or receiver's owned properties)
- **Get Out of Jail Free cards**

Mortgaged properties **can** be traded. The mortgage transfers with the property. The new owner must pay 10% of the mortgage value to take it, or immediately unmortgage it.

### Trade Flow

```
1. Player A opens trade panel → selects Player B
2. Player A builds their offer (money, properties they're giving, properties they want, money they want)
3. Player A sends trade proposal → emits trade_proposed to all clients
4. All players see the proposal appear in the Trade Feed (read-only for non-participants)
5. Player B receives a modal notification
6. Player B can: Accept | Reject | Counter-offer
7. If counter-offer: same flow, roles reversed
8. If accepted: execute_trade() is called server-side
9. All players see the resolution in the Trade Feed and Game Log
```

### Trade Execution

```python
def execute_trade(trade_id, game_state):
    trade = fetch_trade(trade_id)
    initiator = get_player(trade['initiator_id'], game_state)
    receiver = get_player(trade['receiver_id'], game_state)
    
    # Transfer money
    if trade['offered_money'] > 0:
        transfer_funds(initiator, receiver, trade['offered_money'], game_state)
    if trade['requested_money'] > 0:
        transfer_funds(receiver, initiator, trade['requested_money'], game_state)
    
    # Transfer properties
    for prop_id in trade['offered_props']:
        transfer_property(prop_id, initiator['id'], receiver['id'], game_state)
    for prop_id in trade['requested_props']:
        transfer_property(prop_id, receiver['id'], initiator['id'], game_state)
    
    trade['status'] = 'accepted'
    trade['resolved_at'] = datetime.utcnow()
    save_trade(trade)
    
    log_event(game_state, 'trade_completed',
              f"Trade between {initiator['username']} and {receiver['username']} completed: "
              f"{initiator['username']} gave ${trade['offered_money']} + "
              f"{[get_property_name(p) for p in trade['offered_props']]}; "
              f"received ${trade['requested_money']} + "
              f"{[get_property_name(p) for p in trade['requested_props']]}")
    
    socketio.emit('trade_resolved', {'trade': trade}, room=game_state['room_code'])
```

### Trade Panel UI

The trade panel is a **split-screen modal**:
- Left column: Your offer (drag properties, type money amounts)
- Right column: What you're requesting
- Bottom: Trade history for this game (all resolved trades visible to everyone)
- A live trade ticker at the bottom of the main screen shows the 3 most recent trade events

---

## 17. Team System

Teams allow players to cooperate economically. Teams must be enabled in the lobby.

### Creating a Team

During the game (or in the lobby if enabled), a player can:
1. Click **Create Team** → enter a team name (20-char max) and pick a **team color** from a secondary palette
2. Invite other players by clicking their name in the player list
3. Invited players get a modal: **Accept** or **Decline**

### Team Color

Team color is displayed as a **secondary badge** on all team members' names and tokens. It should visually distinguish from the player's personal color. Use a lighter or bordered variant.

```python
TEAM_COLOR_PALETTE = [
    "#B2DFDB",  # Mint
    "#F8BBD9",  # Blush
    "#FFF9C4",  # Lemon
    "#CFD8DC",  # Silver
    "#D7CCC8",  # Warm Grey
    "#DCEDC8",  # Sage
]
```

### Team Mechanics

#### Property Immunity
If `teams_enabled` is `True`, landing on a teammate's property results in **no rent charge**. This is the most significant team benefit.

```python
def is_team_immune(payer, owner_id, game_state):
    if not game_state['settings'].get('teams_enabled', False):
        return False
    payer_team = payer.get('team_id')
    owner = get_player(owner_id, game_state)
    owner_team = owner.get('team_id')
    if payer_team is None or owner_team is None:
        return False
    return payer_team == owner_team
```

#### Shared Vision
Team members can see each other's full financial details (balance, properties, cards) via a **Team Panel** that appears in the UI.

#### Team Trading
Trades between teammates are flagged as `internal_trade` in the log. They still appear publicly in the trade feed.

#### Team Dissolution
A team can be dissolved by its creator at any time. When dissolved:
- All members are removed from the team
- Property immunity is immediately revoked
- The dissolution is logged for all players to see

#### Team Win Condition
If the host enables **Team Mode** win condition (lobby setting: `team_win_condition: true`), the last surviving **team** wins rather than the last individual player.

---

## 18. Auctions & Mortgages

### Auctions

Auctions are triggered when:
- A player **declines to purchase** a property they landed on (and `auction_enabled` is `True`)

#### Auction Flow

```
1. Player declines purchase → server emits auction_start to all clients
2. All players (including the one who declined) can bid
3. Bidding is open for 30 seconds (or until no new bids for 10 seconds)
4. Minimum starting bid: $1
5. Each bid must exceed the previous by at least $1
6. At auction close: highest bidder pays and receives the property
7. If no bids: property remains unowned
```

```python
def resolve_auction(match_id, property_id, game_state):
    bids = redis.lrange(f"game:{match_id}:auction:{property_id}:bids", 0, -1)
    if not bids:
        log_event(game_state, 'auction_no_bids', f"No bids on {get_property_name(property_id)}")
        return
    
    highest_bid = max(json.loads(b) for b in bids, key=lambda x: x['amount'])
    winner = get_player(highest_bid['player_id'], game_state)
    prop = get_property(property_id, game_state)
    
    deduct(winner, highest_bid['amount'])
    prop['owner_id'] = winner['id']
    
    log_event(game_state, 'auction_won',
              f"{winner['username']} won {prop['name']} at auction for ${highest_bid['amount']}")
```

### Mortgages

Mortgages are available if `mortgage_enabled` is `True` in settings.

#### Mortgage Rules
- A player can mortgage any **unimproved** property they own
- Mortgage value = `base_price * 0.5`
- To unmortgage: pay `mortgage_value * 1.1` (10% interest)
- Mortgaged properties **cannot collect rent**
- Mortgaged properties **can be traded** — the new owner must pay the 10% interest fee to unmortgage

```python
def mortgage_property(player, property, game_state, econ):
    if property['dev_level'] > 0:
        return {'error': 'Must remove all developments before mortgaging'}
    
    mortgage_value = property['base_price'] * 0.5
    deposit(player, mortgage_value)
    property['is_mortgaged'] = True
    
    log_event(game_state, 'mortgage',
              f"{player['username']} mortgaged {property['name']} for ${mortgage_value}")

def unmortgage_property(player, property, game_state, econ):
    unmortgage_cost = (property['base_price'] * 0.5) * 1.1
    
    if player['balance'] < unmortgage_cost:
        return {'error': 'Insufficient funds to unmortgage'}
    
    deduct(player, unmortgage_cost)
    property['is_mortgaged'] = False
    
    log_event(game_state, 'unmortgage',
              f"{player['username']} unmortgaged {property['name']} for ${unmortgage_cost:.2f}")
```

---

## 19. The Game Log

The game log is a **central, live, append-only feed** that all players see at all times. It is the primary source of truth for what has happened in the game.

### Log Entry Structure

```python
def log_event(game_state, event_type, description, player_id=None):
    entry = {
        'round': game_state['current_round'],
        'turn': game_state['current_turn_index'],
        'player_id': player_id,
        'event_type': event_type,
        'description': description,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Persist to PostgreSQL
    db.execute("""
        INSERT INTO game_log (match_id, round, turn, player_id, event_type, description)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (game_state['match_id'], entry['round'], entry['turn'],
          entry['player_id'], entry['event_type'], entry['description']))
    
    # Add to Redis buffer (last 100 entries)
    redis.lpush(f"game:{game_state['match_id']}:log_buffer", json.dumps(entry))
    redis.ltrim(f"game:{game_state['match_id']}:log_buffer", 0, 99)
    
    # Broadcast to all clients
    socketio.emit('log_entry', entry, room=game_state['room_code'])
```

### Log Event Types

| Event Type | Color Code in UI |
|---|---|
| `dice_roll` | Grey |
| `move` | Grey |
| `rent_collected` | Red (payer) / Green (owner) |
| `property_purchased` | Blue |
| `auction_won` | Blue |
| `income_tax` | Orange |
| `property_tax` | Orange |
| `turn_tax` | Orange |
| `luxury_tax` | Orange |
| `super_tax` | Orange |
| `welfare_paid` | Green |
| `welfare_failed` | Red |
| `trade_proposed` | Yellow |
| `trade_completed` | Green |
| `trade_rejected` | Grey |
| `lobby_success` | Purple |
| `lobby_failed` | Grey |
| `uprising` | Bright Red + Bold |
| `bankruptcy` | Dark Red + Bold |
| `hyper_inflation` | Flashing Red |
| `chance_card` | Yellow |
| `community_chest` | Yellow |
| `jail_sent` | Orange |
| `jail_released` | Grey |
| `team_formed` | Teal |
| `team_dissolved` | Teal |

### Log UI

- Displayed as a scrolling panel on the right side of the screen
- New entries animate in from the bottom
- Players can filter by event type using toggles
- Clicking on a player name in the log highlights their token on the board
- Log is downloadable as a `.txt` file at game end

---

## 20. Late-Game Triggers

### Hyper-Inflation (Round 50+)

If `hyper_inflation_trigger` is enabled and the game exceeds the configured round limit (default: 50):

```python
def check_hyper_inflation(game_state, econ, settings):
    if not settings.get('hyper_inflation_trigger', True):
        return
    
    trigger_round = settings.get('hyper_inflation_round', 50)
    if game_state['current_round'] < trigger_round:
        return
    
    # Aggressively increase inflation every round past the trigger
    rounds_past = game_state['current_round'] - trigger_round
    inflation_boost = 0.02 * rounds_past
    econ['inflation_rate'] = min(econ['inflation_rate'] + inflation_boost, 2.0)
    
    # Tax multiplier escalates
    econ['tax_multiplier'] = min(econ['tax_multiplier'] * 1.05, 2.0)
    
    # Property values spike unpredictably
    for prop in all_properties(game_state):
        prop['current_value'] *= random.uniform(1.05, 1.20)
    
    log_event(game_state, 'hyper_inflation',
              f"HYPER-INFLATION ACTIVE! Inflation: {econ['inflation_rate']:.1%} | "
              f"Tax rate: {econ['tax_multiplier']:.1%}")
    
    socketio.emit('hyper_inflation_alert', {
        'round': game_state['current_round'],
        'inflation': econ['inflation_rate']
    }, room=game_state['room_code'])
```

### Bankruptcy

When a player's balance drops below zero and they cannot resolve the debt (through mortgaging or selling developments):

```python
def trigger_bankruptcy(player, creditor, game_state):
    # All properties transfer to creditor (or to the bank/unowned if tax caused bankruptcy)
    for prop in get_player_properties(player['id'], game_state):
        if creditor is not None:
            prop['owner_id'] = creditor['id']
        else:
            prop['owner_id'] = None
            prop['dev_level'] = 0
            prop['is_mortgaged'] = False
    
    player['is_bankrupt'] = True
    player['balance'] = 0
    player['is_connected'] = False
    
    log_event(game_state, 'bankruptcy',
              f"{player['username']} has gone BANKRUPT and is eliminated from the game!")
    
    check_win_condition(game_state)
```

### Win Condition

```python
def check_win_condition(game_state):
    active = [p for p in game_state['players'] if not p['is_bankrupt']]
    
    if game_state['settings'].get('team_win_condition', False):
        active_teams = set(p['team_id'] for p in active if p['team_id'] is not None)
        solo_players = [p for p in active if p['team_id'] is None]
        survivors = len(active_teams) + len(solo_players)
        if survivors == 1:
            winner_desc = f"Team {get_team_name(list(active_teams)[0])}" if active_teams else active[0]['username']
            emit_game_over(winner_desc, game_state)
    else:
        if len(active) == 1:
            emit_game_over(active[0]['username'], game_state)
```

---

## 21. Disconnect & Session Handling

### On Player Disconnect

```python
@socketio.on('disconnect')
def handle_disconnect():
    player = get_player_by_session(request.sid)
    if not player:
        return
    
    player['is_connected'] = False
    game_state = get_game_state(player['match_id'])
    
    log_event(game_state, 'disconnect', f"{player['username']} has disconnected")
    socketio.emit('player_disconnected', {'username': player['username']},
                  room=game_state['room_code'])
    
    # Properties remain — do NOT remove them
    # Influence decays while disconnected (tracked per turn)
    redis.set(f"player:{player['id']}:disconnected_at_round", game_state['current_round'])
    
    # If it is this player's turn, auto-resolve after 30 seconds
    if game_state['current_turn_player_id'] == player['id']:
        schedule_auto_turn(player['id'], game_state, delay=30)
```

### Influence Decay on Disconnect

At the start of each round, check for disconnected players and apply influence decay:

```python
def apply_disconnect_decay(game_state):
    current_round = game_state['current_round']
    for player in game_state['players']:
        if not player['is_connected']:
            rounds_disconnected = current_round - redis.get(f"player:{player['id']}:disconnected_at_round")
            decay = rounds_disconnected * 2
            player['influence_score'] = max(0, player['influence_score'] - decay)
```

### Reconnection

On reconnect, the player's session is restored, their position and balance are unchanged, and they receive the full current game state snapshot.

---

## 22. QOL — Visual Identity & UI Standards

### Color Rules (Hard Requirements)

1. **No two players share a color** in the same match. Lock colors at selection.
2. **Property group color** is shown as a colored border or top-strip on property tiles — always visible, never hidden behind ownership indicators.
3. **Ownership indicator** on a property tile is the **player's personal color**, shown as a small dot or bar at the bottom of the tile.
4. The **game board** renders property group colors as consistent bands — matching how Monopoly boards color-code groups.
5. All player names in the UI (log, leaderboard, trade panel, team panel) must render with a colored badge or dot in that player's `color_hex`.
6. If text is displayed on a light-colored badge background (e.g., yellow), always use dark text (`#111111`). If on dark background, use white text.

### Board UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│   GAME BOARD (center, full board loop)   │  PLAYER PANEL   │
│                                          │  (right column) │
│                                          │  - Each player  │
│                                          │    name + color │
│                                          │  - Balance      │
│                                          │  - Properties   │
│                                          │  - Team badge   │
├──────────────────────────────────────────┤─────────────────┤
│   GAME LOG (scrollable, right or bottom) │  DICE + ACTIONS │
│   [event feed with color-coded types]    │  Roll / Trade / │
│                                          │  Lobby / Build  │
└─────────────────────────────────────────────────────────────┘
```

### Username Validation

```python
import re
from better_profanity import profanity  # pip install better-profanity

def validate_username(name: str) -> tuple[bool, str]:
    if len(name) > 12:
        return False, "Username must be 12 characters or fewer."
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        return False, "Only letters, numbers, and underscores allowed."
    if profanity.contains_profanity(name):
        return False, "Username not allowed."
    return True, ""
```

### Turn Timer

- A visible countdown timer shows how long the active player has left
- Default: 90 seconds per turn (configurable in lobby)
- At 15 seconds remaining: timer turns yellow
- At 5 seconds remaining: timer turns red and pulses
- At 0: server auto-rolls dice and auto-resolves the turn with minimum actions

### Leaderboard

Always visible panel showing all players ranked by **net worth** (balance + property values + development value):

```python
def calculate_net_worth(player, game_state):
    balance = player['balance']
    prop_value = sum(
        p['current_value'] + (p['dev_level'] * 50)
        for p in get_player_properties(player['id'], game_state)
        if not p['is_mortgaged']
    )
    mortgage_debt = sum(
        p['base_price'] * 0.5
        for p in get_player_properties(player['id'], game_state)
        if p['is_mortgaged']
    )
    return balance + prop_value - mortgage_debt
```

---

## 23. Flask Route Map

```
POST   /api/auth/register              → Create account
POST   /api/auth/login                 → Login, return session
POST   /api/lobby/create               → Host creates a room
POST   /api/lobby/join                 → Player joins room by code
GET    /api/lobby/<room_code>          → Get lobby state
PATCH  /api/lobby/<room_code>/settings → Host updates settings
POST   /api/lobby/<room_code>/start    → Host starts game

GET    /api/game/<match_id>/state      → Full game state snapshot
POST   /api/game/<match_id>/roll       → Roll dice (active player only)
POST   /api/game/<match_id>/buy        → Buy current property
POST   /api/game/<match_id>/decline    → Decline purchase (triggers auction if enabled)
POST   /api/game/<match_id>/develop    → Add building to a property
POST   /api/game/<match_id>/mortgage   → Mortgage a property
POST   /api/game/<match_id>/unmortgage → Unmortgage a property
POST   /api/game/<match_id>/trade      → Submit a trade proposal
PATCH  /api/game/<match_id>/trade/<id> → Accept/Reject/Counter a trade
POST   /api/game/<match_id>/lobby      → Submit a lobbying contribution
POST   /api/game/<match_id>/team/create → Create a team
POST   /api/game/<match_id>/team/invite → Invite player to team
PATCH  /api/game/<match_id>/team/respond → Accept/decline team invite
DELETE /api/game/<match_id>/team       → Dissolve team
GET    /api/game/<match_id>/log        → Full game log (paginated)
POST   /api/game/<match_id>/jail/pay   → Pay bail to leave jail
POST   /api/game/<match_id>/jail/card  → Use Get Out of Jail Free card
```

---

## 24. Socket.IO Event Reference

### Server → Client Emissions

| Event | Payload | Description |
|---|---|---|
| `game_start` | `{game_state}` | Game has started, full initial state |
| `turn_start` | `{player_id, time_limit}` | New player's turn begins |
| `dice_rolled` | `{player_id, d1, d2, total, doubles}` | Dice result |
| `player_moved` | `{player_id, from, to, passed_go}` | Token movement |
| `rent_collected` | `{payer, owner, amount, property}` | Rent transaction |
| `property_purchased` | `{player_id, property_id, amount}` | Purchase confirmed |
| `auction_start` | `{property_id, min_bid}` | Auction begins |
| `auction_bid` | `{player_id, amount}` | New auction bid |
| `auction_end` | `{winner_id, amount, property_id}` | Auction resolved |
| `trade_proposed` | `{trade}` | New trade visible to all |
| `trade_resolved` | `{trade}` | Trade accepted/rejected/cancelled |
| `card_drawn` | `{type, card, player}` | Card drawn and resolved |
| `log_entry` | `{entry}` | New game log entry |
| `economy_update` | `{econ}` | Live economic variable update |
| `uprising_event` | `{region, message}` | Uprising triggered |
| `hyper_inflation_alert` | `{round, inflation}` | Hyper-inflation triggered |
| `team_formed` | `{team}` | New team created |
| `team_dissolved` | `{team_id}` | Team dissolved |
| `player_bankrupt` | `{player_id}` | Player eliminated |
| `game_over` | `{winner, stats}` | Game ended |
| `player_disconnected` | `{username}` | Player lost connection |
| `color_taken` | `{color_hex}` | Color locked in lobby |
| `lobby_update` | `{lobby_state}` | Lobby settings changed |

### Client → Server Emissions

| Event | Payload |
|---|---|
| `roll_dice` | `{match_id}` |
| `buy_property` | `{match_id, property_id}` |
| `decline_property` | `{match_id, property_id}` |
| `auction_bid` | `{match_id, property_id, amount}` |
| `submit_trade` | `{match_id, trade_data}` |
| `respond_trade` | `{match_id, trade_id, response}` |
| `submit_lobby` | `{match_id, policy_id, amount}` |
| `create_team` | `{match_id, name, color}` |
| `invite_team` | `{match_id, target_player_id}` |
| `respond_team` | `{match_id, team_id, accept}` |
| `develop_property` | `{match_id, property_id}` |
| `mortgage_property` | `{match_id, property_id}` |
| `unmortgage_property` | `{match_id, property_id}` |
| `pay_jail_bail` | `{match_id}` |
| `use_jail_card` | `{match_id}` |
| `select_color` | `{room_code, color_hex}` |
| `player_ready` | `{room_code}` |
| `update_settings` | `{room_code, settings}` (host only) |
| `start_game` | `{room_code}` (host only) |

---

## 25. Development Roadmap

### Phase 1 — Foundation
- [ ] Flask app setup with Flask-SocketIO
- [ ] PostgreSQL schema creation and migrations (use Flask-Migrate / Alembic)
- [ ] Redis setup and connection
- [ ] User auth (register, login, session)
- [ ] Lobby creation and joining
- [ ] Lobby settings panel (host controls)
- [ ] Color selection with real-time lock broadcast
- [ ] Username validation with profanity filter
- [ ] Game state initialization from lobby settings

### Phase 2 — Core Game Loop
- [ ] Board definition (all 48 positions with correct data)
- [ ] Dice rolling and player movement
- [ ] Property purchase and decline flow
- [ ] Basic rent collection (no development)
- [ ] Tax spaces (income tax, luxury tax, super tax)
- [ ] Jail mechanics (send, pay bail, use card, serve 3 turns)
- [ ] GO salary and income tax on pass
- [ ] Game log (persistent + broadcast)
- [ ] Turn timer with auto-resolve

### Phase 3 — Economic Systems
- [ ] Government initialization per type
- [ ] Per-turn economic drift (inflation, interest, stability)
- [ ] Property value drift
- [ ] Gini coefficient calculation
- [ ] Welfare distribution
- [ ] Property tax (every N rounds)
- [ ] Per-turn flat tax (if enabled)
- [ ] Rage multiplier calculation
- [ ] Uprising trigger and resolution

### Phase 4 — Player Interactions
- [ ] Trade proposal system
- [ ] Counter-offer flow
- [ ] Trade public feed (visible to all)
- [ ] Team creation and invite system
- [ ] Team property immunity
- [ ] Lobbying system
- [ ] Policy application
- [ ] Development (buildings → hotel)
- [ ] Mortgage and unmortgage

### Phase 5 — Cards & Auctions
- [ ] Chance card deck (populate DB, shuffle, cycle)
- [ ] Community Chest deck
- [ ] Card resolution for all 32 cards
- [ ] Auction system with real-time bidding
- [ ] "Get Out of Jail Free" card storage and use

### Phase 6 — Late Game & Polish
- [ ] Hyper-inflation trigger
- [ ] Bankruptcy detection and property transfer
- [ ] Win condition check (individual and team modes)
- [ ] Disconnect handling and influence decay
- [ ] Reconnection flow
- [ ] Leaderboard with live net worth
- [ ] End-of-game stats screen
- [ ] Downloadable game log

### Phase 7 — QOL & UI
- [ ] Full board SVG/Canvas with group color bands
- [ ] Player token rendering in personal color
- [ ] Property ownership indicators (player color dot)
- [ ] Animated dice roll
- [ ] Animated player movement
- [ ] Log color-coding by event type
- [ ] Trade panel UI
- [ ] Team panel UI
- [ ] Economy dashboard (inflation, stability, rage displayed live)
- [ ] Uprising animation/overlay
- [ ] Hyper-inflation visual indicator
- [ ] Mobile responsiveness

---

## 26. Implementation Warnings & Gotchas

### Critical: Minarchism Welfare Lock

The welfare payout under Minarchism **must never be changed by any system** — not drift, not lobbying, not cards. Enforce this with a guard at every point that touches `welfare_payout`:

```python
def set_welfare(econ, value, gov_type):
    if gov_type == 'minarchism':
        return  # Silently blocked
    econ['welfare_payout'] = max(0, value)
```

### Divide-By-Zero in Rage Formula

If welfare is 0 (Minarchism), the Rage formula divides by zero. Always substitute a floor value of `1` for the denominator, never skip the calculation — the rage should still be high under Minarchism.

### Property Tax Before Bankruptcy Check

Always run property tax deductions **before** the bankruptcy check in the same round. Do not swap this order.

### Turn Order on Disconnect

If the active player disconnects mid-turn, start a 30-second server-side timer before auto-resolving. Do **not** immediately skip their turn — they may reconnect.

### Trade Integrity

Validate all trade submissions server-side:
- Player actually owns the offered properties
- Offered money ≤ player's actual balance
- Neither player is currently bankrupt
- The match is in `active` status
- No property offered is currently under development lock (i.e., if selling one property from a group, the group loses the monopoly — remove all buildings first, return partial cost)

### Auction and Decline Order

When a player declines to buy and an auction starts, the **declining player is still allowed to bid**. This is the correct Monopoly rule — do not exclude them.

### Color Validation in Lobby

Validate color selection server-side, not just client-side. Race conditions between two players selecting the same color simultaneously must be resolved server-first, and the loser must be notified via `color_taken` and prompted to re-select.

### Team Immunity and Rent Log

Even when team immunity applies, **still log the event** as `"Team immunity — no rent charged"`. Players who are not on the team should see this in the log so they understand what happened.

### Card Deck Recycling

When all cards in a deck have been drawn, shuffle the discard pile and reuse it. Do not ever run out of cards. Track drawn cards in a parallel Redis list.

### Hyper-Inflation Does Not Apply Retroactively

When hyper-inflation activates, it modifies **future** rent calculations and tax rates. It does not recalculate or claw back past transactions.

### Development Restrictions

- A player may only develop properties in a full group they own
- Development must be **even** — you cannot put a 3rd building on one property before all properties in the group have 2 buildings (enforce this in `develop_property` validation)
- When selling developments, sell in reverse order (most developed first, most even)

### Settings Immutability Mid-Game

Once the game has started (status = `active`), no settings can be changed by the host or any player. All `settings_json` reads are treated as read-only after `game_start` is emitted. Enforce this at the route level.

---

*End of PoorUp Development Instructions — v1.0*

> This document is intended as the complete technical reference for a developer building PoorUp from scratch using Flask. All formulas, schemas, and event names defined here are the canonical source of truth. When in doubt, refer to the formula or schema in this document rather than the original spec sheet.
