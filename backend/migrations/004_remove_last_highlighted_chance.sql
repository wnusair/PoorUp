-- PoorUp board layout revision 5
-- Removes the last highlighted top-row Chance tile from active play.

BEGIN;

UPDATE match_players
SET current_position = 47
WHERE current_position = 44;

COMMIT;