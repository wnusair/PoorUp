-- PoorUp board layout revision 4
-- Removes additional highlighted side-row properties and one Chance/Chest pair from active play.

BEGIN;

UPDATE match_players
SET current_position = CASE current_position
    WHEN 1 THEN 2
    WHEN 7 THEN 8
    WHEN 21 THEN 22
    WHEN 28 THEN 29
    WHEN 33 THEN 34
    WHEN 42 THEN 44
    ELSE current_position
END
WHERE current_position IN (1, 7, 21, 28, 33, 42);

DELETE FROM properties
WHERE board_position IN (1, 7, 21, 28);

COMMIT;