-- PoorUp board layout revision 6
-- Removes the remaining highlighted side special spaces from active play.

BEGIN;

UPDATE match_players
SET current_position = CASE current_position
    WHEN 3 THEN 4
    WHEN 8 THEN 9
    WHEN 29 THEN 30
    ELSE current_position
END
WHERE current_position IN (3, 8, 29);

COMMIT;