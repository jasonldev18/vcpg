-- The tutor's code tour for a step, and a planner revision waiting for the user's approval.
ALTER TABLE steps ADD COLUMN tour_json TEXT;
ALTER TABLE projects ADD COLUMN replan_json TEXT;
