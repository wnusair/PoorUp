-- PoorUp board layout revision 3
-- Removes retired top-row spaces from persisted match data.

BEGIN;

UPDATE match_players
SET current_position = CASE current_position
    WHEN 35 THEN 36
    WHEN 41 THEN 42
    WHEN 43 THEN 44
    WHEN 45 THEN 47
    WHEN 46 THEN 47
    ELSE current_position
END
WHERE current_position IN (35, 41, 43, 45, 46);

DELETE FROM properties
WHERE board_position IN (35, 41, 43, 45, 46);

COMMIT;