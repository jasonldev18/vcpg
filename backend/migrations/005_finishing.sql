-- End of project (SPEC section 6): which stage the project is in, the final review note,
-- the re-test items, and what kind each slide is (title, overview, step, retrospective).
ALTER TABLE projects ADD COLUMN finish_stage TEXT;
ALTER TABLE projects ADD COLUMN final_review_json TEXT;
ALTER TABLE projects ADD COLUMN retest_json TEXT;
ALTER TABLE slides ADD COLUMN kind TEXT NOT NULL DEFAULT 'step';
