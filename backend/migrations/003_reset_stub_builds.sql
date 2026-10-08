-- Phase 1 marked steps as built and reviewed without building anything. Send those steps
-- back to teaching so they are really built; their lessons are kept.
UPDATE steps SET state = 'planned', build_note = NULL, review_note = NULL
WHERE build_note LIKE 'Building, review and the code tour arrive in phases 2 and 3.%'
  AND state IN ('taught', 'built', 'reviewed', 'toured');
