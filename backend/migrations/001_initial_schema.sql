-- PoorUp Initial Database Schema
-- Run with: psql -U postgres -d poorup -f migrations/001_initial_schema.sql

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(12) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teams (
    id          SERIAL PRIMARY KEY,
    match_id    INTEGER NOT NULL,  -- forward reference; FK added after matches
    team_name   VARCHAR(30) NOT NULL,
    team_color  VARCHAR(7),
    created_by  INTEGER             -- FK to match_players added later
);

CREATE TABLE IF NOT EXISTS matches (
    id                  SERIAL PRIMARY KEY,
    room_code           VARCHAR(8) UNIQUE,
    host_user_id        INTEGER REFERENCES users(id),
    government_type     VARCHAR(30) DEFAULT 'liberal_democracy',
    status              VARCHAR(20) DEFAULT 'lobby',
    settings_json       JSONB DEFAULT '{}',
    current_round       INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS match_players (
    id                      SERIAL PRIMARY KEY,
    match_id                INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    color_hex               VARCHAR(7),
    balance                 NUMERIC(14,2) DEFAULT 0,
    influence_score         NUMERIC(8,2) DEFAULT 0,
    approval_rating         NUMERIC(5,2) DEFAULT 50.0,
    current_position        INTEGER DEFAULT 0,
    is_jailed               BOOLEAN DEFAULT FALSE,
    jail_turns_remaining    INTEGER DEFAULT 0,
    team_id                 INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    is_bankrupt             BOOLEAN DEFAULT FALSE,
    is_connected            BOOLEAN DEFAULT TRUE,
    has_jail_card           BOOLEAN DEFAULT FALSE,
    consecutive_doubles     INTEGER DEFAULT 0,
    is_ready                BOOLEAN DEFAULT FALSE,
    is_bot                  BOOLEAN DEFAULT FALSE,
    bot_profile             JSONB DEFAULT '{}'::jsonb
);

-- Add FK now that match_players exists
ALTER TABLE teams
    ADD CONSTRAINT fk_teams_match FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_teams_created_by FOREIGN KEY (created_by) REFERENCES match_players(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS properties (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    name            VARCHAR(60) NOT NULL,
    region          VARCHAR(40),
    group_color     VARCHAR(7),
    board_position  INTEGER NOT NULL,
    base_price      NUMERIC(10,2),
    current_value   NUMERIC(10,2),
    dev_level       INTEGER DEFAULT 0,
    owner_id        INTEGER REFERENCES match_players(id) ON DELETE SET NULL,
    is_mortgaged    BOOLEAN DEFAULT FALSE,
    property_type   VARCHAR(20) DEFAULT 'property'
);

CREATE TABLE IF NOT EXISTS governments (
    id                  SERIAL PRIMARY KEY,
    match_id            INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE UNIQUE,
    gov_type            VARCHAR(30),
    stability           NUMERIC(5,4) DEFAULT 0.70,
    treasury_balance    NUMERIC(14,2) DEFAULT 0,
    welfare_payout      NUMERIC(10,2) DEFAULT 0,
    tax_multiplier      NUMERIC(5,3) DEFAULT 0.15,
    inflation_rate      NUMERIC(5,4) DEFAULT 0.03,
    interest_rate       NUMERIC(5,4) DEFAULT 0.06
);

CREATE TABLE IF NOT EXISTS policies (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    policy_name     VARCHAR(80),
    target_stat     VARCHAR(40),
    effect_value    NUMERIC(8,4),
    is_active       BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS lobbies (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    policy_id       INTEGER NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    player_id       INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    contribution    NUMERIC(10,2) DEFAULT 0,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    initiator_id    INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    receiver_id     INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    offered_money   NUMERIC(10,2) DEFAULT 0,
    requested_money NUMERIC(10,2) DEFAULT 0,
    offered_props   INTEGER[] DEFAULT '{}',
    requested_props INTEGER[] DEFAULT '{}',
    offered_lobby_pledges JSONB DEFAULT '[]'::jsonb,
    requested_lobby_pledges JSONB DEFAULT '[]'::jsonb,
    status          VARCHAR(20) DEFAULT 'pending',
    created_at      TIMESTAMP DEFAULT now(),
    resolved_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deals (
    id                  SERIAL PRIMARY KEY,
    match_id            INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    proposer_id         INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    counterparty_id     INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    status              VARCHAR(20) NOT NULL DEFAULT 'proposed',
    title               VARCHAR(80),
    created_at          TIMESTAMP DEFAULT now(),
    responded_at        TIMESTAMP,
    accepted_at         TIMESTAMP,
    cancelled_at        TIMESTAMP,
    last_updated_at     TIMESTAMP DEFAULT now(),
    proposal_version    INTEGER DEFAULT 1,
    counter_of_deal_id  INTEGER REFERENCES deals(id),
    termination_requested_by_id INTEGER REFERENCES match_players(id) ON DELETE SET NULL,
    termination_requested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deal_clauses (
    id                  SERIAL PRIMARY KEY,
    deal_id             INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    clause_type         VARCHAR(30) NOT NULL,
    grantor_id          INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    beneficiary_id      INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    scope_json          JSONB NOT NULL DEFAULT '{}'::jsonb,
    config_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    deadline_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    state_json          JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    activated_at        TIMESTAMP,
    expired_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deal_investment_tranches (
    id                      SERIAL PRIMARY KEY,
    deal_clause_id          INTEGER NOT NULL REFERENCES deal_clauses(id) ON DELETE CASCADE,
    property_id             INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    investor_id             INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    recipient_id            INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
    funded_cost             NUMERIC(10,2) NOT NULL,
    baseline_dev_level      INTEGER NOT NULL,
    funded_dev_level        INTEGER NOT NULL,
    baseline_rent           NUMERIC(10,2) NOT NULL,
    funded_rent             NUMERIC(10,2) NOT NULL,
    profit_share_percent    NUMERIC(5,4) NOT NULL,
    max_payout              NUMERIC(10,2) NOT NULL,
    payout_to_date          NUMERIC(10,2) DEFAULT 0,
    active                  BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS game_log (
    id          SERIAL PRIMARY KEY,
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    round       INTEGER DEFAULT 0,
    turn        INTEGER DEFAULT 0,
    player_id   INTEGER REFERENCES match_players(id) ON DELETE SET NULL,
    event_type  VARCHAR(40),
    description TEXT,
    timestamp   TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cards (
    id              SERIAL PRIMARY KEY,
    deck_type       VARCHAR(20) NOT NULL,  -- 'chance' | 'community_chest'
    card_text       TEXT NOT NULL,
    effect_type     VARCHAR(40) NOT NULL,
    effect_value    NUMERIC(10,2)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_match_players_match_id ON match_players(match_id);
CREATE INDEX IF NOT EXISTS idx_match_players_user_id  ON match_players(user_id);
CREATE INDEX IF NOT EXISTS idx_properties_match_id    ON properties(match_id);
CREATE INDEX IF NOT EXISTS idx_properties_owner_id    ON properties(owner_id);
CREATE INDEX IF NOT EXISTS idx_game_log_match_id      ON game_log(match_id);
CREATE INDEX IF NOT EXISTS idx_game_log_timestamp     ON game_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_match_id        ON trades(match_id);
CREATE INDEX IF NOT EXISTS idx_deals_match_id         ON deals(match_id);
CREATE INDEX IF NOT EXISTS idx_deal_clauses_deal_id   ON deal_clauses(deal_id);
CREATE INDEX IF NOT EXISTS idx_deal_tranches_prop_id  ON deal_investment_tranches(property_id);
CREATE INDEX IF NOT EXISTS idx_lobbies_match_policy   ON lobbies(match_id, policy_id);

-- ============================================================
-- SEED DATA — Cards
-- ============================================================

INSERT INTO cards (deck_type, card_text, effect_type, effect_value) VALUES
-- Chance cards
('chance', 'Advance to START — Collect GO salary.', 'advance_to_start', NULL),
('chance', 'Advance to Shanghai.', 'advance_to_position', 26),
('chance', 'Advance to London.', 'advance_to_position', 24),
('chance', 'Advance to nearest Airport.', 'advance_to_nearest_transit', NULL),
('chance', 'Bank pays dividend — Collect $50.', 'collect', 50),
('chance', 'Go Back 3 Spaces.', 'move_back', 3),
('chance', 'Make general repairs — $25 per building, $100 per hotel.', 'street_repairs', 100),
('chance', 'Pay $15 poor tax.', 'pay', 15),
('chance', 'Take a trip to Dubai Airport.', 'advance_to_position', 15),
('chance', 'Take a walk to Free Space.', 'advance_to_position', 20),
('chance', 'You are assessed street repairs — $40 per building, $115 per hotel.', 'street_repairs_community', 115),
('chance', 'Receive consulting fee — Collect $25.', 'collect', 25),
('chance', 'Elected board chairperson — Pay $50 to each player.', 'pay_each_player', 50),
('chance', 'Loan matures — Collect $150.', 'collect', 150),

-- Community Chest cards
('community_chest', 'Advance to START — Collect GO salary.', 'advance_to_start', NULL),
('community_chest', 'Bank error in your favor — Collect $200.', 'collect', 200),
('community_chest', 'Doctor''s fee — Pay $50.', 'pay', 50),
('community_chest', 'From sale of stock — Collect $50.', 'collect', 50),
('community_chest', 'Grand Opera Night — Collect $50 from each player.', 'collect_from_each_player', 50),
('community_chest', 'Holiday Fund matures — Collect $100.', 'collect', 100),
('community_chest', 'Income tax refund — Collect $20.', 'collect', 20),
('community_chest', 'It is your birthday — Collect $10 from each player.', 'collect_from_each_player', 10),
('community_chest', 'Life insurance matures — Collect $100.', 'collect', 100),
('community_chest', 'Hospital fees — Pay $100.', 'pay', 100),
('community_chest', 'School fees — Pay $150.', 'pay', 150),
('community_chest', 'Receive consultancy fee — Collect $25.', 'collect', 25),
('community_chest', 'You inherit $100 — Collect $100.', 'collect', 100),
('community_chest', 'Welfare bonus — Collect current welfare payout doubled.', 'collect_welfare_bonus', NULL)

ON CONFLICT DO NOTHING;
