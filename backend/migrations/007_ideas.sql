-- Discovery: idea batches for 'Give me ideas', and where a lesson path returns when done.
CREATE TABLE ideas (
  id INTEGER PRIMARY KEY,
  topic TEXT NOT NULL,
  cards_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE lessons ADD COLUMN return_idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL;
ALTER TABLE lessons ADD COLUMN return_card INTEGER;
