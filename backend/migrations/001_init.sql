CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  brief TEXT NOT NULL,
  start_path TEXT NOT NULL CHECK (start_path IN ('plan', 'idea', 'lesson')),
  status TEXT NOT NULL DEFAULT 'planning' CHECK (status IN ('planning', 'active', 'finishing', 'done')),
  workspace_path TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);

CREATE TABLE steps (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  title TEXT NOT NULL,
  component TEXT NOT NULL,
  goal TEXT NOT NULL,
  concepts TEXT NOT NULL DEFAULT '[]',
  files TEXT NOT NULL DEFAULT '[]',
  acceptance TEXT NOT NULL DEFAULT '[]',
  state TEXT NOT NULL DEFAULT 'planned',
  build_note TEXT,
  review_note TEXT,
  commit_sha TEXT,
  UNIQUE (project_id, position)
);

CREATE TABLE rubric_items (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'missing' CHECK (status IN ('missing', 'partial', 'covered')),
  evidence TEXT
);

CREATE TABLE attempts (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('answer', 'hint', 'reteach')),
  content TEXT NOT NULL,
  grader_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  step_id INTEGER REFERENCES steps(id) ON DELETE CASCADE,
  agent TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE slides (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  step_id INTEGER REFERENCES steps(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  json TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE deck_exports (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  format TEXT NOT NULL CHECK (format IN ('pptx', 'pdf')),
  path TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE readmes (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  template TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  review_json TEXT,
  ready INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE lessons (
  id INTEGER PRIMARY KEY,
  concept TEXT NOT NULL,
  path_json TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE sources (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('trusted', 'community')),
  title TEXT NOT NULL,
  url_or_path TEXT NOT NULL,
  added_by TEXT NOT NULL
);

CREATE TABLE passages (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  embedding BLOB,
  position INTEGER NOT NULL,
  UNIQUE (source_id, position)
);

CREATE TABLE dossiers (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  markdown TEXT NOT NULL
);

CREATE TABLE mock_interviews (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  length_min INTEGER NOT NULL CHECK (length_min IN (10, 20, 30)),
  focus TEXT NOT NULL,
  transcript TEXT NOT NULL DEFAULT '[]',
  scorecard_json TEXT
);

CREATE TABLE agent_calls (
  id INTEGER PRIMARY KEY,
  agent TEXT NOT NULL,
  model TEXT NOT NULL,
  effort TEXT NOT NULL,
  runtime TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  step_id INTEGER REFERENCES steps(id) ON DELETE SET NULL,
  input_ref TEXT,
  output_ref TEXT,
  ok INTEGER NOT NULL,
  error TEXT,
  duration_ms INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_overrides (
  agent TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  effort TEXT NOT NULL CHECK (effort IN ('medium', 'high', 'xhigh', 'max'))
);

CREATE TABLE audit_runs (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('project', 'deep')),
  status TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  report_json TEXT
);

CREATE TABLE audit_issues (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
  agent TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  evidence TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE audit_prs (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
  issue_id INTEGER REFERENCES audit_issues(id) ON DELETE SET NULL,
  branch TEXT NOT NULL,
  pr_url TEXT,
  auto_merge INTEGER NOT NULL DEFAULT 0,
  state TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT
);
