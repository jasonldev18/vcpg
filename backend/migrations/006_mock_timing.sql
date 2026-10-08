-- Mock interviews are timed: the server stops asking once the chosen length is up.
ALTER TABLE mock_interviews ADD COLUMN started_at TEXT;
ALTER TABLE mock_interviews ADD COLUMN ended_at TEXT;
