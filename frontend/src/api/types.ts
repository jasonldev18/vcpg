// Mirrors the API responses in backend/routes. Rubric text never reaches the client.

export type StepState =
  | 'planned'
  | 'taught'
  | 'built'
  | 'reviewed'
  | 'toured'
  | 'interviewing'
  | 'passed'
  | 'slide_done'
  | 'blocked'

export interface Message {
  id: number
  agent: string
  role: 'user' | 'assistant' | 'reteach'
  content: string
}

export interface Step {
  id: number
  project_id: number
  position: number
  title: string
  component: string
  goal: string
  concepts: string[]
  state: StepState
  current: boolean
  lesson: string | null
  build_note: BuildNote | null
  review_note: ReviewNote | null
  tour: { stops: TourStop[] } | null
  build?: BuildStatus
  chat: Message[]
  gate: Message[]
  progress: { covered: number; total: number }
  can_hint: boolean
}

export interface BuildNote {
  files: { path: string; summary: string }[]
  decisions: string[]
  not_done: string[]
}

export interface ReviewNote {
  commands: { cmd: string; result: 'pass' | 'fail'; summary: string }[]
  cut: { path: string; what: string; why: string }[]
  fixed: { path: string; what: string }[]
  status: 'pass' | 'fail'
  failure: string | null
}

export interface TourStop {
  file: string
  line_start: number
  line_end: number
  explanation: string
}

export interface BuildStatus {
  running: boolean
  paused: boolean
  error: string | null
  isolation: 'docker' | 'venv'
}

export interface PlanView {
  questions: string[]
  project_name: string
  one_liner: string
  stack: string[]
  changes_from_spine: { step: string; change: string; reason: string }[]
  steps: { title: string; goal: string; concepts: string[]; component: string }[]
}

export interface Project {
  id: number
  name: string
  brief: string
  status: 'planning' | 'active' | 'finishing' | 'done'
  plan: PlanView | null
  steps: Step[]
  current_step_id: number | null
  finish: Finish | null
  replan: {
    old: { title: string; goal: string }[]
    new: { title: string; goal: string; concepts: string[]; component: string }[]
    changes: { step: string; change: string; reason: string }[]
  } | null
}

export interface KeyStatus {
  saved: boolean
  last4: string | null
}

export type Visual =
  | {
      kind: 'architecture'
      spec: {
        nodes: { id: string; label: string; group: string }[]
        edges: { from: string; to: string; label: string }[]
      }
    }
  | { kind: 'flow'; spec: { steps: string[] } }
  | {
      kind: 'chart'
      spec: {
        type: 'bar' | 'line' | 'scatter'
        series: { name: string; x: (number | string)[]; y: number[] }[]
        x_label: string
        y_label: string
      }
    }
  | { kind: 'code'; spec: { path: string; lines: [number, number]; highlight: number[] } }
  | { kind: 'table'; spec: { columns: string[]; rows: string[][] } }

export interface SlideData {
  title: string
  kicker: string
  what: string
  visual: Visual
  decisions: { choice: string; tradeoff: string }[]
  failure_and_scale: string[]
  struggled: { question: string; hints: number }[]
  notes: string
}

export interface DeckSlide {
  id: number
  kind: 'title' | 'overview' | 'step' | 'retrospective'
  slide: SlideData
  code: string[] | null
}

export interface DeckExport {
  id: number
  version: number
  format: 'pptx' | 'pdf'
  created_at: string
}

export interface Deck {
  slides: DeckSlide[]
  exports: DeckExport[]
}

export interface Finish {
  stage: 'final_review' | 'retest' | 'deck' | 'readme' | 'done'
  final_review: ReviewNote | null
  final_review_status: { running: boolean; error: string | null }
  retest: {
    passed: number
    total: number
    current_step: string | null
    messages: Message[]
  } | null
}

export interface Readme {
  template: string
  content: string
  review: {
    notes: {
      line: number
      kind: 'does_not_match' | 'gap' | 'unclear'
      note: string
      project_shows: string
    }[]
  } | null
  ready: boolean
}

export interface ArchivedProject {
  id: number
  name: string
  stack: string[]
  finished_at: string | null
  dossier: string | null
  readme: string | null
  exports: DeckExport[]
  mocks: { id: number; length_min: number; focus: string; started_at: string }[]
}

export interface MockInterview {
  id: number
  project_id: number
  length_min: number
  focus: 'deep_dive' | 'system_design' | 'behavioral'
  seconds_left: number
  ended: boolean
  transcript: { role: 'interviewer' | 'learner'; text: string }[]
  scorecard: {
    dimensions: {
      name: 'system_design' | 'failure_modes' | 'motivation_and_impact' | 'communication'
      score: number
      evidence: string | null
      reason: string
    }[]
    practise: string[]
  } | null
}

export interface Idea {
  name: string
  line: string
  pitch: string
  difficulty: 'gentle' | 'medium' | 'stretch'
  step_count: number
  thumbnail: {
    template: 'chat' | 'ranked' | 'cluster' | 'code_hits' | 'chart' | 'pipeline'
    data_json: string
  }
  concepts: { name: string; familiarity: 'new' | 'basics' | 'used' }[]
  architecture: string[]
  questions: string[]
}

export interface IdeaBatch {
  id: number
  topic: string
  cards: Idea[]
}

export interface LessonQuestion {
  type: 'mc' | 'tf' | 'short' | 'code'
  prompt: string
  options: { text: string; correct: boolean; why: string }[]
  answer: string
  rubric: string[]
  tests: string
}

export interface LessonSection {
  kind: 'start_here' | 'see_it' | 'worked_example' | 'check_yourself' | 'your_turn' | 'recap'
  paragraphs: { text: string; citations: string[] }[]
  visual_json: string
  code: string
  questions: LessonQuestion[]
}

export interface LessonContent {
  title: string
  by_the_end: string[]
  sections: LessonSection[]
  community: { text: string; source_id: string }[]
}

export interface LessonPathView {
  id: number
  concept: string
  status: string
  return_idea_id: number | null
  return_card: number | null
  dropped_note: string
  lessons: {
    title: string
    goal: string
    key_terms: string[]
    content: LessonContent | null
    dropped: LessonSection['kind'][]
    passages?: Record<string, { title: string; text: string }>
  }[]
}

export interface SourceRow {
  id: number
  kind: 'trusted' | 'community'
  title: string
  url_or_path: string
  added_by: string
  passages: number
}

export interface TokenStatus extends KeyStatus {
  found: string[]
  problems: string[]
}

export interface AuditState {
  current: { run_id: number; kind: 'project' | 'deep'; stage: string } | null
  runs: {
    id: number
    kind: string
    status: string
    started_at: string
    finished_at: string | null
  }[]
  issues: {
    id: number
    run_id: number
    agent: string
    severity: 'low' | 'medium' | 'high'
    title: string
    evidence: string
    status: string
  }[]
  prs: {
    id: number
    run_id: number
    branch: string
    pr_url: string | null
    auto_merge: number
    state: string
  }[]
  next_deep_scan: string | null
  github: boolean
}
