-- PoorUp deal termination handshake
-- Adds the fields required to track which side requested termination first.

BEGIN;

ALTER TABLE deals
    ADD COLUMN IF NOT EXISTS termination_requested_by_id INTEGER REFERENCES match_players(id) ON DELETE SET NULL;

ALTER TABLE deals
    ADD COLUMN IF NOT EXISTS termination_requested_at TIMESTAMP;

COMMIT;